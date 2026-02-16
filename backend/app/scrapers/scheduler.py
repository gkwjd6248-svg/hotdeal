"""APScheduler-based scraping scheduler.

This module provides a background job scheduler that orchestrates
periodic scraping jobs for all active shops. It uses APScheduler
to run scraper adapters at configurable intervals.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional
import traceback
import structlog

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.shop import Shop
from app.models.scraper_job import ScraperJob
from app.scrapers.scraper_service import ScraperService

logger = structlog.get_logger(__name__)


class ScraperScheduler:
    """Manages periodic scraping jobs using APScheduler.

    This scheduler:
    - Starts and stops background scraping jobs
    - Staggers job execution to avoid thundering herd
    - Records job execution results to scraper_jobs table
    - Handles errors gracefully without stopping the scheduler
    """

    def __init__(self, db_session_factory: async_sessionmaker[AsyncSession]):
        """Initialize scraper scheduler.

        Args:
            db_session_factory: Async session factory for database access
        """
        self.db_session_factory = db_session_factory
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.logger = logger.bind(service="scraper_scheduler")
        self._job_ids = {}  # Map shop_slug -> job_id

    def start(self) -> None:
        """Start the scheduler.

        This starts the APScheduler background thread but does NOT
        automatically add jobs. Call add_shop_job() or load_shop_jobs()
        to register scraping jobs.
        """
        if not self.scheduler.running:
            self.scheduler.start()
            self.logger.info("scheduler_started")
        else:
            self.logger.warning("scheduler_already_running")

    def stop(self) -> None:
        """Stop the scheduler gracefully.

        Waits for all running jobs to complete before shutting down.
        """
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            self.logger.info("scheduler_stopped")
        else:
            self.logger.warning("scheduler_not_running")

    async def load_shop_jobs(self) -> int:
        """Load and schedule jobs for all active shops from database.

        Queries the shops table for all active shops and creates
        a periodic job for each one.

        Returns:
            Number of jobs scheduled
        """
        self.logger.info("loading_shop_jobs")

        async with self.db_session_factory() as db:
            result = await db.execute(
                select(Shop).where(Shop.is_active == True)
            )
            shops = list(result.scalars().all())

        jobs_added = 0
        for idx, shop in enumerate(shops):
            # Stagger jobs by shop index * 30 seconds to avoid all jobs firing at once
            offset_seconds = idx * 30

            self.add_shop_job(
                shop_slug=shop.slug,
                interval_minutes=shop.scrape_interval_minutes,
                offset_seconds=offset_seconds,
            )
            jobs_added += 1

        self.logger.info(
            "shop_jobs_loaded",
            count=jobs_added,
        )

        return jobs_added

    def add_shop_job(
        self,
        shop_slug: str,
        interval_minutes: int = 15,
        offset_seconds: int = 0,
    ) -> Optional[Job]:
        """Add a periodic scraping job for a shop.

        Args:
            shop_slug: Shop identifier (e.g., "naver", "coupang")
            interval_minutes: How often to run the job
            offset_seconds: Initial delay before first run (for staggering)

        Returns:
            APScheduler Job instance or None if already exists
        """
        # Check if job already exists
        if shop_slug in self._job_ids:
            self.logger.warning(
                "job_already_exists",
                shop_slug=shop_slug,
            )
            return None

        # Create interval trigger
        trigger = IntervalTrigger(
            minutes=interval_minutes,
            start_date=datetime.now(timezone.utc),
            timezone="UTC",
        )

        # Add job to scheduler
        job = self.scheduler.add_job(
            func=self._run_shop_scrape_wrapper,
            trigger=trigger,
            args=[shop_slug],
            id=f"scrape_{shop_slug}",
            name=f"Scrape {shop_slug}",
            replace_existing=True,
            max_instances=1,  # Prevent concurrent runs of same shop
        )

        self._job_ids[shop_slug] = job.id

        self.logger.info(
            "shop_job_added",
            shop_slug=shop_slug,
            interval_minutes=interval_minutes,
            offset_seconds=offset_seconds,
            next_run=job.next_run_time.isoformat() if job.next_run_time else None,
        )

        # If offset requested, reschedule first run
        if offset_seconds > 0:
            from datetime import timedelta
            next_run = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
            job.modify(next_run_time=next_run)
            self.logger.debug(
                "job_rescheduled_with_offset",
                shop_slug=shop_slug,
                offset_seconds=offset_seconds,
                next_run=next_run.isoformat(),
            )

        return job

    def remove_shop_job(self, shop_slug: str) -> bool:
        """Remove a scraping job for a shop.

        Args:
            shop_slug: Shop identifier

        Returns:
            True if job was removed, False if not found
        """
        job_id = self._job_ids.get(shop_slug)
        if not job_id:
            self.logger.warning("job_not_found", shop_slug=shop_slug)
            return False

        self.scheduler.remove_job(job_id)
        del self._job_ids[shop_slug]

        self.logger.info("shop_job_removed", shop_slug=shop_slug)
        return True

    async def _run_shop_scrape_wrapper(self, shop_slug: str) -> None:
        """Wrapper for run_shop_scrape that handles exceptions.

        This is the function that APScheduler calls. It catches all
        exceptions to prevent job failures from stopping the scheduler.

        Args:
            shop_slug: Shop identifier
        """
        try:
            await self.run_shop_scrape(shop_slug)
        except Exception as e:
            self.logger.error(
                "scrape_job_failed",
                shop_slug=shop_slug,
                error=str(e),
                exc_info=True,
            )

    async def run_shop_scrape(self, shop_slug: str) -> None:
        """Execute a single shop scraping job.

        This method:
        1. Creates a ScraperJob record with status="running"
        2. Runs the scraper adapter via ScraperService
        3. Updates ScraperJob with results and metrics
        4. Handles errors and records them to the database

        Args:
            shop_slug: Shop identifier
        """
        self.logger.info("starting_scrape_job", shop_slug=shop_slug)

        async with self.db_session_factory() as db:
            # Get shop
            result = await db.execute(
                select(Shop).where(Shop.slug == shop_slug)
            )
            shop = result.scalar_one_or_none()

            if not shop:
                self.logger.error("shop_not_found", shop_slug=shop_slug)
                return

            # Create ScraperJob record
            job_record = ScraperJob(
                shop_id=shop.id,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.add(job_record)
            await db.commit()
            await db.refresh(job_record)

            job_id = job_record.id
            start_time = datetime.now(timezone.utc)

            try:
                # Run scraper service
                scraper_service = ScraperService(db)
                stats = await scraper_service.run_adapter(shop_slug)

                # Calculate duration
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()

                # Update job record with success
                job_record.status = "completed"
                job_record.completed_at = end_time
                job_record.duration_seconds = Decimal(str(round(duration, 2)))
                job_record.items_found = stats.get("deals_fetched", 0)
                job_record.items_created = stats.get("products_created", 0)
                job_record.items_updated = stats.get("products_updated", 0)
                job_record.deals_detected = stats.get("deals_created", 0) + stats.get("deals_updated", 0)

                await db.commit()

                self.logger.info(
                    "scrape_job_completed",
                    shop_slug=shop_slug,
                    job_id=str(job_id),
                    duration_seconds=float(duration),
                    **stats,
                )

            except Exception as e:
                # Calculate duration even on failure
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()

                # Update job record with failure
                job_record.status = "failed"
                job_record.completed_at = end_time
                job_record.duration_seconds = Decimal(str(round(duration, 2)))
                job_record.error_message = str(e)
                job_record.error_traceback = traceback.format_exc()

                await db.commit()

                self.logger.error(
                    "scrape_job_failed",
                    shop_slug=shop_slug,
                    job_id=str(job_id),
                    error=str(e),
                    duration_seconds=float(duration),
                    exc_info=True,
                )

    def get_jobs_status(self) -> dict:
        """Get status of all scheduled jobs.

        Returns:
            Dict with job information keyed by shop_slug
        """
        jobs = {}
        for shop_slug, job_id in self._job_ids.items():
            job = self.scheduler.get_job(job_id)
            if job:
                jobs[shop_slug] = {
                    "job_id": job_id,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
        return jobs

    def is_running(self) -> bool:
        """Check if scheduler is running.

        Returns:
            True if scheduler is running
        """
        return self.scheduler.running

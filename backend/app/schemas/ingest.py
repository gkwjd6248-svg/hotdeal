"""Pydantic schemas for the external scraper ingest endpoint.

These schemas define the contract between the local Playwright scraper
running on a developer/production machine and the Render backend API.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Valid choices (mirrors NormalizedDeal in app/scrapers/base.py)
# ---------------------------------------------------------------------------

_VALID_DEAL_TYPES = frozenset(
    ["price_drop", "flash_sale", "coupon", "clearance", "bundle"]
)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class IngestDealItem(BaseModel):
    """A single scraped deal submitted by the local scraper.

    Mirrors the fields available on NormalizedDeal / NormalizedProduct so the
    endpoint can reconstruct those dataclasses without any loss of information.
    """

    external_id: str = Field(
        ...,
        min_length=1,
        description="Shop-specific product identifier (stable across scraper runs)",
        examples=["12345"],
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Product / deal display title",
        examples=["삼성 갤럭시 버즈3 프로 무선 이어폰"],
    )
    deal_price: float = Field(
        ...,
        ge=0,
        description="Current / discounted price in KRW (or shop currency)",
        examples=[29900],
    )
    original_price: Optional[float] = Field(
        None,
        ge=0,
        description="Pre-discount list price. None when not available.",
        examples=[59900],
    )
    deal_url: str = Field(
        ...,
        min_length=1,
        description="Canonical URL of the product / deal page",
        examples=["https://item.gmarket.co.kr/Item?goodscode=12345"],
    )
    image_url: Optional[str] = Field(
        None,
        description="Product image URL",
        examples=["https://cdn.gmarket.co.kr/item/12345.jpg"],
    )
    category_hint: Optional[str] = Field(
        None,
        description=(
            "Category slug or free-text hint used for auto-categorisation "
            "(e.g. 'pc-hardware', '전자제품')"
        ),
        examples=["pc-hardware"],
    )
    deal_type: str = Field(
        "price_drop",
        description="Deal classification. Must be one of: price_drop, flash_sale, coupon, clearance, bundle",
        examples=["price_drop"],
    )
    brand: Optional[str] = Field(
        None,
        max_length=200,
        description="Brand / manufacturer name",
        examples=["Samsung"],
    )
    description: Optional[str] = Field(
        None,
        description="Optional long-form product description",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary shop-specific key-value pairs stored as JSONB",
    )

    @field_validator("deal_type")
    @classmethod
    def validate_deal_type(cls, v: str) -> str:
        """Ensure deal_type is one of the accepted values."""
        if v not in _VALID_DEAL_TYPES:
            raise ValueError(
                f"deal_type must be one of {sorted(_VALID_DEAL_TYPES)}, got '{v}'"
            )
        return v

    @model_validator(mode="after")
    def original_price_gte_deal_price(self) -> "IngestDealItem":
        """Warn-level guard: original_price should not be less than deal_price.

        We don't reject the deal outright because scrapers sometimes report
        incomplete data; the AI scoring will penalise deals with no real
        discount anyway.
        """
        if (
            self.original_price is not None
            and self.original_price < self.deal_price
        ):
            # Swap so downstream logic is never confused by inverted prices.
            self.original_price = None
        return self


class IngestRequest(BaseModel):
    """Payload sent by the local scraper to POST /api/v1/ingest/deals."""

    api_key: str = Field(
        ...,
        min_length=1,
        description="Shared secret that must match INGEST_API_KEY on the server",
    )
    shop_slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Shop identifier that must exist in the shops table (e.g. 'gmarket')",
        examples=["gmarket"],
    )
    deals: List[IngestDealItem] = Field(
        ...,
        min_length=1,
        description="List of scraped deals. Minimum 1 item required.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class IngestStats(BaseModel):
    """Processing statistics returned after a successful ingest request."""

    received: int = Field(..., description="Total deals received in the request")
    products_created: int = Field(
        ..., description="New product rows inserted into the database"
    )
    products_updated: int = Field(
        ..., description="Existing product rows updated with fresh price/data"
    )
    deals_created: int = Field(
        ..., description="New deal rows created (score >= threshold)"
    )
    deals_skipped: int = Field(
        ...,
        description=(
            "Deals whose AI score fell below the configured threshold. "
            "The product and price history are still saved."
        ),
    )
    errors: int = Field(
        ...,
        description="Per-deal processing errors (other deals in the batch still processed)",
    )


class IngestResponse(BaseModel):
    """Response body for POST /api/v1/ingest/deals."""

    status: str = Field("success", description="Always 'success' on HTTP 200")
    stats: IngestStats

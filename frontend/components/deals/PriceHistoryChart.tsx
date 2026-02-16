"use client";

import { formatPrice } from "@/lib/utils";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface PricePoint {
  price: number;
  recorded_at: string;
}

interface PriceHistoryChartProps {
  data: PricePoint[];
  currentPrice: number;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return `${date.getMonth() + 1}/${date.getDate()}`;
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-lg">
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-sm font-bold text-accent">
        {formatPrice(payload[0].value)}
      </p>
    </div>
  );
}

export default function PriceHistoryChart({
  data,
  currentPrice,
}: PriceHistoryChartProps) {
  if (!data || data.length < 2) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-border bg-card text-sm text-gray-500">
        가격 이력 데이터가 부족합니다
      </div>
    );
  }

  const chartData = data.map((point) => ({
    date: formatDate(point.recorded_at),
    fullDate: new Date(point.recorded_at).toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "long",
      day: "numeric",
    }),
    price: point.price,
  }));

  const prices = data.map((p) => p.price);
  if (prices.length === 0) return null;
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const padding = (maxPrice - minPrice) * 0.1 || maxPrice * 0.05;

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">
          가격 변동 추이
        </h3>
        <div className="flex items-center gap-4 text-xs text-gray-400">
          <span>
            최저{" "}
            <span className="font-medium text-green-400">
              {formatPrice(minPrice)}
            </span>
          </span>
          <span>
            최고{" "}
            <span className="font-medium text-red-400">
              {formatPrice(maxPrice)}
            </span>
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
          <defs>
            <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#FF9200" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#FF9200" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: "#6b7280" }}
            tickLine={false}
            axisLine={{ stroke: "#2a2a4a" }}
          />
          <YAxis
            domain={[minPrice - padding, maxPrice + padding]}
            tick={{ fontSize: 11, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) =>
              v >= 10000 ? `${Math.round(v / 10000)}만` : v.toLocaleString()
            }
            width={45}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ stroke: "#FF9200", strokeDasharray: "3 3" }}
          />
          <Area
            type="monotone"
            dataKey="price"
            stroke="#FF9200"
            strokeWidth={2}
            fill="url(#priceGradient)"
            dot={{ r: 3, fill: "#FF9200", stroke: "#1a1a2e", strokeWidth: 2 }}
            activeDot={{ r: 5, fill: "#FF9200", stroke: "#fff", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>

      {currentPrice <= minPrice && (
        <div className="mt-3 rounded-lg bg-green-500/10 px-3 py-2 text-center text-xs font-medium text-green-400">
          현재 가격이 역대 최저가입니다!
        </div>
      )}
    </div>
  );
}

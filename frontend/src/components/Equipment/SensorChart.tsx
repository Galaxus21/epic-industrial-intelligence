/**
 * AI Operations Brain — Sensor Chart
 * SVG line chart for vibration / temperature time-series data.
 * Uses recharts ResponsiveContainer for clean rendering.
 */
"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";

interface DataPoint { ts: string; value: number; }

interface SensorChartProps {
  data: DataPoint[];
  alarmThreshold?: number;
  tripThreshold?: number;
  unit?: string;
  color?: string;
}

export function SensorChart({ data, alarmThreshold, tripThreshold, unit = "", color = "#f59e0b" }: SensorChartProps) {
  const formatted = data.map(d => ({
    ts: d.ts,
    value: d.value,
    label: format(parseISO(d.ts), "MMM d HH:mm"),
  }));

  return (
    <ResponsiveContainer width="100%" height={180}>
      <LineChart data={formatted} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#2a2a2a" />
        <XAxis dataKey="label" tick={{ fill: "#6b7280", fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis tick={{ fill: "#6b7280", fontSize: 10 }} unit={unit} />
        <Tooltip
          contentStyle={{ background: "#1f1f1f", border: "1px solid #2a2a2a", borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: "#a0a0a0" }}
          itemStyle={{ color }}
        />
        {alarmThreshold && (
          <ReferenceLine
            y={alarmThreshold}
            stroke="#f97316"
            strokeDasharray="4 2"
            label={{ value: `Alarm ${alarmThreshold}`, fill: "#f97316", fontSize: 10, position: "insideTopRight" }}
          />
        )}
        {tripThreshold && (
          <ReferenceLine
            y={tripThreshold}
            stroke="#ef4444"
            strokeDasharray="4 2"
            label={{ value: `Trip ${tripThreshold}`, fill: "#ef4444", fontSize: 10, position: "insideTopRight" }}
          />
        )}
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={{ fill: color, r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

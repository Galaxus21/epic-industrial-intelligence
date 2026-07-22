/**
 * AI Operations Brain — Health Ring Component
 * SVG donut chart showing a 0-100 health / score value.
 * Props: value (0-100), size (px), strokeWidth
 */
import clsx from "clsx";

interface HealthRingProps {
  value: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  className?: string;
}

function getColor(value: number): string {
  if (value >= 85) return "#10b981";  // green
  if (value >= 65) return "#f59e0b";  // amber
  if (value >= 45) return "#f97316";  // orange
  return "#ef4444";                   // red
}

export function HealthRing({ value, size = 72, strokeWidth = 6, label, className }: HealthRingProps) {
  const radius = (size - strokeWidth * 2) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = circumference - (value / 100) * circumference;
  const color = getColor(value);
  const center = size / 2;

  return (
    <div className={clsx("flex flex-col items-center gap-1", className)}>
      <svg
        width={size}
        height={size}
        className="-rotate-90"
        aria-label={`${label ?? "Health score"}: ${value}%`}
      >
        <title>{`${label ?? "Health score"}: ${value}% — ${value >= 85 ? "Good condition" : value >= 65 ? "Monitor closely" : value >= 45 ? "Needs attention" : "Critical condition"}`}</title>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#2a2a2a"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={progress}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 0.8s ease" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <span className="text-sm font-bold" style={{ color }}>{value}%</span>
      </div>
      {label && <p className="text-xs text-[#6b7280] text-center">{label}</p>}
    </div>
  );
}

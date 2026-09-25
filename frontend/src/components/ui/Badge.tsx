/**
 * AI Operations Brain — Badge Component
 * Small pill badge for status / severity labels.
 */
import clsx from "clsx";

type BadgeVariant = "critical" | "high" | "medium" | "low" | "info" | "success" | "warning" | "muted";

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
  title?: string;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  critical: "bg-red-500/15 text-red-400 border border-red-500/30",
  high:     "bg-orange-500/15 text-orange-400 border border-orange-500/30",
  medium:   "bg-amber-500/15 text-amber-400 border border-amber-500/30",
  low:      "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
  info:     "bg-blue-500/15 text-blue-400 border border-blue-500/30",
  success:  "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
  warning:  "bg-amber-500/15 text-amber-400 border border-amber-500/30",
  muted:    "bg-[#2a2a2a] text-[#9ca3af] border border-[#333]",
};

export function Badge({ children, variant = "muted", className, title }: BadgeProps) {
  return (
    <span title={title} className={clsx("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium", VARIANT_CLASSES[variant], className)}>
      {children}
    </span>
  );
}

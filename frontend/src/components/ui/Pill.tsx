/**
 * AI Operations Brain — Pill Component
 * Small status/label pill. `capitalize` title-cases and de-underscores the
 * label (opt-in — most callers already pass a pre-formatted label). `icon`
 * renders an optional leading icon and switches the container to inline-flex.
 */
import clsx from "clsx";

interface PillProps {
  label: string;
  cls: string;
  icon?: React.ReactNode;
  capitalize?: boolean;
}

export function Pill({ label, cls, icon, capitalize }: PillProps) {
  return (
    <span className={clsx(
      "text-xs px-2 py-0.5 rounded border font-medium",
      icon != null && "inline-flex items-center gap-1",
      capitalize && "capitalize",
      cls,
    )}>
      {icon}
      {capitalize ? label.replace(/_/g, " ") : label}
    </span>
  );
}

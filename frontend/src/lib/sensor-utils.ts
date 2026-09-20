/**
 * Sensor display and threshold evaluation utilities.
 * Shared between Equipment pages, QueryInterface, and telemetry widgets.
 */

const ACRONYMS = new Set(["DE", "NDE", "DP", "RPM", "HP", "LP", "CW", "MW", "PH"]);

export function formatSensorLabel(key: string): string {
  return key
    .split("_")
    .map(word => {
      const upper = word.toUpperCase();
      if (ACRONYMS.has(upper)) return upper;
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

export function evalAlarmDirection(r: { normal?: number; alarm?: number; alarm_direction?: string }): "low" | "high" {
  if (r.alarm_direction) {
    const d = r.alarm_direction.toLowerCase();
    if (d === "low" || d === "high") return d;
  }
  if (r.alarm !== undefined && r.normal !== undefined && r.alarm < r.normal) {
    return "low";
  }
  return "high";
}

export function isSensorInAlarm(r: { value: number; normal?: number; alarm?: number; alarm_direction?: string }): boolean {
  if (r.alarm === undefined || Number.isNaN(r.value)) return false;
  const dir = evalAlarmDirection(r);
  return dir === "low" ? r.value < r.alarm : r.value > r.alarm;
}

export function isSensorInTrip(r: { value: number; normal?: number; trip?: number; alarm?: number; alarm_direction?: string }): boolean {
  if (r.trip === undefined || Number.isNaN(r.value)) return false;
  const dir = evalAlarmDirection(r);
  return dir === "low" ? r.value <= r.trip : r.value >= r.trip;
}

export function getSensorColor(r: { value: number; normal?: number; alarm?: number; trip?: number; alarm_direction?: string }): string {
  if (isSensorInTrip(r)) return "#ef4444";
  if (isSensorInAlarm(r)) return "#f97316";
  if (r.normal !== undefined && Math.abs(r.value - r.normal) > Math.abs(r.normal) * 0.1) return "#f59e0b";
  return "#10b981";
}

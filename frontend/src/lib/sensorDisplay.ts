/**
 * Sensor display: labels and status colours.
 * Whether a reading is in alarm is decided only by the backend (backend/app/services/alarmEvaluation.py),
 * which sends a status per reading; this file only shows it.
 */

// backend/app/services/sensorLabel.py keeps the same list; keep the two identical.
const sensorAcronyms = new Set(["DE", "NDE", "DP", "RPM", "HP", "LP", "CW", "MW", "PH"]);

const statusColors: Record<string, string> = {
  trip: "#ef4444",
  alarm: "#f97316",
  high: "#f59e0b",
  low: "#60a5fa",
  normal: "#10b981",
};
// Also the colour of "no_reading": a sensor with no number to judge is shown as unknown, never as normal.
const unknownStatusColor = "#6b7280";

export function formatSensorLabel(key: string): string {
  return key
    .split("_")
    .map(word => {
      const upper = word.toUpperCase();
      if (sensorAcronyms.has(upper)) return upper;
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(" ");
}

export function statusColor(status: string | undefined): string {
  return (status && statusColors[status]) || unknownStatusColor;
}

export function isAlarmStatus(status: string | undefined): boolean {
  return status === "alarm" || status === "trip";
}

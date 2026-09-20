/**
 * EPIC — Equipment Detail Page
 * Shows equipment brain connections, sensor charts, and timeline.
 */
import Link from "next/link";
import { getEquipment, getEquipmentBrain, getEquipmentTimeline, getEquipmentSensors } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { EquipmentTimeline } from "@/components/Equipment/EquipmentTimeline";
import { SensorChart } from "@/components/Equipment/SensorChart";
import { BrainConnections } from "@/components/Equipment/BrainConnections";
import { AlertTriangle, ArrowLeft, BrainCircuit, Zap } from "lucide-react";
import { formatSensorLabel, isSensorInAlarm } from "@/lib/sensor-utils";

export const dynamic = "force-dynamic";

export default async function EquipmentDetailPage({ params }: { params: { id: string } }) {
  const [eq, brain, timeline, sensors] = await Promise.all([
    getEquipment(params.id).catch(() => null),
    getEquipmentBrain(params.id).catch(() => ({})),
    getEquipmentTimeline(params.id).catch(() => ({ equipment_id: params.id, events: [] })),
    getEquipmentSensors(params.id).catch(() => ({ equipment_id: params.id, sensors: {} as Record<string, { ts: string; value: number }[]> })),
  ]);

  if (!eq) {
    return (
      <div className="p-6 text-center">
        <p className="text-[#6b7280]">Equipment {params.id} not found.</p>
      </div>
    );
  }

  const vibrationReading = eq.current_readings?.vibration_de;
  const vibrationAlert = vibrationReading && vibrationReading.alarm && vibrationReading.value > vibrationReading.alarm;
  const healthColor = eq.health_score == null ? "#6b7280" : eq.health_score >= 85 ? "#10b981" : eq.health_score >= 65 ? "#f59e0b" : eq.health_score >= 45 ? "#f97316" : "#ef4444";

  return (
    <div className="p-6">
      {/* Back */}
      <Link href="/" className="inline-flex items-center gap-1.5 text-xs text-[#6b7280] hover:text-[#a0a0a0] mb-4 transition-colors">
        <ArrowLeft size={12} /> Back to Dashboard
      </Link>

      {/* Equipment Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-[#6b7280]">{eq.id}</span>
            <Badge variant={eq.criticality === "Critical" ? "critical" : eq.criticality === "High" ? "high" : "muted"}>
              {eq.criticality} Criticality
            </Badge>
            {vibrationAlert && (
              <Badge variant="high">
                <AlertTriangle size={10} className="mr-1" /> Vibration Alarm
              </Badge>
            )}
          </div>
          <h1 className="text-2xl font-bold text-[#f9f9f9]">{eq.name}</h1>
          <p className="text-sm text-[#6b7280] mt-1">{eq.type} · {eq.location}</p>
          {eq.manufacturer && (
            <p className="text-xs text-[#6b7280] mt-0.5">{eq.manufacturer} {eq.model}</p>
          )}
        </div>

        {/* Quick score card */}
        <div className="grid grid-cols-2 gap-3">
          <ScoreBox label="Health" value={eq.health_score} color={healthColor} unit="%" />
          <ScoreBox label="Failure Risk" value={eq.failure_probability} color={(eq.failure_probability ?? 0) > 15 ? "#f97316" : "#10b981"} unit="%" />
          <ScoreBox label="Compliance" value={eq.compliance_score} color={(eq.compliance_score ?? 0) >= 90 ? "#10b981" : "#f59e0b"} unit="%" />
          <ScoreBox label="Maint. Due" value={eq.maintenance_due_days} color={(eq.maintenance_due_days ?? 99) <= 7 ? "#f97316" : "#a0a0a0"} unit="d" />
        </div>
      </div>

      {/* AI Query CTA */}
      <Link href={`/query?equipment=${eq.id}`}>
        <div className="flex items-center gap-3 p-4 mb-6 bg-amber-500/10 border border-amber-500/30 rounded-xl hover:bg-amber-500/15 transition-colors cursor-pointer">
          <BrainCircuit size={20} className="text-amber-400 flex-shrink-0" />
          <div>
            <p className="text-sm font-semibold text-amber-400">Ask EPIC</p>
            <p className="text-xs text-[#a0a0a0]">e.g., "Pump vibration increased today. Can I continue operating?"</p>
          </div>
          <Zap size={14} className="text-amber-500 ml-auto" />
        </div>
      </Link>

      {/* Current Readings */}
      {eq.current_readings && Object.keys(eq.current_readings).length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-[#a0a0a0] mb-3">Current Readings</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {Object.entries(eq.current_readings).map(([key, reading]) => {
              const isAlarm = isSensorInAlarm(reading);
              return (
                <div key={key} className={`bg-[#1f1f1f] border rounded-lg p-3 ${isAlarm ? "border-orange-500/40" : "border-[#2a2a2a]"}`}>
                  <p className="text-xs text-[#a0a0a0] mb-1">{formatSensorLabel(key)}</p>
                  <p className={`text-lg font-bold ${isAlarm ? "text-orange-400" : "text-[#f9f9f9]"}`}>
                    {reading.value}
                    <span className="text-xs font-normal text-[#6b7280] ml-1">{reading.unit}</span>
                  </p>
                  {reading.alarm && (
                    <p className="text-xs text-[#6b7280]">Alarm: {reading.alarm}</p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Two-column layout: Brain + Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Brain Connections */}
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
          <h2 className="text-sm font-semibold text-[#a0a0a0] mb-4">Equipment Knowledge Graph</h2>
          <BrainConnections brain={brain as Record<string, unknown>} equipmentId={params.id} />
        </div>

        {/* Timeline */}
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
          <h2 className="text-sm font-semibold text-[#a0a0a0] mb-4">Equipment Timeline</h2>
          <EquipmentTimeline events={timeline.events} />
        </div>
      </div>

      {/* Sensor History Chart */}
      {sensors.sensors.vibration_de && sensors.sensors.vibration_de.length > 0 && (
        <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl p-4">
          <h2 className="text-sm font-semibold text-[#a0a0a0] mb-4">Vibration Trend (DE Bearing)</h2>
          <SensorChart data={sensors.sensors.vibration_de} alarmThreshold={7.1} tripThreshold={11.2} unit="mm/s" />
        </div>
      )}
    </div>
  );
}

function ScoreBox({ label, value, color, unit }: { label: string; value: number | null; color: string; unit: string }) {
  return (
    <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-3 text-center min-w-[80px]">
      <p className="text-xs text-[#6b7280] mb-1">{label}</p>
      <p className="text-xl font-bold" style={{ color }}>{value != null ? `${value}${unit}` : "—"}</p>
    </div>
  );
}

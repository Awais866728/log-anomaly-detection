import {
  SERVICE_NAMES,
  type Alert,
  type Kpis,
  type ServiceName,
  type ServiceStatus,
  type VolumePoint,
} from "@/lib/types"

export const kpis: Kpis = {
  logsPerMinute: 1284,
  avgDetectionLatencyMs: 42,
}

export const recentAlerts: Alert[] = [
  { id: "a1", time: "14:32:05", service: "ssh", model: "DeepLog LSTM", severity: "critical", reason: "300 failed password events in 1 minute" },
  { id: "a2", time: "14:27:41", service: "nginx", model: "PCA", severity: "warning", reason: "Spike of 404 responses on /api/admin" },
  { id: "a3", time: "14:19:12", service: "app", model: "Random Forest", severity: "warning", reason: "Error rate on POST /items 6x above normal" },
  { id: "a4", time: "14:05:58", service: "postgres", model: "Random Forest", severity: "critical", reason: "Repeated authentication failures for user loguser" },
  { id: "a5", time: "13:51:30", service: "ssh", model: "PCA", severity: "warning", reason: "Login from a source IP never seen before" },
]

export const serviceStatuses: ServiceStatus[] = [
  { name: "nginx", container: "log-anomaly-nginx-1", health: "healthy" },
  { name: "app", container: "log-anomaly-app-1", health: "healthy" },
  { name: "postgres", container: "log-anomaly-postgres-1", health: "healthy" },
  { name: "ssh", container: "log-anomaly-ssh-1", health: "healthy" },
]

// Typical log lines per minute for each service
const BASE_RATE: Record<ServiceName, number> = { nginx: 520, app: 470, postgres: 180, ssh: 60 }

function minuteLabel(date: Date) {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`
}

function simulatePoint(date: Date): VolumePoint {
  const point = { time: minuteLabel(date) } as VolumePoint
  for (const service of SERVICE_NAMES) {
    point[service] = Math.round(BASE_RATE[service] * (0.85 + Math.random() * 0.3))
  }
  return point
}

// Simulated feed: re-estimates the current minute, starts a new point when the minute changes
export function nextLogVolume(points: VolumePoint[], now: Date, minutes = 30): VolumePoint[] {
  if (points.length === 0) {
    return Array.from({ length: minutes }, (_, i) => simulatePoint(new Date(now.getTime() - (minutes - 1 - i) * 60_000)))
  }
  const current = simulatePoint(now)
  const last = points[points.length - 1]
  return last.time === current.time ? [...points.slice(0, -1), current] : [...points, current].slice(-minutes)
}

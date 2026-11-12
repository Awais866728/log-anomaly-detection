export const SERVICE_NAMES = ["nginx", "app", "postgres", "ssh"] as const

export type ServiceName = (typeof SERVICE_NAMES)[number]

export type Severity = "critical" | "warning"

export type Health = "healthy" | "down"

export interface Kpis {
  logsPerMinute: number
  avgDetectionLatencyMs: number
}

export interface Alert {
  id: string
  time: string
  service: ServiceName
  model: string
  severity: Severity
  reason: string
}

export interface ServiceStatus {
  name: ServiceName
  container: string
  health: Health
}

// One point per minute: log lines per service
export type VolumePoint = { time: string } & Record<ServiceName, number>

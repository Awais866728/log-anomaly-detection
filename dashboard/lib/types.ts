export const SERVICE_NAMES = ["nginx", "app", "postgres", "ssh"] as const

export type ServiceName = (typeof SERVICE_NAMES)[number]

// Alerts can also come from replayed offline datasets such as HDFS
export type AlertSource = ServiceName | "hdfs (replay)"

export type Severity = "critical" | "warning"

export type Health = "healthy" | "warning" | "down"

export interface Kpis {
  avgDetectionLatencyMs: number
}

export interface EventContribution {
  label: string
  template: string
  count: number
  normalCount: number
}

export interface Alert {
  id: string
  time: string
  window: string
  source: AlertSource
  model: string
  severity: Severity
  status: "open" | "resolved"
  probability: number
  reason: string
  events: EventContribution[]
  logLines: string[]
}

export interface ServiceStatus {
  name: ServiceName
  container: string
  health: Health
  uptime: string
  logsPerMinute: number
  sparkline: number[]
}

export interface PipelineStep {
  name: string
  detail: string
  health: Health
}

export const DATASETS = ["HDFS", "BGL"] as const

export type Dataset = (typeof DATASETS)[number]

export interface Scores {
  precision: number
  recall: number
  f1: number
}

export interface ModelResult {
  name: string
  kind: string
  description: string
  scores: Record<Dataset, Scores>
}

export type LogLevel = "INFO" | "WARN" | "ERROR"

export interface LogLine {
  id: number
  time: string
  service: ServiceName
  level: LogLevel
  message: string
  alertId?: string
}

// One point per minute: log lines per service
export type VolumePoint = { time: string } & Record<ServiceName, number>

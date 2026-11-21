export const SERVICE_NAMES = ["nginx", "app", "postgres", "ssh"] as const

export type ServiceName = (typeof SERVICE_NAMES)[number]

// Alerts can also come from replayed offline datasets (HDFS, BGL)
export const REPLAY_SOURCES = ["hdfs (replay)", "bgl (replay)"] as const

export type AlertSource = ServiceName | (typeof REPLAY_SOURCES)[number]

// "Alert": a model flags the window; "New template": the only reason is an event never seen in normal training
export type AlertLevel = "Alert" | "New template"

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
  // SHAP contribution to the anomaly class (Random Forest only); null for other models and unseen templates
  shap?: number | null
  // count 0 although normal windows have this event: "expected but missing"
  missing?: boolean
  // event never seen in normal training (a new template)
  unseen?: boolean
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
  level?: AlertLevel
  flaggedBy?: string[]
  setting?: string | null
  lastLineTime?: string | null // time of the last log line in the window (the log's own clock)
  alertTime?: string // when the detector produced the alert
  latencyMs?: number // from the last line reaching the stream to the alert
  lineIds?: number[]
  trueLabel?: number | null // replay only: 1 if the window is labelled anomalous
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
  false_alarm_rate?: number
}

export interface ModelResult {
  name: string
  kind: string
  description: string
  scores: Record<Dataset, Scores>
  settings?: Partial<Record<Dataset, string>>
}

export type LogLevel = "INFO" | "WARN" | "ERROR"

export interface LogLine {
  id: number
  time: string
  service: ServiceName | (typeof REPLAY_SOURCES)[number]
  level: LogLevel
  message: string
  alertId?: string
}

// One point per minute: log lines per service
export type VolumePoint = { time: string } & Record<ServiceName, number>

export const SERVICE_NAMES = ["nginx", "app", "postgres", "ssh"] as const

export type ServiceName = (typeof SERVICE_NAMES)[number]

// Alerts can also come from replayed offline datasets (HDFS and BGL with labels, OpenSSH and Apache without)
export const REPLAY_SOURCES = ["hdfs (replay)", "bgl (replay)", "openssh (replay)", "apache (replay)"] as const

export const ALL_SOURCES = [...SERVICE_NAMES, ...REPLAY_SOURCES] as const

export type AlertSource = ServiceName | (typeof REPLAY_SOURCES)[number]

// "Alert": a model flags the window; "New template": the only reason is an event never seen in normal training
export type AlertLevel = "Alert" | "New template"

export type Severity = "critical" | "warning"

export type Health = "healthy" | "warning" | "down"

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

// null = not known yet (no line received / docker not readable): shown as "no data yet"
export interface ServiceStatus {
  name: ServiceName
  container: string | null
  state: string | null // docker compose ps: running, exited, ...
  status: string | null // docker compose ps: "Up 4 hours (healthy)"
  health: Health | null
  uptime: string | null
  logsPerMinute: number | null // lines received in the last 60 s
  lastLineReceived: string | null
  sparkline: number[] // lines per full minute, last 12 minutes since the detection service started
  alerts: number
  newTemplates: number
  models: string[]
}

export interface PipelineStep {
  name: string
  detail: string
  health: Health | null
}

// Labelled datasets: precision / recall / F1 on the test set
export const DATASETS = ["HDFS", "BGL"] as const

export type Dataset = (typeof DATASETS)[number]

// No labels: only the share of windows flagged, with the settings chosen on HDFS and on BGL
export const UNLABELLED_DATASETS = ["OpenSSH", "Apache"] as const

export type UnlabelledDataset = (typeof UNLABELLED_DATASETS)[number]

export interface FlagRate {
  chosen_on: string
  setting: string
  flag_rate: number
}

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
  unlabelled: Record<UnlabelledDataset, FlagRate[]>
}

// A model pack loaded in the detection service
export interface PackInfo {
  source: string
  label: string
  mode: "live" | "replay"
  dataset: string
  models: string[]
  settings: Record<string, string>
  templates: number
  train_windows: number | null
  window: string
  labelled: boolean
  settings_from: string | null // unlabelled packs: the labelled dataset their settings were chosen on
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

// One point per full minute: live log lines per service
export type VolumePoint = { time: string } & Record<ServiceName, number>

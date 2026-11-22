"use client"

import { useEffect, useRef, useState } from "react"

import type {
  Alert,
  AlertLevel,
  AlertSource,
  Health,
  LogLevel,
  LogLine,
  ModelResult,
  PackInfo,
  PipelineStep,
  ServiceName,
  ServiceStatus,
  VolumePoint,
} from "@/lib/types"

// Detection service (src/streaming/service.py). Set NEXT_PUBLIC_DETECTOR_URL before `next dev` / `next build`.
export const DETECTOR_URL = process.env.NEXT_PUBLIC_DETECTOR_URL ?? "http://localhost:8000"

const MAX_LINES = 200 // per source, so a fast replay doesn't push the live services out
const MAX_ALERTS = 200 // per source: a BGL replay alone makes many alerts per second

// ---------------------------------------------------------------- service formats (snake_case, as in explain_alert)

interface ServiceEvent {
  event: string
  template: string
  count: number
  shap: number | null
  normal_count: number
  missing: boolean
  unseen: boolean
}

export interface ServiceAlert {
  id: string
  level: AlertLevel
  window_id: string | number
  dataset: string
  source: string
  model: string
  anomaly_probability: number
  reason: "model" | "unseen event"
  top_events: ServiceEvent[]
  flagged_by: string[]
  unseen_events: string[]
  setting: string | null
  window: string
  n_lines: number
  last_line_time: string | null
  last_line_received: string
  alert_time: string
  latency_ms: number
  log_lines: string[]
  line_ids: number[]
  true_label: number | null
  status: "open" | "resolved"
}

interface ServiceLogLine {
  id: number
  time: string
  received: string
  service: string
  level: LogLevel
  message: string
}

export interface DetectorStats {
  lines: number
  windows: number
  logs_per_minute: number
  alerts: number
  new_templates: number
  new_template_repeats: number
  avg_detection_latency_ms: number | null
  late_hdfs_lines: number
  packs: Record<string, { mode: string; models: string[]; settings: Record<string, string> }>
}

interface ServiceSystem {
  services: {
    name: ServiceName
    container: string | null
    state: string | null
    status: string | null
    health: Health | null
    uptime: string | null
    logs_per_minute: number | null
    last_line_received: string | null
    sparkline: number[]
    alerts: number
    new_templates: number
    models: string[]
  }[]
  pipeline: PipelineStep[]
  volume: ({ minute: number } & Record<ServiceName, number>)[]
  docker_available: boolean
}

// ---------------------------------------------------------------- mapping to the dashboard types

function clock(isoTime: string) {
  return new Date(isoTime).toLocaleTimeString("en-GB", { hour12: false })
}

function summary(a: ServiceAlert) {
  if (a.level === "New template") {
    const first = a.top_events[0]
    return `New template: ${first ? first.template : a.unseen_events.join(", ")}`
  }
  const others = a.flagged_by.filter((m) => m !== a.model)
  return `${a.model} flagged this window${others.length ? ` (also ${others.join(", ")})` : ""}`
}

export function toAlert(a: ServiceAlert): Alert {
  return {
    id: a.id,
    time: clock(a.alert_time),
    window: a.window,
    source: a.source as AlertSource,
    model: a.model,
    severity: a.level === "Alert" ? "critical" : "warning",
    status: a.status,
    probability: a.anomaly_probability, // anomaly_probability -> probability
    reason: summary(a),
    events: a.top_events.map((e) => ({
      // top_events -> events
      label: e.event,
      template: e.template,
      count: e.count,
      normalCount: e.normal_count,
      shap: e.shap,
      missing: e.missing,
      unseen: e.unseen,
    })),
    logLines: a.log_lines,
    level: a.level,
    flaggedBy: a.flagged_by,
    setting: a.setting,
    lastLineTime: a.last_line_time,
    alertTime: a.alert_time,
    latencyMs: a.latency_ms,
    lineIds: a.line_ids,
    trueLabel: a.true_label,
  }
}

function toLogLine(l: ServiceLogLine): LogLine {
  return { id: l.id, time: clock(l.received), service: l.service as LogLine["service"], level: l.level, message: l.message }
}

// ---------------------------------------------------------------- data access

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${DETECTOR_URL}${path}`, { cache: "no-store" })
  if (!response.ok) throw new Error(`${path}: ${response.status}`)
  return response.json() as Promise<T>
}

export function getModelResults() {
  return getJson<ModelResult[]>("/api/models")
}

export function getPacks() {
  return getJson<PackInfo[]>("/api/packs")
}

export interface SystemStatus {
  connection: Connection
  // null until the first answer arrives
  services: ServiceStatus[] | null
  pipeline: PipelineStep[] | null
  volume: VolumePoint[] | null
  dockerAvailable: boolean | null
}

const SYSTEM_POLL_MS = 5000

function minuteLabel(unixSeconds: number) {
  return new Date(unixSeconds * 1000).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false })
}

// Container state (docker compose ps), log volume and pipeline status from the detection service, every 5 s
export function useSystemStatus(): SystemStatus {
  const [state, setState] = useState<SystemStatus>({
    connection: "connecting",
    services: null,
    pipeline: null,
    volume: null,
    dockerAvailable: null,
  })

  useEffect(() => {
    let closed = false
    const load = () =>
      getJson<ServiceSystem>("/api/system")
        .then((s) => {
          if (closed) return
          setState({
            connection: "live",
            services: s.services.map((x) => ({
              name: x.name,
              container: x.container,
              state: x.state,
              status: x.status,
              health: x.health,
              uptime: x.uptime,
              logsPerMinute: x.logs_per_minute,
              lastLineReceived: x.last_line_received ? clock(x.last_line_received) : null,
              sparkline: x.sparkline,
              alerts: x.alerts,
              newTemplates: x.new_templates,
              models: x.models,
            })),
            pipeline: s.pipeline,
            volume: s.volume.map(({ minute, ...counts }) => ({ time: minuteLabel(minute), ...counts })),
            dockerAvailable: s.docker_available,
          })
        })
        .catch(() => !closed && setState((prev) => ({ ...prev, connection: "offline" })))
    load()
    const timer = setInterval(load, SYSTEM_POLL_MS)
    return () => {
      closed = true
      clearInterval(timer)
    }
  }, [])

  return state
}

export type Connection = "connecting" | "live" | "offline"

export interface DetectorFeed {
  connection: Connection
  // newest first; the last MAX_LINES of each source
  lines: LogLine[]
  alerts: Alert[] // newest first; the last MAX_ALERTS of each source
  stats: DetectorStats | null
  // line id -> alert id, for log lines that belong to an alerted window
  lineAlerts: Record<number, string>
}

// Initial state from the REST endpoints, then live updates over server-sent events (/api/events)
export function useDetectorFeed({ paused = false } = {}): DetectorFeed {
  const [connection, setConnection] = useState<Connection>("connecting")
  const [lines, setLines] = useState<Record<string, LogLine[]>>({})
  const [alerts, setAlerts] = useState<Record<string, Alert[]>>({})
  const [stats, setStats] = useState<DetectorStats | null>(null)
  // pausing only freezes the log view; alerts and stats keep updating
  const pausedRef = useRef(paused)
  useEffect(() => {
    pausedRef.current = paused
  }, [paused])

  useEffect(() => {
    let closed = false
    Promise.all([
      getJson<ServiceLogLine[]>(`/api/logs?limit=${MAX_LINES}`),
      getJson<ServiceAlert[]>(`/api/alerts?limit=${MAX_ALERTS}`),
      getJson<DetectorStats>("/api/stats"),
    ])
      .then(([l, a, s]) => {
        if (closed) return
        setLines(addLines({}, l.map(toLogLine)))
        setAlerts(addAlerts({}, a.map(toAlert)))
        setStats(s)
      })
      .catch(() => !closed && setConnection("offline"))

    const source = new EventSource(`${DETECTOR_URL}/api/events`)
    source.onopen = () => setConnection("live")
    source.onerror = () => setConnection("offline") // EventSource reconnects by itself
    source.addEventListener("alert", (e) => {
      const alert = toAlert(JSON.parse((e as MessageEvent).data))
      setAlerts((prev) => addAlerts(prev, [alert]))
    })
    source.addEventListener("stats", (e) => setStats(JSON.parse((e as MessageEvent).data)))
    source.addEventListener("logs", (e) => {
      if (pausedRef.current) return
      const fresh = (JSON.parse((e as MessageEvent).data) as ServiceLogLine[]).map(toLogLine)
      setLines((prev) => addLines(prev, fresh))
    })
    return () => {
      closed = true
      source.close()
    }
  }, [])

  const lineAlerts: Record<number, string> = {}
  const allAlerts = Object.values(alerts)
    .flat()
    .sort((a, b) => (b.alertTime ?? "").localeCompare(a.alertTime ?? ""))
  for (const alert of allAlerts) for (const id of alert.lineIds ?? []) lineAlerts[id] = alert.id
  const merged = Object.values(lines)
    .flat()
    .sort((a, b) => b.id - a.id)
  return { connection, lines: merged, alerts: allAlerts, stats, lineAlerts }
}

// Add alerts to the per-source lists: newest first, MAX_ALERTS per source, no duplicates
function addAlerts(prev: Record<string, Alert[]>, fresh: Alert[]) {
  const next = { ...prev }
  for (const alert of fresh) {
    const kept = (next[alert.source] ?? []).filter((a) => a.id !== alert.id)
    next[alert.source] = [alert, ...kept]
      .sort((a, b) => (b.alertTime ?? "").localeCompare(a.alertTime ?? ""))
      .slice(0, MAX_ALERTS)
  }
  return next
}

// Add lines (any order) to the per-source buffers: newest first, MAX_LINES per source
function addLines(prev: Record<string, LogLine[]>, fresh: LogLine[]) {
  const next = { ...prev }
  const bySource: Record<string, LogLine[]> = {}
  for (const line of fresh) (bySource[line.service] ??= []).push(line)
  for (const [source, items] of Object.entries(bySource)) {
    next[source] = [...items.sort((a, b) => b.id - a.id), ...(next[source] ?? [])].slice(0, MAX_LINES)
  }
  return next
}

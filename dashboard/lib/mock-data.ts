import {
  SERVICE_NAMES,
  type Alert,
  type Kpis,
  type LogLevel,
  type LogLine,
  type ModelResult,
  type PipelineStep,
  type ServiceName,
  type ServiceStatus,
  type VolumePoint,
} from "@/lib/types"

// Simulated network delay, so loading skeletons are visible
const delay = () => new Promise((resolve) => setTimeout(resolve, 800))

const kpis: Kpis = { avgDetectionLatencyMs: 42 }

const alerts: Alert[] = [
  {
    id: "a1",
    time: "14:32:05",
    window: "14:31:00 – 14:32:00",
    source: "ssh",
    model: "DeepLog LSTM",
    severity: "critical",
    status: "open",
    probability: 0.98,
    reason: "SSH brute force: 300 failed password events in 1 minute",
    events: [
      { template: "Failed password for <*> from <*> port <*> ssh2", count: 300, normalCount: 2 },
      { template: "Invalid user <*> from <*> port <*>", count: 142, normalCount: 0 },
      { template: "Connection closed by authenticating user <*> <*> port <*> [preauth]", count: 96, normalCount: 1 },
      { template: "Disconnected from invalid user <*> <*> port <*> [preauth]", count: 88, normalCount: 0 },
    ],
    logLines: [
      "Failed password for root from 45.13.22.9 port 51022 ssh2",
      "Invalid user admin from 45.13.22.9 port 51023",
      "Failed password for invalid user admin from 45.13.22.9 port 51023 ssh2",
      "Connection closed by authenticating user root 45.13.22.9 port 51022 [preauth]",
      "Failed password for root from 45.13.22.9 port 51024 ssh2",
      "Invalid user oracle from 45.13.22.9 port 51025",
      "Disconnected from invalid user oracle 45.13.22.9 port 51025 [preauth]",
      "Failed password for root from 45.13.22.9 port 51026 ssh2",
    ],
  },
  {
    id: "a2",
    time: "14:27:41",
    window: "14:26:00 – 14:27:00",
    source: "nginx",
    model: "PCA",
    severity: "warning",
    status: "open",
    probability: 0.81,
    reason: "Traffic spike: 9x the normal request rate",
    events: [
      { template: '<*> - - [<*>] "GET /api/items HTTP/1.1" 200 <*>', count: 4820, normalCount: 520 },
      { template: '<*> - - [<*>] "POST /api/items HTTP/1.1" 201 <*>', count: 910, normalCount: 140 },
      { template: '<*> - - [<*>] "GET / HTTP/1.1" 200 <*>', count: 610, normalCount: 60 },
    ],
    logLines: [
      '172.20.0.1 - - [12/Nov/2026:14:26:01 +0000] "GET /api/items HTTP/1.1" 200 209',
      '172.20.0.1 - - [12/Nov/2026:14:26:01 +0000] "GET /api/items HTTP/1.1" 200 209',
      '172.20.0.1 - - [12/Nov/2026:14:26:01 +0000] "POST /api/items HTTP/1.1" 201 67',
      '172.20.0.1 - - [12/Nov/2026:14:26:02 +0000] "GET / HTTP/1.1" 200 615',
      '172.20.0.1 - - [12/Nov/2026:14:26:02 +0000] "GET /api/items HTTP/1.1" 200 209',
      '172.20.0.1 - - [12/Nov/2026:14:26:02 +0000] "GET /api/items HTTP/1.1" 200 209',
    ],
  },
  {
    id: "a3",
    time: "14:18:40",
    window: "14:17:00 – 14:18:00",
    source: "app",
    model: "Random Forest",
    severity: "critical",
    status: "resolved",
    probability: 0.99,
    reason: "Database down: app cannot connect to postgres",
    events: [
      { template: "<*> ERROR GET /items database error: connect ECONNREFUSED <*>", count: 412, normalCount: 0 },
      { template: "<*> INFO <*> GET /items 500 <*>", count: 389, normalCount: 1 },
      { template: "<*> ERROR POST /items database error: connect ECONNREFUSED <*>", count: 104, normalCount: 0 },
      { template: "<*> ERROR database not ready (attempt <*>): <*>", count: 9, normalCount: 0 },
    ],
    logLines: [
      "2026-11-12T14:17:02.118Z ERROR GET /items database error: connect ECONNREFUSED 172.20.0.3:5432",
      "2026-11-12T14:17:02.119Z INFO 172.20.0.1 GET /items 500 3ms",
      "2026-11-12T14:17:02.404Z ERROR POST /items database error: connect ECONNREFUSED 172.20.0.3:5432",
      "2026-11-12T14:17:02.405Z INFO 172.20.0.1 POST /items 500 2ms",
      "2026-11-12T14:17:03.880Z ERROR database not ready (attempt 1): connect ECONNREFUSED 172.20.0.3:5432",
      "2026-11-12T14:17:05.881Z ERROR database not ready (attempt 2): connect ECONNREFUSED 172.20.0.3:5432",
    ],
  },
  {
    id: "a4",
    time: "13:47:55",
    window: "block blk_-3544583377289625738",
    source: "hdfs",
    model: "DeepLog LSTM",
    severity: "critical",
    status: "resolved",
    probability: 0.97,
    reason: "HDFS block failure: block could not be written or deleted",
    events: [
      { template: "Unexpected error trying to delete block <BLK>. BlockInfo not found in volumeMap.", count: 3, normalCount: 0 },
      { template: "writeBlock <BLK> received exception java.io.IOException: Could not read from stream", count: 2, normalCount: 0 },
      { template: "PacketResponder <NUM> for block <BLK> Interrupted.", count: 2, normalCount: 0 },
      { template: "Receiving block <BLK> src: /<IP> dest: /<IP>", count: 3, normalCount: 3 },
    ],
    logLines: [
      "081109 214043 2561 INFO dfs.DataNode$DataXceiver: Receiving block blk_-3544583377289625738 src: /10.250.11.100:37794 dest: /10.250.11.100:50010",
      "081109 214043 2563 INFO dfs.DataNode$DataXceiver: writeBlock blk_-3544583377289625738 received exception java.io.IOException: Could not read from stream",
      "081109 214043 2564 INFO dfs.DataNode$PacketResponder: PacketResponder 1 for block blk_-3544583377289625738 Interrupted.",
      "081110 103524 19 WARN dfs.FSDataset: Unexpected error trying to delete block blk_-3544583377289625738. BlockInfo not found in volumeMap.",
    ],
  },
  {
    id: "a5",
    time: "13:31:30",
    window: "13:30:00 – 13:31:00",
    source: "ssh",
    model: "PCA",
    severity: "warning",
    status: "resolved",
    probability: 0.74,
    reason: "Login from a source IP never seen before",
    events: [
      { template: "Accepted password for <*> from <*> port <*> ssh2", count: 1, normalCount: 0 },
      { template: "pam_unix(sshd:session): session opened for user <*>", count: 1, normalCount: 0 },
      { template: "Received disconnect from <*> port <*>:11: disconnected by user", count: 1, normalCount: 0 },
    ],
    logLines: [
      "Accepted password for testuser from 10.0.0.23 port 40122 ssh2",
      "pam_unix(sshd:session): session opened for user testuser(uid=1000) by testuser(uid=0)",
      "Received disconnect from 10.0.0.23 port 40122:11: disconnected by user",
    ],
  },
]

const services: ServiceStatus[] = [
  { name: "nginx", container: "log-anomaly-nginx-1", health: "healthy", uptime: "3d 4h", logsPerMinute: 520, sparkline: [498, 512, 530, 505, 541, 520, 515, 533, 508, 520, 526, 519] },
  { name: "app", container: "log-anomaly-app-1", health: "healthy", uptime: "3d 4h", logsPerMinute: 470, sparkline: [455, 461, 480, 472, 466, 490, 470, 458, 476, 483, 465, 470] },
  { name: "postgres", container: "log-anomaly-postgres-1", health: "healthy", uptime: "2h 13m", logsPerMinute: 180, sparkline: [172, 168, 185, 190, 176, 181, 179, 174, 188, 183, 177, 180] },
  { name: "ssh", container: "log-anomaly-ssh-1", health: "healthy", uptime: "3d 4h", logsPerMinute: 60, sparkline: [58, 55, 62, 59, 64, 57, 61, 60, 56, 63, 59, 60] },
]

const pipeline: PipelineStep[] = [
  { name: "Servers", detail: "4 containers", health: "healthy" },
  { name: "Log collector", detail: "docker logs", health: "healthy" },
  { name: "Queue", detail: "1.2k messages behind", health: "warning" },
  { name: "Parser", detail: "Drain3, 391 templates", health: "healthy" },
  { name: "Models", detail: "4 detectors", health: "healthy" },
  { name: "Explanation", detail: "SHAP, top events", health: "healthy" },
  { name: "Dashboard", detail: "this page", health: "healthy" },
]

// Real results from our experiments (notebooks 06–12)
const modelResults: ModelResult[] = [
  {
    name: "PCA",
    kind: "Statistical",
    description: "Flags windows whose event counts can't be rebuilt from normal patterns.",
    scores: { HDFS: { precision: 0.989, recall: 0.752, f1: 0.854 }, BGL: { precision: 0.187, recall: 0.955, f1: 0.312 } },
  },
  {
    name: "Isolation Forest",
    kind: "Unsupervised ML",
    description: "Isolates unusual windows with random splits, trained on normal data only.",
    scores: { HDFS: { precision: 0.059, recall: 0.045, f1: 0.051 }, BGL: { precision: 0.034, recall: 0.043, f1: 0.038 } },
  },
  {
    name: "Random Forest",
    kind: "Supervised ML",
    description: "Learns from labelled normal and anomalous windows.",
    scores: { HDFS: { precision: 1.0, recall: 0.998, f1: 0.999 }, BGL: { precision: 0.993, recall: 0.537, f1: 0.697 } },
  },
  {
    name: "LSTM",
    kind: "Deep learning",
    description: "Predicts the next event from the previous 10 (DeepLog) and flags surprises.",
    scores: { HDFS: { precision: 0.889, recall: 0.506, f1: 0.645 }, BGL: { precision: 0.172, recall: 0.993, f1: 0.294 } },
  },
]

export async function getKpis() {
  await delay()
  return kpis
}

export async function getAlerts() {
  await delay()
  return alerts
}

export async function getServices() {
  await delay()
  return services
}

export async function getPipeline() {
  await delay()
  return pipeline
}

export async function getModelResults() {
  await delay()
  return modelResults
}

// Simulated live feeds below run in the browser, since they depend on the clock

function pad(n: number) {
  return String(n).padStart(2, "0")
}

function clock(date: Date, seconds = false) {
  const hm = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  return seconds ? `${hm}:${pad(date.getSeconds())}` : hm
}

function pick<T>(items: T[]) {
  return items[Math.floor(Math.random() * items.length)]
}

const BASE_RATE = Object.fromEntries(services.map((s) => [s.name, s.logsPerMinute])) as Record<ServiceName, number>

function simulatePoint(date: Date): VolumePoint {
  const point = { time: clock(date) } as VolumePoint
  for (const service of SERVICE_NAMES) {
    point[service] = Math.round(BASE_RATE[service] * (0.85 + Math.random() * 0.3))
  }
  return point
}

// Log volume: re-estimates the current minute, starts a new point when the minute changes
export function nextLogVolume(points: VolumePoint[], now: Date, minutes = 30): VolumePoint[] {
  if (points.length === 0) {
    return Array.from({ length: minutes }, (_, i) => simulatePoint(new Date(now.getTime() - (minutes - 1 - i) * 60_000)))
  }
  const current = simulatePoint(now)
  const last = points[points.length - 1]
  return last.time === current.time ? [...points.slice(0, -1), current] : [...points, current].slice(-minutes)
}

type LogTemplate = [ServiceName, LogLevel, string, string?]

const LOG_TEMPLATES: LogTemplate[] = [
  ["nginx", "INFO", '172.20.0.1 - - "GET /api/items HTTP/1.1" 200 209'],
  ["nginx", "INFO", '172.20.0.1 - - "POST /api/items HTTP/1.1" 201 67'],
  ["nginx", "INFO", '172.20.0.1 - - "GET / HTTP/1.1" 200 615'],
  ["nginx", "WARN", '172.20.0.1 - - "GET /api/admin HTTP/1.1" 404 153'],
  ["app", "INFO", "172.20.0.1 GET /items 200 6ms"],
  ["app", "INFO", "172.20.0.1 POST /items 201 9ms"],
  ["app", "ERROR", "POST /items database error: connection timeout after 5000ms"],
  ["postgres", "INFO", "checkpoint starting: time"],
  ["postgres", "INFO", "connection authorized: user=loguser database=logs"],
  ["postgres", "WARN", "could not receive data from client: Connection reset by peer"],
  ["ssh", "INFO", "Accepted password for testuser from 172.20.0.1 port 48746 ssh2"],
  ["ssh", "WARN", "Failed password for root from 45.13.22.9 port 51022 ssh2", "a1"],
  ["ssh", "WARN", "Invalid user admin from 45.13.22.9 port 51023", "a1"],
]

// Weights: mostly web traffic, now and then brute-force lines that belong to alert a1
const WEIGHTS = [30, 8, 4, 1, 26, 7, 1, 2, 4, 1, 2, 6, 3]
const WEIGHTED = LOG_TEMPLATES.flatMap((template, i) => Array(WEIGHTS[i]).fill(template) as LogTemplate[])

function simulateLine(id: number, date: Date): LogLine {
  const [service, level, message, alertId] = pick(WEIGHTED)
  return { id, time: clock(date, true), service, level, message, alertId }
}

// Live log stream: adds a few lines per tick, keeps the newest `max` (newest first)
export function nextLogLines(lines: LogLine[], now: Date, max = 200): LogLine[] {
  const seeding = lines.length === 0
  const startId = seeding ? 0 : lines[0].id + 1
  const count = seeding ? 20 : 1 + Math.floor(Math.random() * 3)
  // the first batch is spread over the last 20 seconds; later lines all belong to "now"
  const fresh = Array.from({ length: count }, (_, i) =>
    simulateLine(startId + i, seeding ? new Date(now.getTime() - (count - 1 - i) * 1000) : now)
  )
  return [...fresh.reverse(), ...lines].slice(0, max)
}

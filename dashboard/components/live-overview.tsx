"use client"

import { Activity, Bell, Server, Timer } from "lucide-react"

import { AlertsTable } from "@/components/alerts-table"
import { ConnectionNotice } from "@/components/connection-notice"
import { KpiCard } from "@/components/kpi-card"
import { LogVolumeChart } from "@/components/log-volume-chart"
import { ServiceStatusList } from "@/components/service-status-list"
import { NO_DATA } from "@/components/no-data"
import { useDetectorFeed, useSystemStatus } from "@/lib/detector"

// Overview: everything comes from the detection service (alerts and stats over SSE, services and log volume every 5 s)
export function LiveOverview() {
  const { connection, alerts, stats } = useDetectorFeed()
  const { services, volume } = useSystemStatus()
  const critical = alerts.filter((a) => a.level === "Alert").length
  const known = services?.filter((s) => s.health != null) ?? []
  const healthy = known.filter((s) => s.health === "healthy").length
  const latency = stats?.avg_detection_latency_ms

  return (
    <>
      <ConnectionNotice connection={connection} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Logs per minute"
          value={stats ? stats.logs_per_minute.toLocaleString("en-US") : NO_DATA}
          hint="All sources, last 60 s"
          icon={Activity}
        />
        <KpiCard label="Active alerts" value={stats ? String(alerts.length) : NO_DATA} hint={`${critical} alerts, ${alerts.length - critical} new templates`} icon={Bell} />
        <KpiCard
          label="Avg detection latency"
          value={latency != null ? `${latency.toLocaleString("en-US")} ms` : NO_DATA}
          hint="Last line in stream to alert"
          icon={Timer}
        />
        <KpiCard
          label="Services healthy"
          value={known.length ? `${healthy}/${known.length}` : NO_DATA}
          hint="Docker containers (docker compose ps)"
          icon={Server}
        />
      </div>
      <LogVolumeChart points={volume} />
      <div className="grid gap-4 lg:grid-cols-3">
        {/* min-w-0 lets the table scroll inside its card on small screens */}
        <div className="min-w-0 lg:col-span-2">
          <AlertsTable title="Recent alerts" alerts={alerts.slice(0, 5)} />
        </div>
        <ServiceStatusList services={services} />
      </div>
    </>
  )
}

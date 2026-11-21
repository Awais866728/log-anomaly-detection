"use client"

import { Activity, Bell, Server, Timer } from "lucide-react"

import { AlertsTable } from "@/components/alerts-table"
import { ConnectionNotice } from "@/components/connection-notice"
import { KpiCard } from "@/components/kpi-card"
import { LogVolumeChart } from "@/components/log-volume-chart"
import { ServiceStatusList } from "@/components/service-status-list"
import { useDetectorFeed } from "@/lib/detector"
import type { ServiceStatus } from "@/lib/types"

// Overview: KPIs and recent alerts from the detection service; log volume and service health are still sample data
export function LiveOverview({ services }: { services: ServiceStatus[] }) {
  const { connection, alerts, stats } = useDetectorFeed()
  const critical = alerts.filter((a) => a.level === "Alert").length
  const healthy = services.filter((s) => s.health === "healthy").length
  const latency = stats?.avg_detection_latency_ms

  return (
    <>
      <ConnectionNotice connection={connection} />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Logs per minute"
          value={stats ? stats.logs_per_minute.toLocaleString("en-US") : "-"}
          hint="All sources, last 60 s"
          icon={Activity}
        />
        <KpiCard label="Active alerts" value={String(alerts.length)} hint={`${critical} alerts, ${alerts.length - critical} new templates`} icon={Bell} />
        <KpiCard
          label="Avg detection latency"
          value={latency != null ? `${latency.toLocaleString("en-US")} ms` : "-"}
          hint="Last line in stream to alert"
          icon={Timer}
        />
        <KpiCard label="Services healthy" value={`${healthy}/${services.length}`} hint="Docker containers (sample data)" icon={Server} />
      </div>
      <LogVolumeChart />
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

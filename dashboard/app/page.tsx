import { Activity, Bell, Server, Timer } from "lucide-react"

import { KpiCard } from "@/components/kpi-card"
import { LogVolumeChart } from "@/components/log-volume-chart"
import { RecentAlertsTable } from "@/components/recent-alerts-table"
import { ServiceStatusList } from "@/components/service-status-list"
import { kpis, recentAlerts, serviceStatuses } from "@/lib/mock-data"

export default function OverviewPage() {
  const healthy = serviceStatuses.filter((s) => s.health === "healthy").length
  const critical = recentAlerts.filter((a) => a.severity === "critical").length

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Logs per minute" value={kpis.logsPerMinute.toLocaleString("en-US")} hint="All services" icon={Activity} />
        <KpiCard label="Active alerts" value={String(recentAlerts.length)} hint={`${critical} critical`} icon={Bell} />
        <KpiCard label="Avg detection latency" value={`${kpis.avgDetectionLatencyMs} ms`} hint="Log line to alert" icon={Timer} />
        <KpiCard label="Services healthy" value={`${healthy}/${serviceStatuses.length}`} hint="Docker containers" icon={Server} />
      </div>
      <LogVolumeChart />
      <div className="grid gap-4 lg:grid-cols-3">
        {/* min-w-0 lets the table scroll inside its card on small screens */}
        <div className="min-w-0 lg:col-span-2">
          <RecentAlertsTable alerts={recentAlerts} />
        </div>
        <ServiceStatusList services={serviceStatuses} />
      </div>
    </>
  )
}

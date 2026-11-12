import { Activity, Bell, Server, Timer } from "lucide-react"

import { AlertsTable } from "@/components/alerts-table"
import { KpiCard } from "@/components/kpi-card"
import { LogVolumeChart } from "@/components/log-volume-chart"
import { ServiceStatusList } from "@/components/service-status-list"
import { getAlerts, getKpis, getServices } from "@/lib/mock-data"

export default async function OverviewPage() {
  const [kpis, alerts, services] = await Promise.all([getKpis(), getAlerts(), getServices()])
  const openAlerts = alerts.filter((a) => a.status === "open")
  const logsPerMinute = services.reduce((sum, s) => sum + s.logsPerMinute, 0)
  const healthy = services.filter((s) => s.health === "healthy").length

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Logs per minute" value={logsPerMinute.toLocaleString("en-US")} hint="All services" icon={Activity} />
        <KpiCard
          label="Active alerts"
          value={String(openAlerts.length)}
          hint={`${openAlerts.filter((a) => a.severity === "critical").length} critical`}
          icon={Bell}
        />
        <KpiCard label="Avg detection latency" value={`${kpis.avgDetectionLatencyMs} ms`} hint="Log line to alert" icon={Timer} />
        <KpiCard label="Services healthy" value={`${healthy}/${services.length}`} hint="Docker containers" icon={Server} />
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

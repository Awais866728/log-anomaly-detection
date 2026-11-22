import { NoData } from "@/components/no-data"
import { Sparkline } from "@/components/sparkline"
import { HEALTH_TONE, StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { ServiceStatus } from "@/lib/types"

function Field({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="truncate font-medium tabular-nums">{value == null ? <NoData /> : value}</dd>
    </div>
  )
}

export function ServiceCard({ service }: { service: ServiceStatus }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          {service.name}
          {service.health ? <StatusBadge tone={HEALTH_TONE[service.health]} label={service.health} /> : <NoData />}
        </CardTitle>
        <CardDescription className="truncate font-mono text-xs">{service.container ?? "container not found"}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <Field label="Uptime" value={service.uptime ?? (service.state && service.state !== "running" ? service.state : null)} />
          <Field label="Logs per minute" value={service.logsPerMinute?.toLocaleString("en-US") ?? null} />
          <Field label="Last line received" value={service.lastLineReceived} />
          <Field label="Alerts / new templates" value={`${service.alerts} / ${service.newTemplates}`} />
        </dl>
        <div>
          <p className="text-xs text-muted-foreground">Lines per minute, last {service.sparkline.length || 12} full minutes</p>
          {service.sparkline.length >= 2 ? <Sparkline values={service.sparkline} /> : <NoData className="text-xs" />}
        </div>
        <p className="text-xs text-muted-foreground">
          Models: {service.models.length ? service.models.join(", ") : "no pack loaded"}
        </p>
      </CardContent>
    </Card>
  )
}

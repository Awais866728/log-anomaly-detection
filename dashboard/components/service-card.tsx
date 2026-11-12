import { Sparkline } from "@/components/sparkline"
import { HEALTH_TONE, StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { ServiceStatus } from "@/lib/types"

export function ServiceCard({ service }: { service: ServiceStatus }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          {service.name}
          <StatusBadge tone={HEALTH_TONE[service.health]} label={service.health} />
        </CardTitle>
        <CardDescription className="truncate font-mono text-xs">{service.container}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid grid-cols-2 gap-2 text-sm">
          <div>
            <dt className="text-xs text-muted-foreground">Uptime</dt>
            <dd className="font-medium tabular-nums">{service.uptime}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Logs per minute</dt>
            <dd className="font-medium tabular-nums">{service.logsPerMinute}</dd>
          </div>
        </dl>
        <Sparkline values={service.sparkline} />
      </CardContent>
    </Card>
  )
}

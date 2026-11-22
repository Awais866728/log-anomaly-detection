import { NoData } from "@/components/no-data"
import { HEALTH_TONE, StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ServiceStatus } from "@/lib/types"

export function ServiceStatusList({ services }: { services: ServiceStatus[] | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Services</CardTitle>
      </CardHeader>
      <CardContent>
        {services ? (
          <ul className="divide-y">
            {services.map((service) => (
              <li key={service.name} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="font-medium">{service.name}</p>
                  <p className="truncate font-mono text-xs text-muted-foreground">{service.status ?? service.container ?? "container not found"}</p>
                </div>
                {service.health ? <StatusBadge tone={HEALTH_TONE[service.health]} label={service.health} /> : <NoData />}
              </li>
            ))}
          </ul>
        ) : (
          <NoData />
        )}
      </CardContent>
    </Card>
  )
}

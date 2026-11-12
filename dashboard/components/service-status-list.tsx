import { StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ServiceStatus } from "@/lib/types"

export function ServiceStatusList({ services }: { services: ServiceStatus[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Services</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="divide-y">
          {services.map((service) => (
            <li key={service.name} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0">
                <p className="font-medium">{service.name}</p>
                <p className="truncate font-mono text-xs text-muted-foreground">{service.container}</p>
              </div>
              <StatusBadge tone={service.health === "healthy" ? "healthy" : "critical"} label={service.health} />
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

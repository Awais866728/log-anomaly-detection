"use client"

import { ConnectionNotice } from "@/components/connection-notice"
import { NoData } from "@/components/no-data"
import { PipelineFlow } from "@/components/pipeline-flow"
import { ServiceCard } from "@/components/service-card"
import { Card, CardContent } from "@/components/ui/card"
import { useSystemStatus } from "@/lib/detector"

// Services: container state from docker compose ps and log counts, both read by the detection service
export function LiveServices() {
  const { connection, services, pipeline, dockerAvailable } = useSystemStatus()
  // the last step is this page itself: healthy while the detection service answers
  const steps = pipeline && [
    ...pipeline,
    { name: "Dashboard", detail: `this page, ${connection}`, health: connection === "live" ? ("healthy" as const) : ("down" as const) },
  ]

  return (
    <>
      <ConnectionNotice connection={connection} />
      {dockerAvailable === false && (
        <p className="rounded-md border px-3 py-2 text-sm text-muted-foreground">
          The detection service could not run <code className="font-mono text-xs">docker compose ps</code>, so container health and
          uptime are not known.
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {services ? (
          services.map((service) => <ServiceCard key={service.name} service={service} />)
        ) : (
          <Card className="sm:col-span-2 xl:col-span-4">
            <CardContent>
              <NoData />
            </CardContent>
          </Card>
        )}
      </div>
      <PipelineFlow steps={steps} />
    </>
  )
}

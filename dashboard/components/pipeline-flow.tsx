import { Fragment } from "react"
import { ChevronRight } from "lucide-react"

import { HEALTH_TONE, StatusDot } from "@/components/status-badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { PipelineStep } from "@/lib/types"

export function PipelineFlow({ steps }: { steps: PipelineStep[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>System pipeline</CardTitle>
        <CardDescription>How a log line travels from a server to this dashboard</CardDescription>
      </CardHeader>
      <CardContent>
        {/* vertical on small screens, a single row from xl */}
        <ol className="flex flex-col items-stretch gap-2 xl:flex-row">
          {steps.map((step, i) => (
            <Fragment key={step.name}>
              {i > 0 && (
                <li className="self-center text-muted-foreground" aria-hidden>
                  <ChevronRight className="size-4 max-xl:rotate-90" />
                </li>
              )}
              <li className="flex-1 rounded-md border px-3 py-2">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <StatusDot tone={HEALTH_TONE[step.health]} />
                  {step.name}
                </p>
                <p className="text-xs text-muted-foreground">{step.detail}</p>
              </li>
            </Fragment>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

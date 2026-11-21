"use client"

import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { chartConfigFor, SeriesLegend, type Series } from "@/components/chart-series"
import { StatusBadge } from "@/components/status-badge"
import { ChartContainer, ChartLegend, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import type { Alert } from "@/lib/types"

const SERIES: Series[] = [
  { key: "count", label: "In this window", style: 0 },
  { key: "normalCount", label: "Normal", style: 3 },
]
const chartConfig = chartConfigFor(SERIES)

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h3 className="text-sm font-medium">{title}</h3>
      {children}
    </section>
  )
}

function formatTime(iso?: string | null) {
  return iso ? new Date(iso).toISOString().replace("T", " ").replace("Z", " UTC") : "-"
}

// Label / value pairs for the summary grid; detection-service fields only when present
function summaryItems(alert: Alert): [string, string][] {
  const items: [string, string][] = [
    ["Service", alert.source],
    ["Time window", alert.window],
    ["Model", alert.setting ? `${alert.model} (${alert.setting})` : alert.model],
    [alert.model === "Random Forest" ? "Anomaly probability" : "Anomaly score (share of normal windows below)", `${Math.round(alert.probability * 100)}%`],
  ]
  if (alert.alertTime) {
    items.push(
      ["Last log line", formatTime(alert.lastLineTime)],
      ["Alert produced", formatTime(alert.alertTime)],
      ["Latency (stream to alert)", `${alert.latencyMs?.toLocaleString("en-US")} ms`],
      ["Flagged by", alert.flaggedBy?.length ? alert.flaggedBy.join(", ") : "unseen-event rule only"]
    )
  }
  if (alert.trueLabel != null) items.push(["True label (replay)", alert.trueLabel ? "anomaly" : "normal"])
  return items
}

export function AlertSheet({ alert, onClose }: { alert: Alert | null; onClose: () => void }) {
  return (
    <Sheet open={alert !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto data-[side=right]:sm:max-w-xl">
        {alert && (
          <>
            <SheetHeader className="pr-10">
              <SheetTitle>{alert.reason}</SheetTitle>
              <SheetDescription className="flex gap-2 pt-1">
                <StatusBadge tone={alert.severity} label={alert.level ?? alert.severity} />
                <StatusBadge tone={alert.status === "open" ? "neutral" : "healthy"} label={alert.status} />
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-6 px-4 pb-6">
              <Section title="Summary">
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  {summaryItems(alert).map(([label, value]) => (
                    <div key={label}>
                      <dt className="text-xs text-muted-foreground">{label}</dt>
                      <dd className="font-medium">{value}</dd>
                    </div>
                  ))}
                </dl>
              </Section>

              <Section title="Why this alert">
                <ChartContainer config={chartConfig} className="aspect-auto h-56 w-full">
                  <BarChart data={alert.events.map((e, i) => ({ ...e, rank: `#${i + 1}` }))} layout="vertical" margin={{ left: 0, right: 12 }}>
                    <CartesianGrid horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tickLine={false} axisLine={false} />
                    <YAxis type="category" dataKey="rank" tickLine={false} axisLine={false} width={28} />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <ChartLegend content={<SeriesLegend series={SERIES} shape="box" />} />
                    {SERIES.map((s) => (
                      <Bar key={s.key} dataKey={s.key} fill={`var(--color-${s.key})`} radius={2} isAnimationActive={false} />
                    ))}
                  </BarChart>
                </ChartContainer>
                <ol className="space-y-3 text-sm">
                  {alert.events.map((event, i) => (
                    <li key={event.label} className="flex gap-2">
                      <span className="text-muted-foreground tabular-nums">#{i + 1}</span>
                      <div className="min-w-0 space-y-0.5">
                        <p>
                          <span className="font-medium">{event.label}</span>
                          {event.unseen && <span className="text-warning"> (new template)</span>}{" "}
                          {event.missing ? (
                            <strong>expected but missing</strong>
                          ) : (
                            <>
                              appeared <strong className="tabular-nums">{event.count.toLocaleString("en-US")}</strong>{" "}
                              {event.count === 1 ? "time" : "times"}
                            </>
                          )}{" "}
                          <span className="text-muted-foreground">
                            (normal: about {event.normalCount.toLocaleString("en-US", { maximumFractionDigits: 1 })}
                            {event.shap != null && `, SHAP ${event.shap >= 0 ? "+" : ""}${event.shap.toFixed(3)}`})
                          </span>
                        </p>
                        <code className="block font-mono text-xs break-words text-muted-foreground">{event.template}</code>
                      </div>
                    </li>
                  ))}
                </ol>
              </Section>

              <Section title="Raw log lines">
                {/* one log line per row; long lines scroll sideways inside the box */}
                <pre className="max-h-64 overflow-auto rounded-md border bg-muted/50 p-3 font-mono text-xs leading-relaxed whitespace-pre">
                  {alert.logLines.join("\n")}
                </pre>
              </Section>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

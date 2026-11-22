"use client"

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import { chartConfigFor, dashFor, SeriesLegend, type Series } from "@/components/chart-series"
import { NoData } from "@/components/no-data"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { SERVICE_NAMES, type VolumePoint } from "@/lib/types"

const SERIES: Series[] = SERVICE_NAMES.map((name, i) => ({ key: name, label: name, style: i }))
const chartConfig = chartConfigFor(SERIES)

// Live log lines per service and full minute, counted by the detection service (last 30 minutes since it started)
export function LogVolumeChart({ points }: { points: VolumePoint[] | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Log volume</CardTitle>
        <CardDescription>Log lines per minute by service, full minutes only, last 30 minutes</CardDescription>
      </CardHeader>
      <CardContent>
        {points && points.length > 0 ? (
          <ChartContainer config={chartConfig} className="aspect-auto h-72 w-full">
            <LineChart data={points} margin={{ left: 4, right: 12 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="time" tickLine={false} axisLine={false} tickMargin={8} minTickGap={32} />
              <YAxis tickLine={false} axisLine={false} width={40} />
              <ChartTooltip content={<ChartTooltipContent indicator="line" />} />
              <ChartLegend content={<SeriesLegend series={SERIES} />} />
              {SERIES.map((s) => (
                <Line
                  key={s.key}
                  dataKey={s.key}
                  type="monotone"
                  stroke={`var(--color-${s.key})`}
                  strokeWidth={2}
                  strokeDasharray={dashFor(s)}
                  dot={points.length === 1}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ChartContainer>
        ) : (
          <div className="flex h-72 items-center justify-center">
            <NoData />
          </div>
        )}
      </CardContent>
    </Card>
  )
}

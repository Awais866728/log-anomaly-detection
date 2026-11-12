"use client"

import { useEffect, useState } from "react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import { chartConfigFor, dashFor, SeriesLegend, type Series } from "@/components/chart-series"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { nextLogVolume } from "@/lib/mock-data"
import { SERVICE_NAMES, type VolumePoint } from "@/lib/types"

const UPDATE_MS = 3000
const SERIES: Series[] = SERVICE_NAMES.map((name, i) => ({ key: name, label: name, style: i }))
const chartConfig = chartConfigFor(SERIES)

export function LogVolumeChart() {
  const [points, setPoints] = useState<VolumePoint[]>([])

  useEffect(() => {
    // Data depends on the clock, so it is only generated in the browser
    const tick = () => setPoints((prev) => nextLogVolume(prev, new Date()))
    const first = setTimeout(tick, 0)
    const timer = setInterval(tick, UPDATE_MS)
    return () => {
      clearTimeout(first)
      clearInterval(timer)
    }
  }, [])

  return (
    <Card>
      <CardHeader>
        <CardTitle>Log volume</CardTitle>
        <CardDescription>Log lines per minute by service, last 30 minutes</CardDescription>
      </CardHeader>
      <CardContent>
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
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

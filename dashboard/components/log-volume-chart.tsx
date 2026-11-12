"use client"

import { useEffect, useState } from "react"
import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart"
import { nextLogVolume } from "@/lib/mock-data"
import { SERVICE_NAMES, type ServiceName, type VolumePoint } from "@/lib/types"

const UPDATE_MS = 3000

// Neutral greys; lines are told apart by shade and dash pattern
const chartConfig = {
  nginx: { label: "nginx", theme: { light: "oklch(0.25 0 0)", dark: "oklch(0.95 0 0)" } },
  app: { label: "app", theme: { light: "oklch(0.45 0 0)", dark: "oklch(0.78 0 0)" } },
  postgres: { label: "postgres", theme: { light: "oklch(0.6 0 0)", dark: "oklch(0.62 0 0)" } },
  ssh: { label: "ssh", theme: { light: "oklch(0.72 0 0)", dark: "oklch(0.5 0 0)" } },
} satisfies ChartConfig

const DASHES: Record<ServiceName, string | undefined> = {
  nginx: undefined,
  app: "6 3",
  postgres: "2 3",
  ssh: "8 3 2 3",
}

// Legend with a sample of each line, so the dash patterns are visible (colour squares can't show them)
function DashLegend() {
  return (
    <ul className="flex flex-wrap justify-center gap-x-5 gap-y-1 pt-3 text-xs text-muted-foreground">
      {SERVICE_NAMES.map((service) => (
        <li key={service} className="flex items-center gap-1.5">
          <svg width="20" height="6" aria-hidden>
            <line x1="0" y1="3" x2="20" y2="3" stroke={`var(--color-${service})`} strokeWidth="2" strokeDasharray={DASHES[service]} />
          </svg>
          {chartConfig[service].label}
        </li>
      ))}
    </ul>
  )
}

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
            <ChartLegend content={<DashLegend />} />
            {SERVICE_NAMES.map((service) => (
              <Line
                key={service}
                dataKey={service}
                type="monotone"
                stroke={`var(--color-${service})`}
                strokeWidth={2}
                strokeDasharray={DASHES[service]}
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

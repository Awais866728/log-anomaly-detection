"use client"

import { Line, LineChart, YAxis } from "recharts"

import { chartConfigFor } from "@/components/chart-series"
import { ChartContainer } from "@/components/ui/chart"

const chartConfig = chartConfigFor([{ key: "value", label: "Logs per minute", style: 0 }])

export function Sparkline({ values }: { values: number[] }) {
  return (
    <ChartContainer config={chartConfig} className="aspect-auto h-10 w-full">
      <LineChart data={values.map((value, i) => ({ i, value }))} margin={{ top: 4, bottom: 4, left: 0, right: 0 }}>
        {/* scale to the data range, so small changes are visible */}
        <YAxis hide domain={["dataMin", "dataMax"]} />
        <Line dataKey="value" type="monotone" stroke="var(--color-value)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ChartContainer>
  )
}

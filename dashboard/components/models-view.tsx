"use client"

import { useState } from "react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { chartConfigFor, SeriesLegend, type Series } from "@/components/chart-series"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DATASETS, type Dataset, type ModelResult } from "@/lib/types"
import { cn } from "@/lib/utils"

const SERIES: Series[] = DATASETS.map((name, i) => ({ key: name, label: `${name} F1`, style: i * 2 }))
const chartConfig = chartConfigFor(SERIES)
const METRICS = ["precision", "recall", "f1"] as const

export function ModelsView({ models }: { models: ModelResult[] }) {
  const [dataset, setDataset] = useState<Dataset>("HDFS")
  const bestF1 = Math.max(...models.map((m) => m.scores[dataset].f1))

  return (
    <>
      <Tabs value={dataset} onValueChange={(value) => setDataset(value as Dataset)}>
        <TabsList>
          {DATASETS.map((d) => (
            <TabsTrigger key={d} value={d}>
              {d}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <div className="grid gap-4 xl:grid-cols-5">
        <Card className="min-w-0 xl:col-span-3">
          <CardHeader>
            <CardTitle>Results on {dataset}</CardTitle>
            <CardDescription>Test set, last 30% of the data in time order</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead className="text-right">Precision</TableHead>
                  <TableHead className="text-right">Recall</TableHead>
                  <TableHead className="text-right">F1</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {models.map((model) => (
                  <TableRow key={model.name}>
                    <TableCell className="min-w-64 whitespace-normal">
                      <p className="font-medium">{model.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {model.kind}: {model.description}
                      </p>
                    </TableCell>
                    {METRICS.map((metric) => (
                      <TableCell
                        key={metric}
                        className={cn("text-right tabular-nums", metric === "f1" && model.scores[dataset].f1 === bestF1 && "font-semibold")}
                      >
                        {model.scores[dataset][metric].toFixed(3)}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>F1 by model and dataset</CardTitle>
            <CardDescription>Higher is better; 1.0 is perfect</CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={chartConfig} className="aspect-auto h-72 w-full">
              <BarChart
                data={models.map((m) => ({ name: m.name, ...Object.fromEntries(DATASETS.map((d) => [d, m.scores[d].f1])) }))}
                margin={{ left: 0, right: 8 }}
              >
                <CartesianGrid vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} interval={0} fontSize={11} />
                <YAxis domain={[0, 1]} tickLine={false} axisLine={false} width={32} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <ChartLegend content={<SeriesLegend series={SERIES} shape="box" />} />
                {SERIES.map((s) => (
                  <Bar key={s.key} dataKey={s.key} fill={`var(--color-${s.key})`} radius={2} isAnimationActive={false} />
                ))}
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>
    </>
  )
}

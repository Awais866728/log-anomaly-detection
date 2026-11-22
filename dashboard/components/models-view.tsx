"use client"

import { useState } from "react"
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { chartConfigFor, SeriesLegend, type Series } from "@/components/chart-series"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ChartContainer, ChartLegend, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DATASETS, UNLABELLED_DATASETS, type Dataset, type ModelResult, type UnlabelledDataset } from "@/lib/types"
import { cn } from "@/lib/utils"

const F1_SERIES: Series[] = DATASETS.map((name, i) => ({ key: name, label: `${name} F1`, style: i * 2 }))
const f1Config = chartConfigFor(F1_SERIES)
// flag rate on an unlabelled dataset, with the setting chosen on each labelled dataset
const FLAG_SERIES: Series[] = DATASETS.map((name, i) => ({ key: name, label: `${name} setting`, style: i * 2 }))
const flagConfig = chartConfigFor(FLAG_SERIES)
const METRICS = ["precision", "recall", "f1"] as const
const TABS = [...DATASETS, ...UNLABELLED_DATASETS]

function isLabelled(d: string): d is Dataset {
  return (DATASETS as readonly string[]).includes(d)
}

function ModelName({ model, setting }: { model: ModelResult; setting?: string }) {
  return (
    <TableCell className="min-w-64 whitespace-normal">
      <p className="font-medium">{model.name}</p>
      <p className="text-xs text-muted-foreground">
        {model.kind}: {model.description}
      </p>
      {setting && <p className="text-xs text-muted-foreground">Setting: {setting}</p>}
    </TableCell>
  )
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function LabelledResults({ models, dataset }: { models: ModelResult[]; dataset: Dataset }) {
  const bestF1 = Math.max(...models.map((m) => m.scores[dataset].f1))
  return (
    <>
      <Card className="min-w-0 xl:col-span-3">
        <CardHeader>
          <CardTitle>Results on {dataset}</CardTitle>
          <CardDescription>Test set (last 30% in time order), settings chosen on a validation part (docs/cross_system_results.csv)</CardDescription>
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
                  <ModelName model={model} setting={model.settings?.[dataset]} />
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
          <ChartContainer config={f1Config} className="aspect-auto h-72 w-full">
            <BarChart
              data={models.map((m) => ({ name: m.name, ...Object.fromEntries(DATASETS.map((d) => [d, m.scores[d].f1])) }))}
              margin={{ left: 0, right: 8 }}
            >
              <CartesianGrid vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} interval={0} fontSize={11} />
              <YAxis domain={[0, 1]} tickLine={false} axisLine={false} width={32} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<SeriesLegend series={F1_SERIES} shape="box" />} />
              {F1_SERIES.map((s) => (
                <Bar key={s.key} dataKey={s.key} fill={`var(--color-${s.key})`} radius={2} isAnimationActive={false} />
              ))}
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </>
  )
}

function UnlabelledResults({ models, dataset }: { models: ModelResult[]; dataset: UnlabelledDataset }) {
  // Random Forest needs labels for training, so it has no rows here
  const rows = models.filter((m) => m.unlabelled[dataset].length > 0)
  const rate = (m: ModelResult, chosenOn: Dataset) => m.unlabelled[dataset].find((r) => r.chosen_on === chosenOn)
  return (
    <>
      <Card className="min-w-0 xl:col-span-3">
        <CardHeader>
          <CardTitle>Flag rate on {dataset}</CardTitle>
          <CardDescription>
            {dataset} has no anomaly labels, so precision, recall and F1 can&apos;t be computed: this is only the share of windows each
            model flags, with the setting chosen on HDFS and on BGL.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Model</TableHead>
                {DATASETS.map((d) => (
                  <TableHead key={d} className="text-right">
                    {d} setting
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((model) => (
                <TableRow key={model.name}>
                  <ModelName model={model} />
                  {DATASETS.map((d) => {
                    const r = rate(model, d)
                    return (
                      <TableCell key={d} className="text-right whitespace-normal">
                        {r ? (
                          <>
                            <p className="tabular-nums">{percent(r.flag_rate)}</p>
                            <p className="text-xs text-muted-foreground">{r.setting}</p>
                          </>
                        ) : (
                          <span className="text-muted-foreground">not run</span>
                        )}
                      </TableCell>
                    )
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {rows.length < models.length && (
            <p className="pt-3 text-xs text-muted-foreground">
              Not run on {dataset}: {models.filter((m) => !rows.includes(m)).map((m) => m.name).join(", ")} (supervised, needs labels).
            </p>
          )}
        </CardContent>
      </Card>
      <Card className="xl:col-span-2">
        <CardHeader>
          <CardTitle>Share of windows flagged</CardTitle>
          <CardDescription>Lower means fewer alerts; without labels it doesn&apos;t say which are correct</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={flagConfig} className="aspect-auto h-72 w-full">
            <BarChart
              data={rows.map((m) => ({ name: m.name, ...Object.fromEntries(DATASETS.map((d) => [d, rate(m, d)?.flag_rate ?? null])) }))}
              margin={{ left: 0, right: 8 }}
            >
              <CartesianGrid vertical={false} />
              <XAxis dataKey="name" tickLine={false} axisLine={false} tickMargin={8} interval={0} fontSize={11} />
              <YAxis tickLine={false} axisLine={false} width={40} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<SeriesLegend series={FLAG_SERIES} shape="box" />} />
              {FLAG_SERIES.map((s) => (
                <Bar key={s.key} dataKey={s.key} fill={`var(--color-${s.key})`} radius={2} isAnimationActive={false} />
              ))}
            </BarChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </>
  )
}

export function ModelsView({ models }: { models: ModelResult[] }) {
  const [dataset, setDataset] = useState<(typeof TABS)[number]>("HDFS")

  return (
    <>
      <Tabs value={dataset} onValueChange={(value) => setDataset(value as (typeof TABS)[number])}>
        <TabsList>
          {TABS.map((d) => (
            <TabsTrigger key={d} value={d}>
              {d}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <div className="grid gap-4 xl:grid-cols-5">
        {isLabelled(dataset) ? <LabelledResults models={models} dataset={dataset} /> : <UnlabelledResults models={models} dataset={dataset} />}
      </div>
    </>
  )
}

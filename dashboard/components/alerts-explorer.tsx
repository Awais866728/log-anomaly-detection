"use client"

import { useState } from "react"

import { AlertSheet } from "@/components/alert-sheet"
import { AlertsTable } from "@/components/alerts-table"
import { ALL, FilterSelect } from "@/components/filter-select"
import { ALL_SOURCES, type Alert } from "@/lib/types"

export function AlertsExplorer({ alerts }: { alerts: Alert[] }) {
  const [severity, setSeverity] = useState(ALL)
  const [source, setSource] = useState(ALL)
  const [selected, setSelected] = useState<Alert | null>(null)

  // every source, also those without alerts yet (e.g. a replay that hasn't been started)
  const labels = Object.fromEntries(ALL_SOURCES.map((s) => [s, `${s} (${alerts.filter((a) => a.source === s).length})`]))
  const visible = alerts.filter((a) => (severity === ALL || a.severity === severity) && (source === ALL || a.source === source))

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <FilterSelect label="Severity" allLabel="All severities" value={severity} options={["critical", "warning"]} onChange={setSeverity} />
        <FilterSelect label="Service" allLabel="All services" value={source} options={ALL_SOURCES} labels={labels} onChange={setSource} />
      </div>
      <AlertsTable title={`${visible.length} alerts`} alerts={visible} showStatus onSelect={setSelected} />
      <AlertSheet alert={selected} onClose={() => setSelected(null)} />
    </>
  )
}

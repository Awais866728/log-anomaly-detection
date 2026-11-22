"use client"

import { useState } from "react"
import { Pause, Play, Search } from "lucide-react"

import { ConnectionNotice } from "@/components/connection-notice"
import { ALL, FilterSelect } from "@/components/filter-select"
import { StatusBadge, type Tone } from "@/components/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { useDetectorFeed } from "@/lib/detector"
import { ALL_SOURCES, type LogLevel } from "@/lib/types"
import { cn } from "@/lib/utils"

const LEVELS: LogLevel[] = ["INFO", "WARN", "ERROR"]
const LEVEL_TONE: Record<LogLevel, Tone> = { INFO: "neutral", WARN: "warning", ERROR: "critical" }
const SOURCES = [...ALL_SOURCES]
const MAX_SHOWN = 200

export function LiveLogStream() {
  const [paused, setPaused] = useState(false)
  const [service, setService] = useState(ALL)
  const [level, setLevel] = useState(ALL)
  const [search, setSearch] = useState("")
  const { connection, lines, alerts, lineAlerts } = useDetectorFeed({ paused })
  const alertReasons = Object.fromEntries(alerts.map((a) => [a.id, a.reason]))

  const query = search.trim().toLowerCase()
  const matching = lines.filter(
    (l) =>
      (service === ALL || l.service === service) &&
      (level === ALL || l.level === level) &&
      (!query || l.message.toLowerCase().includes(query))
  )
  const visible = matching.slice(0, MAX_SHOWN)

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <FilterSelect label="Service" allLabel="All services" value={service} options={SOURCES} onChange={setService} />
        <FilterSelect label="Level" allLabel="All levels" value={level} options={LEVELS} onChange={setLevel} />
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search messages" aria-label="Search messages" className="h-8 w-56 pl-8" />
        </div>
        <Button variant="outline" size="sm" className="ml-auto" onClick={() => setPaused((p) => !p)}>
          {paused ? <Play /> : <Pause />}
          {paused ? "Resume" : "Pause"}
        </Button>
      </div>
      <ConnectionNotice connection={connection} />
      <Card>
        <CardHeader>
          <CardTitle>Live logs</CardTitle>
          <CardDescription>
            {matching.length > MAX_SHOWN ? `newest ${MAX_SHOWN} of ${matching.length}` : matching.length} matching lines ·{" "}
            {paused ? "paused" : "streamed from the detection service"}, last 200 kept per service
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="max-h-[calc(100svh-17rem)] min-h-64 overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Service</TableHead>
                  <TableHead>Level</TableHead>
                  <TableHead>Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((line) => (
                  // lines that belong to an alert get a light red background
                  <TableRow key={line.id} className={cn(lineAlerts[line.id] && "bg-critical/5 hover:bg-critical/10")}>
                    <TableCell className="font-mono text-xs tabular-nums">{line.time}</TableCell>
                    <TableCell className="font-mono text-xs">{line.service}</TableCell>
                    <TableCell>
                      <StatusBadge tone={LEVEL_TONE[line.level]} label={line.level} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {line.message}
                      {lineAlerts[line.id] && (
                        <span className="ml-2 font-sans font-medium text-critical" title={alertReasons[lineAlerts[line.id]]}>
                          alert {lineAlerts[line.id]}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </>
  )
}

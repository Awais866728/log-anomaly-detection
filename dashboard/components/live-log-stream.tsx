"use client"

import { useEffect, useState } from "react"
import { Pause, Play, Search } from "lucide-react"

import { ALL, FilterSelect } from "@/components/filter-select"
import { StatusBadge, type Tone } from "@/components/status-badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { nextLogLines } from "@/lib/mock-data"
import { SERVICE_NAMES, type LogLevel, type LogLine } from "@/lib/types"
import { cn } from "@/lib/utils"

const LEVELS: LogLevel[] = ["INFO", "WARN", "ERROR"]
const LEVEL_TONE: Record<LogLevel, Tone> = { INFO: "neutral", WARN: "warning", ERROR: "critical" }

// alertReasons maps an alert id to its reason, for lines that belong to an alert
export function LiveLogStream({ alertReasons }: { alertReasons: Record<string, string> }) {
  const [lines, setLines] = useState<LogLine[]>([])
  const [paused, setPaused] = useState(false)
  const [service, setService] = useState(ALL)
  const [level, setLevel] = useState(ALL)
  const [search, setSearch] = useState("")

  useEffect(() => {
    if (paused) return
    const tick = () => setLines((prev) => nextLogLines(prev, new Date()))
    const first = setTimeout(tick, 0)
    const timer = setInterval(tick, 1000)
    return () => {
      clearTimeout(first)
      clearInterval(timer)
    }
  }, [paused])

  const query = search.trim().toLowerCase()
  const visible = lines.filter(
    (l) =>
      (service === ALL || l.service === service) &&
      (level === ALL || l.level === level) &&
      (!query || l.message.toLowerCase().includes(query))
  )

  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <FilterSelect label="Service" value={service} options={SERVICE_NAMES} onChange={setService} />
        <FilterSelect label="Level" value={level} options={LEVELS} onChange={setLevel} />
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search messages" aria-label="Search messages" className="h-8 w-56 pl-8" />
        </div>
        <Button variant="outline" size="sm" className="ml-auto" onClick={() => setPaused((p) => !p)}>
          {paused ? <Play /> : <Pause />}
          {paused ? "Resume" : "Pause"}
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Live logs</CardTitle>
          <CardDescription>
            {visible.length} of {lines.length} lines · {paused ? "paused" : "new lines every second"}, last 200 kept
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
                  <TableRow key={line.id} className={cn(line.alertId && "bg-critical/5 hover:bg-critical/10")}>
                    <TableCell className="font-mono text-xs tabular-nums">{line.time}</TableCell>
                    <TableCell className="font-mono text-xs">{line.service}</TableCell>
                    <TableCell>
                      <StatusBadge tone={LEVEL_TONE[line.level]} label={line.level} />
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {line.message}
                      {line.alertId && (
                        <span className="ml-2 font-sans font-medium text-critical" title={alertReasons[line.alertId]}>
                          alert {line.alertId}
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

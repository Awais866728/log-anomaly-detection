"use client"

import { StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { Alert } from "@/lib/types"
import { cn } from "@/lib/utils"

interface AlertsTableProps {
  title: string
  alerts: Alert[]
  showStatus?: boolean
  onSelect?: (alert: Alert) => void
}

export function AlertsTable({ title, alerts, showStatus = false, onSelect }: AlertsTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Service</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Severity</TableHead>
              {showStatus && <TableHead>Status</TableHead>}
              <TableHead>Reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {alerts.map((alert) => (
              <TableRow
                key={alert.id}
                className={cn(onSelect && "cursor-pointer")}
                // rows act as buttons when they open details
                {...(onSelect && {
                  tabIndex: 0,
                  role: "button",
                  onClick: () => onSelect(alert),
                  onKeyDown: (e: React.KeyboardEvent) => (e.key === "Enter" || e.key === " ") && onSelect(alert),
                })}
              >
                <TableCell className="font-mono text-xs tabular-nums">{alert.time}</TableCell>
                <TableCell className="font-mono text-xs">{alert.source}</TableCell>
                <TableCell>{alert.model}</TableCell>
                <TableCell>
                  <StatusBadge tone={alert.severity} label={alert.level ?? alert.severity} />
                </TableCell>
                {showStatus && (
                  <TableCell>
                    <StatusBadge tone={alert.status === "open" ? "neutral" : "healthy"} label={alert.status} />
                  </TableCell>
                )}
                <TableCell className="min-w-64 whitespace-normal text-muted-foreground">{alert.reason}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

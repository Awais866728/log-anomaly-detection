import { StatusBadge } from "@/components/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { Alert } from "@/lib/types"

export function RecentAlertsTable({ alerts }: { alerts: Alert[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent alerts</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Time</TableHead>
              <TableHead>Service</TableHead>
              <TableHead>Model</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Reason</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {alerts.map((alert) => (
              <TableRow key={alert.id}>
                <TableCell className="font-mono text-xs tabular-nums">{alert.time}</TableCell>
                <TableCell className="font-mono text-xs">{alert.service}</TableCell>
                <TableCell>{alert.model}</TableCell>
                <TableCell>
                  <StatusBadge tone={alert.severity} label={alert.severity} />
                </TableCell>
                <TableCell className="min-w-64 whitespace-normal text-muted-foreground">{alert.reason}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}

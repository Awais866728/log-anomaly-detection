import { NoData } from "@/components/no-data"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import type { PackInfo } from "@/lib/types"

// Model packs loaded in the detection service, one row per source
export function LivePacks({ packs }: { packs: PackInfo[] | null }) {
  const live = packs?.filter((p) => p.mode === "live") ?? []
  const replay = packs?.filter((p) => p.mode === "replay") ?? []
  return (
    <Card className="min-w-0">
      <CardHeader>
        <CardTitle>Live services</CardTitle>
        <CardDescription>
          Models loaded in the detection service per Docker service, trained on the collected normal logs (python -m
          src.streaming.packs live)
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {packs == null ? (
          <NoData />
        ) : live.length === 0 ? (
          <p className="text-sm text-muted-foreground">No live packs loaded.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Service</TableHead>
                <TableHead>Models (setting)</TableHead>
                <TableHead>Window</TableHead>
                <TableHead className="text-right">Templates</TableHead>
                <TableHead className="text-right">Training windows</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {live.map((p) => (
                <TableRow key={p.source}>
                  <TableCell className="font-medium">{p.label}</TableCell>
                  <TableCell className="whitespace-normal">
                    {p.models.map((m) => `${m} (${p.settings[m] ?? "default"})`).join(", ")}
                  </TableCell>
                  <TableCell>{p.window}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.templates}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.train_windows ?? <NoData />}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {replay.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Replay packs also loaded:{" "}
            {replay
              .map(
                (p) =>
                  `${p.label}: ${p.models.join(", ")}, ${p.templates} templates, window ${p.window}` +
                  (p.labelled ? "" : ` (no labels; settings chosen on ${p.settings_from ?? "another dataset"})`)
              )
              .join("; ")}
            .
          </p>
        )}
      </CardContent>
    </Card>
  )
}

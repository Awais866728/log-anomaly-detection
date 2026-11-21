"use client"

import { StatusBadge } from "@/components/status-badge"
import { DETECTOR_URL, type Connection } from "@/lib/detector"

// Shown above live data when the detection service can't be reached
export function ConnectionNotice({ connection }: { connection: Connection }) {
  if (connection === "live") return null
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border px-3 py-2 text-sm text-muted-foreground">
      <StatusBadge tone={connection === "offline" ? "critical" : "neutral"} label={connection} />
      {connection === "offline" ? (
        <span>
          Detection service not reachable at <code className="font-mono text-xs">{DETECTOR_URL}</code>. Start it with{" "}
          <code className="font-mono text-xs">uvicorn src.streaming.service:app --port 8000</code> (see the README).
        </span>
      ) : (
        <span>Connecting to the detection service ...</span>
      )}
    </div>
  )
}

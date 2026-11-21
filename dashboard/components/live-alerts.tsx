"use client"

import { AlertsExplorer } from "@/components/alerts-explorer"
import { ConnectionNotice } from "@/components/connection-notice"
import { useDetectorFeed } from "@/lib/detector"

// Alerts page: alerts from the detection service, updated as they are produced
export function LiveAlerts() {
  const { connection, alerts } = useDetectorFeed()
  return (
    <>
      <ConnectionNotice connection={connection} />
      <AlertsExplorer alerts={alerts} />
    </>
  )
}

import { LiveLogStream } from "@/components/live-log-stream"
import { getAlerts } from "@/lib/mock-data"

export default async function LiveLogsPage() {
  const alerts = await getAlerts()
  return <LiveLogStream alertReasons={Object.fromEntries(alerts.map((a) => [a.id, a.reason]))} />
}

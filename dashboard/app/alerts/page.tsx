import { AlertsExplorer } from "@/components/alerts-explorer"
import { getAlerts } from "@/lib/mock-data"

export default async function AlertsPage() {
  return <AlertsExplorer alerts={await getAlerts()} />
}

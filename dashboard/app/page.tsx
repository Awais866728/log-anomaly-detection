import { LiveOverview } from "@/components/live-overview"
import { getServices } from "@/lib/mock-data"

export default async function OverviewPage() {
  // service health is still sample data; KPIs and alerts come from the detection service
  return <LiveOverview services={await getServices()} />
}

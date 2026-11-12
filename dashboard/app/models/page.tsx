import { ModelsView } from "@/components/models-view"
import { getModelResults } from "@/lib/mock-data"

export default async function ModelsPage() {
  return <ModelsView models={await getModelResults()} />
}

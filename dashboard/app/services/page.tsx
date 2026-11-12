import { PipelineFlow } from "@/components/pipeline-flow"
import { ServiceCard } from "@/components/service-card"
import { getPipeline, getServices } from "@/lib/mock-data"

export default async function ServicesPage() {
  const [services, pipeline] = await Promise.all([getServices(), getPipeline()])

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {services.map((service) => (
          <ServiceCard key={service.name} service={service} />
        ))}
      </div>
      <PipelineFlow steps={pipeline} />
    </>
  )
}

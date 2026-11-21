"use client"

import { useEffect, useState } from "react"

import { ConnectionNotice } from "@/components/connection-notice"
import { ModelsView } from "@/components/models-view"
import { SkeletonCard } from "@/components/skeletons"
import { getModelResults, type Connection } from "@/lib/detector"
import type { ModelResult } from "@/lib/types"

// Model comparison from docs/cross_system_results.csv, served by the detection service
export function LiveModels() {
  const [models, setModels] = useState<ModelResult[] | null>(null)
  const [connection, setConnection] = useState<Connection>("connecting")

  useEffect(() => {
    getModelResults()
      .then((m) => {
        setModels(m)
        setConnection("live")
      })
      .catch(() => setConnection("offline"))
  }, [])

  return (
    <>
      <ConnectionNotice connection={connection} />
      {models ? <ModelsView models={models} /> : <SkeletonCard bodyClassName="h-72" />}
    </>
  )
}

"use client"

import { useEffect, useState } from "react"

import { ConnectionNotice } from "@/components/connection-notice"
import { LivePacks } from "@/components/live-packs"
import { ModelsView } from "@/components/models-view"
import { SkeletonCard } from "@/components/skeletons"
import { getModelResults, getPacks, type Connection } from "@/lib/detector"
import type { ModelResult, PackInfo } from "@/lib/types"

// Model comparison from docs/cross_system_results.csv and the packs loaded, both served by the detection service
export function LiveModels() {
  const [models, setModels] = useState<ModelResult[] | null>(null)
  const [packs, setPacks] = useState<PackInfo[] | null>(null)
  const [connection, setConnection] = useState<Connection>("connecting")

  useEffect(() => {
    Promise.all([getModelResults(), getPacks()])
      .then(([m, p]) => {
        setModels(m)
        setPacks(p)
        setConnection("live")
      })
      .catch(() => setConnection("offline"))
  }, [])

  return (
    <>
      <ConnectionNotice connection={connection} />
      {models ? <ModelsView models={models} /> : <SkeletonCard bodyClassName="h-72" />}
      <LivePacks packs={packs} />
    </>
  )
}

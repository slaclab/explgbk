import { createFileRoute } from "@tanstack/react-router"

import { instrumentsReadInstrumentsOptions } from "@/client/@tanstack/react-query.gen"
import { InstrumentsGrid } from "@/components/Experiments/InstrumentsGrid"

export const Route = createFileRoute("/_layout/experiments/")({
  loader: ({ context: { queryClient } }) => {
    queryClient.prefetchQuery(instrumentsReadInstrumentsOptions())
  },
  head: () => ({
    meta: [{ title: "Experiments - Experimental Logbook" }],
  }),
  component: ExperimentsIndex,
})

function ExperimentsIndex() {
  return (
    <div className="flex flex-col gap-6 min-h-0 flex-1">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Experiments</h1>
        <p className="text-muted-foreground">
          Select an instrument to browse its experiments
        </p>
      </div>
      <InstrumentsGrid />
    </div>
  )
}

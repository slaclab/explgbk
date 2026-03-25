import { createFileRoute } from "@tanstack/react-router"
import { z } from "zod"

import type { ExperimentsReadExperimentsData } from "@/client"
import {
  experimentsReadExperimentsQueryKey,
  instrumentsReadInstrumentsOptions,
} from "@/client/@tanstack/react-query.gen"
import { zExperimentsReadExperimentsData } from "@/client/zod.gen"
import { ExperimentsService } from "@/client/sdk.gen"
import { InstrumentExperiments } from "@/components/Experiments/ExperimentsTable"

const PAGE_SIZE = 25

type SortBy = NonNullable<ExperimentsReadExperimentsData["query"]>["sort_by"]

// Reuse the generated enum so the allowed values stay in sync with the API
const sortByEnum = zExperimentsReadExperimentsData.shape.query
  .unwrap()
  .shape.sort_by.unwrap()

const searchSchema = z.object({
  sort_by: sortByEnum.default(sortByEnum.options[0]),
  sort_desc: z.boolean().default(false),
})

export const Route = createFileRoute("/_layout/experiments/$instrument")({
  validateSearch: searchSchema,
  loaderDeps: ({ search: { sort_by, sort_desc } }) => ({ sort_by, sort_desc }),
  loader: async ({
    context: { queryClient },
    params: { instrument },
    deps: { sort_by, sort_desc },
  }) => {
    const queryOptions = {
      query: {
        limit: PAGE_SIZE,
        sort_by: sort_by as SortBy,
        sort_desc,
        instrument,
      },
    }
    // Prefetch instruments list (for back-navigation cache warmth)
    queryClient.prefetchQuery(instrumentsReadInstrumentsOptions())
    // Prefetch page 0 of the experiments infinite query (non-blocking)
    queryClient.prefetchInfiniteQuery({
      queryKey: experimentsReadExperimentsQueryKey(queryOptions),
      queryFn: async ({ signal }) => {
        const { data } = await ExperimentsService.experimentsReadExperiments({
          ...queryOptions,
          query: { ...queryOptions.query, skip: 0 },
          signal,
          throwOnError: true,
        })
        return data
      },
      initialPageParam: 0,
    })
  },
  head: ({ params }) => ({
    meta: [{ title: `${params.instrument} Experiments` }],
  }),
  component: InstrumentExperiments,
})

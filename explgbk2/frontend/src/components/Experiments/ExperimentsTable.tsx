import { useInfiniteQuery } from "@tanstack/react-query"
import { useNavigate, useParams, useSearch } from "@tanstack/react-router"
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table"
import { Loader2, Search } from "lucide-react"
import { useEffect, useMemo, useRef } from "react"
import { useInView } from "react-intersection-observer"

import {
  type ExperimentsReadExperimentsData,
  ExperimentsService,
} from "@/client"
import { experimentsReadExperimentsQueryKey } from "@/client/@tanstack/react-query.gen"
import { experimentColumns } from "@/components/Experiments/columns"
import PendingExperiments from "@/components/Pending/PendingExperiments"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const PAGE_SIZE = 25

type SortBy = NonNullable<ExperimentsReadExperimentsData["query"]>["sort_by"]

export function ExperimentsTable() {
  const { instrument } = useParams({
    from: "/_layout/experiments/$instrument",
  })
  const { sort_by, sort_desc } = useSearch({
    from: "/_layout/experiments/$instrument",
  })
  const navigate = useNavigate()
  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const sorting: SortingState = [{ id: sort_by, desc: sort_desc }]

  const setSorting = (
    updaterOrValue: SortingState | ((prev: SortingState) => SortingState),
  ) => {
    const next =
      typeof updaterOrValue === "function"
        ? updaterOrValue(sorting)
        : updaterOrValue
    const first = next[0]
    if (first) {
      navigate({
        to: "/experiments/$instrument",
        params: { instrument },
        search: { sort_by: first.id as SortBy, sort_desc: first.desc },
        replace: true,
      })
    }
  }

  const baseQueryOptions = {
    query: {
      limit: PAGE_SIZE,
      sort_by: sort_by as SortBy,
      sort_desc,
      instrument,
    },
  }

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isPending } =
    useInfiniteQuery({
      queryKey: experimentsReadExperimentsQueryKey(baseQueryOptions),
      queryFn: async ({ pageParam = 0, signal }) => {
        const { data } = await ExperimentsService.experimentsReadExperiments({
          ...baseQueryOptions,
          query: {
            ...baseQueryOptions.query,
            skip: (pageParam as number) * PAGE_SIZE,
          },
          signal,
          throwOnError: true,
        })
        return data
      },
      initialPageParam: 0,
      getNextPageParam: (lastPage, allPages) => {
        const loaded = allPages.length * PAGE_SIZE
        return loaded < lastPage.count ? allPages.length : undefined
      },
    })

  const { ref: sentinelRef, inView } = useInView({ threshold: 0.1 })

  useEffect(() => {
    if (inView && hasNextPage && !isFetchingNextPage) {
      fetchNextPage()
    }
  }, [inView, hasNextPage, isFetchingNextPage, fetchNextPage])

  // biome-ignore lint/correctness/useExhaustiveDependencies: intentionally scroll to top when instrument or sort changes
  useEffect(() => {
    scrollContainerRef.current?.scrollTo({ top: 0 })
  }, [instrument, sort_by, sort_desc])

  const experiments = useMemo(
    () => data?.pages.flatMap((page) => page.data ?? []) ?? [],
    [data],
  )
  const totalCount = data?.pages[0]?.count ?? 0

  const table = useReactTable({
    data: experiments,
    columns: experimentColumns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    manualSorting: true,
    enableSortingRemoval: false,
    onSortingChange: setSorting,
    state: { sorting },
  })

  if (isPending) return <PendingExperiments />

  if (experiments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No experiments found</h3>
        <p className="text-muted-foreground">
          No experiments are available for {instrument}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 min-h-0 flex-1">
      <div className="text-sm text-muted-foreground">
        Showing {experiments.length} of {totalCount} experiments
      </div>
      <div
        ref={scrollContainerRef}
        className="flex-1 min-h-0 overflow-y-auto rounded-md border"
      >
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-background">
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent">
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <div ref={sentinelRef} className="flex justify-center py-4">
          {isFetchingNextPage && (
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          )}
        </div>
      </div>
    </div>
  )
}

export function InstrumentExperiments() {
  const { instrument } = useParams({
    from: "/_layout/experiments/$instrument",
  })
  return (
    <div className="flex flex-col gap-6 min-h-0 flex-1">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{instrument}</h1>
        <p className="text-muted-foreground">Experiments for {instrument}</p>
      </div>
      <ExperimentsTable />
    </div>
  )
}

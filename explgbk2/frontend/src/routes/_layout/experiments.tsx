import { useInfiniteQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { Loader2, Search } from "lucide-react"
import { useEffect, useRef } from "react"

import { ExperimentsService } from "@/client"
import { columns } from "@/components/Experiments/columns"
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

export const Route = createFileRoute("/_layout/experiments")({
  component: Experiments,
  head: () => ({
    meta: [
      {
        title: "Experiments - Experimental Logbook",
      },
    ],
  }),
})

function ExperimentsTable() {
  const sentinelRef = useRef<HTMLDivElement>(null)

  const { data, fetchNextPage, hasNextPage, isFetchingNextPage, isPending } =
    useInfiniteQuery({
      queryKey: ["experiments"],
      queryFn: ({ pageParam = 0 }) =>
        ExperimentsService.experimentsReadExperiments({
          query: { skip: pageParam * PAGE_SIZE, limit: PAGE_SIZE },
        }),
      initialPageParam: 0,
      getNextPageParam: (lastPage, allPages) => {
        const loaded = allPages.length * PAGE_SIZE
        return loaded < (lastPage.data?.count ?? 0) ? allPages.length : undefined
      },
    })

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage()
        }
      },
      { threshold: 0.1 },
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])

  const experiments = data?.pages.flatMap((page) => page.data?.data ?? []) ?? []
  const totalCount = data?.pages[0]?.data?.count ?? 0

  const table = useReactTable({
    data: experiments,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  if (isPending) return <PendingExperiments />

  if (experiments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <Search className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No experiments found</h3>
        <p className="text-muted-foreground">No experiments are available yet</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 min-h-0 flex-1">
      <div className="text-sm text-muted-foreground">
        Showing {experiments.length} of {totalCount} experiments
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto rounded-md border">
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

function Experiments() {
  return (
    <div className="flex flex-col gap-6 min-h-0 flex-1">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Experiments</h1>
          <p className="text-muted-foreground">Browse and view experiments</p>
        </div>
      </div>
      <ExperimentsTable />
    </div>
  )
}

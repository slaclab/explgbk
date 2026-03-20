import type { Column, ColumnDef } from "@tanstack/react-table"
import { format, parseISO } from "date-fns"
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react"
import type { ExperimentPublic } from "@/client"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

function SortHeader({
  column,
  label,
}: {
  column: Column<ExperimentPublic>
  label: string
}) {
  const sorted = column.getIsSorted()
  return (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-3 h-8 data-[state=open]:bg-accent"
      onClick={column.getToggleSortingHandler()}
    >
      {label}
      {sorted === "asc" ? (
        <ArrowUp className="ml-2 h-4 w-4" />
      ) : sorted === "desc" ? (
        <ArrowDown className="ml-2 h-4 w-4" />
      ) : (
        <ArrowUpDown className="ml-2 h-4 w-4 opacity-50" />
      )}
    </Button>
  )
}

export const columns: ColumnDef<ExperimentPublic>[] = [
  {
    accessorKey: "name",
    header: ({ column }) => <SortHeader column={column} label="Name" />,
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "instrument",
    header: ({ column }) => <SortHeader column={column} label="Instrument" />,
    cell: ({ row }) => {
      const instrument = row.original.instrument
      return (
        <span className={cn("text-muted-foreground", !instrument && "italic")}>
          {instrument || "—"}
        </span>
      )
    },
  },
  {
    accessorKey: "leader_account",
    header: ({ column }) => <SortHeader column={column} label="Leader" />,
    cell: ({ row }) => {
      const leader = row.original.leader_account
      return (
        <span className={cn("text-muted-foreground", !leader && "italic")}>
          {leader || "—"}
        </span>
      )
    },
  },
  {
    accessorKey: "run_count",
    header: ({ column }) => <SortHeader column={column} label="Runs" />,
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">
        {row.original.run_count ?? 0}
      </span>
    ),
  },
  {
    accessorKey: "start_time",
    header: ({ column }) => <SortHeader column={column} label="Start Time" />,
    cell: ({ row }) => {
      const start = row.original.start_time
      return (
        <span className="text-muted-foreground text-sm">
          {start ? format(parseISO(start), "PPp") : "—"}
        </span>
      )
    },
  },
  {
    accessorKey: "created_at",
    header: ({ column }) => <SortHeader column={column} label="Created" />,
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">
        {row.original.created_at
          ? format(parseISO(row.original.created_at), "PPp")
          : "—"}
      </span>
    ),
  },
]

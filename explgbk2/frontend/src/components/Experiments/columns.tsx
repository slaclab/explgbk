import type { ColumnDef } from "@tanstack/react-table"
import { format, parseISO } from "date-fns"
import type { ExperimentPublic } from "@/client"
import { cn } from "@/lib/utils"

export const columns: ColumnDef<ExperimentPublic>[] = [
  {
    accessorKey: "name",
    header: "Name",
    cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
  },
  {
    accessorKey: "instrument",
    header: "Instrument",
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
    header: "Leader",
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
    header: "Runs",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">
        {row.original.run_count ?? 0}
      </span>
    ),
  },
  {
    accessorKey: "start_time",
    header: "Start Time",
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
    header: "Created",
    cell: ({ row }) => (
      <span className="text-muted-foreground text-sm">
        {row.original.created_at
          ? format(parseISO(row.original.created_at), "PPp")
          : "—"}
      </span>
    ),
  },
]

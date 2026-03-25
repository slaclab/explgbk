import { useQuery } from "@tanstack/react-query"
import { Link } from "@tanstack/react-router"
import { FlaskConical } from "lucide-react"

import { instrumentsReadInstrumentsOptions } from "@/client/@tanstack/react-query.gen"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

function InstrumentCardSkeleton() {
  return (
    <Card className="cursor-pointer">
      <CardHeader className="pb-2">
        <Skeleton className="h-6 w-24" />
      </CardHeader>
      <CardContent>
        <Skeleton className="h-5 w-16" />
      </CardContent>
    </Card>
  )
}

export function InstrumentsGrid() {
  const { data, isPending, isError } = useQuery(
    instrumentsReadInstrumentsOptions(),
  )

  const instruments = data ?? []

  if (isPending) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {Array.from({ length: 10 }).map((_, i) => (
          <InstrumentCardSkeleton key={i} />
        ))}
      </div>
    )
  }

  if (isError || instruments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center text-center py-12">
        <div className="rounded-full bg-muted p-4 mb-4">
          <FlaskConical className="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold">No instruments found</h3>
        <p className="text-muted-foreground">
          No instruments are available for your account
        </p>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto">
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {instruments.map((item) => (
          <Link
            key={item.instrument}
            to="/experiments/$instrument"
            params={{ instrument: item.instrument }}
            className="block"
          >
            <Card className="cursor-pointer hover:bg-accent transition-colors h-full">
              <CardHeader className="pb-1 pt-3 px-4">
                <CardTitle className="text-sm font-semibold">
                  {item.instrument}
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-3">
                <Badge variant="secondary">{item.experiment_count}</Badge>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}

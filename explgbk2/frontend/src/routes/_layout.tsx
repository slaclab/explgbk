import { createFileRoute, Link, Outlet, useMatch } from "@tanstack/react-router"

import { Footer } from "@/components/Common/Footer"
import AppSidebar from "@/components/Sidebar/AppSidebar"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"

export const Route = createFileRoute("/_layout")({
  component: Layout,
})

function LayoutBreadcrumbs() {
  const instrumentMatch = useMatch({
    from: "/_layout/experiments/$instrument",
    shouldThrow: false,
  })

  if (!instrumentMatch) return null

  const { instrument } = instrumentMatch.params

  return (
    <>
      <Separator orientation="vertical" className="mr-2 h-4" />
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/experiments">Experiments</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{instrument}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    </>
  )
}

function Layout() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset className="h-svh overflow-hidden">
        <header className="shrink-0 flex h-16 items-center gap-2 border-b bg-background px-4 z-10">
          <SidebarTrigger className="-ml-1 text-muted-foreground" />
          <LayoutBreadcrumbs />
        </header>
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden p-6 md:p-8">
          <div className="mx-auto max-w-7xl w-full flex flex-col flex-1 min-h-0">
            <Outlet />
          </div>
        </div>
        <Footer />
      </SidebarInset>
    </SidebarProvider>
  )
}

export default Layout

import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"

import { AppSidebar } from "@/components/app-sidebar"
import { ThemeProvider } from "@/components/theme-provider"
import { TopBar } from "@/components/top-bar"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { TooltipProvider } from "@/components/ui/tooltip"
import "./globals.css"

const geistSans = Geist({ variable: "--font-sans", subsets: ["latin"] })
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] })

export const metadata: Metadata = {
  title: "LogSentinel",
  description: "Log anomaly detection dashboard",
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <TooltipProvider>
            <SidebarProvider>
              <AppSidebar />
              {/* min-w-0 keeps the content within the space next to the sidebar */}
              <SidebarInset className="min-w-0">
                <TopBar />
                <div className="flex min-w-0 flex-1 flex-col gap-4 p-4 md:p-6">{children}</div>
              </SidebarInset>
            </SidebarProvider>
          </TooltipProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}

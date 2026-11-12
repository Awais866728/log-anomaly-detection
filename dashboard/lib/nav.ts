import { Bell, Boxes, BrainCircuit, LayoutDashboard, ScrollText, type LucideIcon } from "lucide-react"

export interface NavItem {
  title: string
  href: string
  icon: LucideIcon
}

export const NAV_ITEMS: NavItem[] = [
  { title: "Overview", href: "/", icon: LayoutDashboard },
  { title: "Live Logs", href: "/live-logs", icon: ScrollText },
  { title: "Alerts", href: "/alerts", icon: Bell },
  { title: "Models", href: "/models", icon: BrainCircuit },
  { title: "Services", href: "/services", icon: Boxes },
]

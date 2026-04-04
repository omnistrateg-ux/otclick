"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Users,
  Mail,
  BarChart3,
  UserCheck,
  Settings,
  Zap,
} from "lucide-react"

const navigation = [
  { name: "Дашборд", href: "/", icon: LayoutDashboard },
  { name: "Лиды", href: "/leads", icon: Users },
  { name: "Кампании", href: "/campaigns", icon: Mail },
  { name: "Аналитика", href: "/analytics", icon: BarChart3 },
  { name: "Тёплые лиды", href: "/handoffs", icon: UserCheck },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-zinc-800 bg-zinc-950">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-zinc-800 px-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600 to-orange-500">
          <Zap className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-zinc-100">Отклик</h1>
          <p className="text-xs text-zinc-500">Lead Acquisition</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {navigation.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href))

          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                isActive
                  ? "bg-indigo-600/20 text-indigo-400"
                  : "text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-100"
              )}
            >
              <item.icon
                className={cn(
                  "h-5 w-5 transition-colors",
                  isActive
                    ? "text-indigo-400"
                    : "text-zinc-500 group-hover:text-zinc-300"
                )}
              />
              {item.name}
              {isActive && (
                <div className="ml-auto h-1.5 w-1.5 rounded-full bg-indigo-400" />
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-zinc-800 p-4">
        <Link
          href="/settings"
          className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-zinc-400 transition-all hover:bg-zinc-800/50 hover:text-zinc-100"
        >
          <Settings className="h-5 w-5 text-zinc-500" />
          Настройки
        </Link>
        <div className="mt-3 rounded-lg bg-gradient-to-r from-indigo-600/10 to-orange-500/10 p-3">
          <p className="text-xs text-zinc-400">
            Версия 1.0.0
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            Employer Acquisition Engine
          </p>
        </div>
      </div>
    </aside>
  )
}

import { cn } from "@/lib/utils"
import { LucideIcon } from "lucide-react"

interface KPICardProps {
  title: string
  value: string | number
  change?: number
  changeLabel?: string
  icon: LucideIcon
  gradient?: "indigo" | "orange" | "emerald" | "rose"
}

const gradients = {
  indigo: "from-indigo-600/20 to-indigo-600/5",
  orange: "from-orange-600/20 to-orange-600/5",
  emerald: "from-emerald-600/20 to-emerald-600/5",
  rose: "from-rose-600/20 to-rose-600/5",
}

const iconColors = {
  indigo: "text-indigo-400",
  orange: "text-orange-400",
  emerald: "text-emerald-400",
  rose: "text-rose-400",
}

export function KPICard({
  title,
  value,
  change,
  changeLabel,
  icon: Icon,
  gradient = "indigo",
}: KPICardProps) {
  const isPositive = change && change > 0

  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-zinc-800 bg-gradient-to-br p-6",
        gradients[gradient]
      )}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-zinc-400">{title}</p>
          <p className="mt-2 text-3xl font-bold text-zinc-100">{value}</p>
          {change !== undefined && (
            <div className="mt-2 flex items-center gap-1">
              <span
                className={cn(
                  "text-sm font-medium",
                  isPositive ? "text-emerald-400" : "text-rose-400"
                )}
              >
                {isPositive ? "+" : ""}
                {change}%
              </span>
              {changeLabel && (
                <span className="text-sm text-zinc-500">{changeLabel}</span>
              )}
            </div>
          )}
        </div>
        <div
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-lg bg-zinc-800/50",
            iconColors[gradient]
          )}
        >
          <Icon className="h-6 w-6" />
        </div>
      </div>

      {/* Decorative element */}
      <div className="absolute -bottom-4 -right-4 h-24 w-24 rounded-full bg-gradient-to-br from-white/5 to-transparent blur-2xl" />
    </div>
  )
}

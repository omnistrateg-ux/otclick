"use client"

import { useEffect, useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import {
  TrendingUp,
  TrendingDown,
  Users,
  Mail,
  Eye,
  MessageSquare,
  DollarSign,
  Target,
} from "lucide-react"

interface StatItem {
  label: string
  value: number
  previousValue: number
  format: "number" | "percent" | "currency"
  icon: typeof Users
  color: string
}

const stats: StatItem[] = [
  {
    label: "Новых лидов сегодня",
    value: 47,
    previousValue: 38,
    format: "number",
    icon: Users,
    color: "text-indigo-400",
  },
  {
    label: "Писем отправлено",
    value: 156,
    previousValue: 142,
    format: "number",
    icon: Mail,
    color: "text-emerald-400",
  },
  {
    label: "Open Rate",
    value: 34.5,
    previousValue: 31.2,
    format: "percent",
    icon: Eye,
    color: "text-amber-400",
  },
  {
    label: "Reply Rate",
    value: 8.2,
    previousValue: 7.8,
    format: "percent",
    icon: MessageSquare,
    color: "text-orange-400",
  },
  {
    label: "Конверсия",
    value: 4.7,
    previousValue: 4.2,
    format: "percent",
    icon: Target,
    color: "text-rose-400",
  },
  {
    label: "Расходы сегодня",
    value: 12.45,
    previousValue: 15.20,
    format: "currency",
    icon: DollarSign,
    color: "text-violet-400",
  },
]

function formatValue(value: number, format: "number" | "percent" | "currency") {
  switch (format) {
    case "percent":
      return `${value.toFixed(1)}%`
    case "currency":
      return `$${value.toFixed(2)}`
    default:
      return value.toLocaleString("ru-RU")
  }
}

export function QuickStats() {
  const [animatedStats, setAnimatedStats] = useState(
    stats.map((s) => ({ ...s, displayValue: 0 }))
  )

  useEffect(() => {
    const duration = 1000
    const steps = 30
    const interval = duration / steps

    let step = 0
    const timer = setInterval(() => {
      step++
      setAnimatedStats(
        stats.map((stat) => ({
          ...stat,
          displayValue: (stat.value * step) / steps,
        }))
      )
      if (step >= steps) clearInterval(timer)
    }, interval)

    return () => clearInterval(timer)
  }, [])

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {animatedStats.map((stat, index) => {
        const change = ((stat.value - stat.previousValue) / stat.previousValue) * 100
        const isPositive = change > 0
        const Icon = stat.icon

        return (
          <Card
            key={index}
            className="group hover:border-zinc-600 transition-all cursor-default"
          >
            <CardContent className="pt-4 pb-3">
              <div className="flex items-center justify-between mb-2">
                <Icon className={`h-5 w-5 ${stat.color}`} />
                <div
                  className={`flex items-center gap-0.5 text-xs ${
                    isPositive ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {isPositive ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {Math.abs(change).toFixed(1)}%
                </div>
              </div>
              <p className="text-2xl font-bold text-zinc-100 tabular-nums">
                {formatValue(stat.displayValue, stat.format)}
              </p>
              <p className="text-xs text-zinc-500 mt-1">{stat.label}</p>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

"use client"

import { useQuery } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import {
  Users,
  Mail,
  MessageSquare,
  Target,
  Building2,
  Zap,
} from "lucide-react"

interface LeadStats {
  total: number
  by_status: Record<string, number>
}

export function QuickStats() {
  const { data: stats, isLoading, isError } = useQuery({
    queryKey: ["lead-stats"],
    queryFn: async (): Promise<LeadStats> => {
      try {
        const response = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://176.126.166.94:8001/api/v1"}/leads/stats`,
          { signal: AbortSignal.timeout(10000) }
        )
        if (!response.ok) throw new Error("API error")
        return response.json()
      } catch {
        return { total: 0, by_status: {} }
      }
    },
    retry: false,
    staleTime: 30000,
  })

  const { data: handoffs } = useQuery({
    queryKey: ["handoffs"],
    queryFn: async () => {
      try {
        return await api.getHandoffs()
      } catch {
        return []
      }
    },
    retry: false,
  })

  const totalLeads = stats?.total || 0
  const byStatus = stats?.by_status || {}
  const enrichedLeads = byStatus["enriched"] || byStatus["enrichment_done"] || 0
  const scoredLeads = byStatus["scored"] || 0
  const qualifiedLeads = byStatus["qualified"] || 0
  const outreachSent = byStatus["outreach_sent"] || 0
  const warmLeads = handoffs?.length || 0

  const statItems = [
    {
      label: "Всего лидов",
      value: totalLeads,
      icon: Users,
      color: "text-indigo-400",
    },
    {
      label: "Обогащено",
      value: enrichedLeads,
      icon: Target,
      color: "text-emerald-400",
    },
    {
      label: "Оценено",
      value: scoredLeads,
      icon: Building2,
      color: "text-amber-400",
    },
    {
      label: "Квалифицировано",
      value: qualifiedLeads,
      icon: MessageSquare,
      color: "text-orange-400",
    },
    {
      label: "Outreach отправлен",
      value: outreachSent,
      icon: Mail,
      color: "text-rose-400",
    },
    {
      label: "Тёплых лидов",
      value: warmLeads,
      icon: Zap,
      color: "text-violet-400",
    },
  ]

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {statItems.map((stat, index) => {
        const Icon = stat.icon

        return (
          <Card
            key={index}
            className="group hover:border-zinc-600 transition-all cursor-default"
          >
            <CardContent className="pt-4 pb-3">
              <div className="flex items-center justify-between mb-2">
                <Icon className={`h-5 w-5 ${stat.color}`} />
              </div>
              <p className="text-2xl font-bold text-zinc-100 tabular-nums">
                {stat.value.toLocaleString("ru-RU")}
              </p>
              <p className="text-xs text-zinc-500 mt-1">{stat.label}</p>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

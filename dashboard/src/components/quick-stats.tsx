"use client"

import { useQuery } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import {
  Users,
  Mail,
  Eye,
  MessageSquare,
  Target,
  Building2,
} from "lucide-react"

export function QuickStats() {
  const { data: leads, isLoading: leadsLoading } = useQuery({
    queryKey: ["leads", { limit: 1 }],
    queryFn: () => api.getLeads({ limit: 1 }),
  })

  const { data: emails, isLoading: emailsLoading } = useQuery({
    queryKey: ["emails", { limit: 1 }],
    queryFn: () => api.getEmails({ limit: 1 }),
  })

  const { data: funnel, isLoading: funnelLoading } = useQuery({
    queryKey: ["funnel"],
    queryFn: api.getFunnel,
  })

  const { data: handoffs, isLoading: handoffsLoading } = useQuery({
    queryKey: ["handoffs"],
    queryFn: api.getHandoffs,
  })

  const isLoading = leadsLoading || emailsLoading || funnelLoading || handoffsLoading

  const totalLeads = leads?.total || 0
  const totalEmails = emails?.total || 0
  const qualifiedLeads = funnel?.find((f) => f.status === "QUALIFIED")?.count || 0
  const sentLeads = funnel?.find((f) => f.status === "OUTREACH_SENT")?.count || 0
  const repliedLeads = funnel?.find((f) => f.status === "REPLY_RECEIVED")?.count || 0
  const warmLeads = handoffs?.length || 0

  const stats = [
    {
      label: "Всего лидов",
      value: totalLeads,
      icon: Users,
      color: "text-indigo-400",
    },
    {
      label: "Писем отправлено",
      value: totalEmails,
      icon: Mail,
      color: "text-emerald-400",
    },
    {
      label: "Квалифицированных",
      value: qualifiedLeads,
      icon: Target,
      color: "text-amber-400",
    },
    {
      label: "Отправлено outreach",
      value: sentLeads,
      icon: Building2,
      color: "text-orange-400",
    },
    {
      label: "Получено ответов",
      value: repliedLeads,
      icon: MessageSquare,
      color: "text-rose-400",
    },
    {
      label: "Тёплых лидов",
      value: warmLeads,
      icon: Eye,
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
      {stats.map((stat, index) => {
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

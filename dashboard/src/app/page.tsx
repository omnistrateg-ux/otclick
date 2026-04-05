"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { FunnelChart } from "@/components/charts/funnel-chart"
import { DiscoveryModal } from "@/components/discovery-modal"
import { CampaignModal } from "@/components/campaign-modal"
import { ActiveTasks } from "@/components/active-tasks"
import { QuickStats } from "@/components/quick-stats"
import { StatusBadge } from "@/components/status-badge"
import { api } from "@/lib/api"
import { formatNumber, formatDate } from "@/lib/utils"
import {
  Rocket,
  Mail,
  Users,
  Zap,
  ArrowRight,
  Building2,
  Star,
  Clock,
  CheckCircle,
  AlertCircle,
  BarChart3,
  Target,
  Activity,
  RefreshCw,
} from "lucide-react"

export default function DashboardPage() {
  const [discoveryOpen, setDiscoveryOpen] = useState(false)
  const [campaignOpen, setCampaignOpen] = useState(false)

  const { data: funnel, isLoading: funnelLoading, refetch: refetchFunnel } = useQuery({
    queryKey: ["funnel"],
    queryFn: api.getFunnel,
  })

  const { data: leads, isLoading: leadsLoading } = useQuery({
    queryKey: ["leads", { limit: 5 }],
    queryFn: () => api.getLeads({ limit: 5 }),
  })

  const { data: handoffs } = useQuery({
    queryKey: ["handoffs"],
    queryFn: api.getHandoffs,
  })

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 30000,
  })

  const totalLeads = funnel?.reduce((sum, item) => sum + item.count, 0) || 0
  const qualifiedLeads = funnel?.find((f) => f.status === "QUALIFIED")?.count || 0
  const warmLeads = handoffs?.length || 0

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Hero Header */}
      <div className="relative overflow-hidden border-b border-zinc-800">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/20 via-transparent to-orange-500/10" />
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-orange-500/10 rounded-full blur-3xl" />

        <div className="relative px-6 py-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-zinc-100">
                Командный центр
              </h1>
              <p className="text-zinc-400 mt-1">
                Управление привлечением работодателей
              </p>
            </div>
            <div className="flex items-center gap-3">
              {health?.status === "ok" ? (
                <Badge variant="success" className="gap-1">
                  <Activity className="h-3 w-3" />
                  Система работает
                </Badge>
              ) : (
                <Badge variant="destructive" className="gap-1">
                  <AlertCircle className="h-3 w-3" />
                  Проверьте подключение
                </Badge>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-4">
            <Button
              size="lg"
              onClick={() => setDiscoveryOpen(true)}
              className="bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 shadow-lg shadow-indigo-500/25 gap-2"
            >
              <Rocket className="h-5 w-5" />
              Запустить Discovery
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => setCampaignOpen(true)}
              className="gap-2"
            >
              <Mail className="h-5 w-5" />
              Создать рассылку
            </Button>
            <Button
              size="lg"
              variant="ghost"
              onClick={() => refetchFunnel()}
              className="gap-2"
            >
              <RefreshCw className="h-5 w-5" />
              Обновить данные
            </Button>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Quick Stats */}
        <QuickStats />

        {/* Active Tasks */}
        <ActiveTasks />

        {/* Main Grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Funnel - takes 2 columns */}
          <Card className="lg:col-span-2">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-indigo-400" />
                Воронка лидов
              </CardTitle>
              <Link href="/analytics">
                <Button variant="ghost" size="sm" className="gap-1">
                  Подробнее
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {funnelLoading ? (
                <Skeleton className="h-[300px]" />
              ) : funnel ? (
                <FunnelChart data={funnel} />
              ) : (
                <div className="flex h-[300px] items-center justify-center text-zinc-500">
                  Нет данных
                </div>
              )}
            </CardContent>
          </Card>

          {/* Summary Cards */}
          <div className="space-y-6">
            {/* Total Leads */}
            <Card className="relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/20 to-transparent" />
              <CardContent className="relative pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-400">Всего в базе</p>
                    <p className="text-4xl font-bold text-zinc-100 mt-1">
                      {formatNumber(totalLeads)}
                    </p>
                    <p className="text-xs text-zinc-500 mt-2">
                      Всего работодателей в базе
                    </p>
                  </div>
                  <div className="h-16 w-16 rounded-2xl bg-indigo-600/20 flex items-center justify-center">
                    <Users className="h-8 w-8 text-indigo-400" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Qualified */}
            <Card className="relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-600/20 to-transparent" />
              <CardContent className="relative pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-400">Квалифицированные</p>
                    <p className="text-4xl font-bold text-zinc-100 mt-1">
                      {formatNumber(qualifiedLeads)}
                    </p>
                    <p className="text-xs text-zinc-500 mt-2">
                      Готовы к рассылке
                    </p>
                  </div>
                  <div className="h-16 w-16 rounded-2xl bg-emerald-600/20 flex items-center justify-center">
                    <Target className="h-8 w-8 text-emerald-400" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Warm Leads */}
            <Card className="relative overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-orange-600/20 to-transparent" />
              <CardContent className="relative pt-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-400">Тёплые лиды</p>
                    <p className="text-4xl font-bold text-zinc-100 mt-1">
                      {warmLeads}
                    </p>
                    <Link href="/handoffs">
                      <p className="text-xs text-orange-400 mt-2 flex items-center gap-1 hover:text-orange-300">
                        Требуют внимания
                        <ArrowRight className="h-3 w-3" />
                      </p>
                    </Link>
                  </div>
                  <div className="h-16 w-16 rounded-2xl bg-orange-600/20 flex items-center justify-center">
                    <Zap className="h-8 w-8 text-orange-400" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Recent Leads & Warm Leads */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Recent Leads */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5 text-indigo-400" />
                Последние лиды
              </CardTitle>
              <Link href="/leads">
                <Button variant="ghost" size="sm" className="gap-1">
                  Все лиды
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {leadsLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5].map((i) => (
                    <Skeleton key={i} className="h-16" />
                  ))}
                </div>
              ) : leads?.items.length ? (
                <div className="space-y-3">
                  {leads.items.map((lead) => (
                    <Link
                      key={lead.id}
                      href={`/leads/${lead.id}`}
                      className="flex items-center gap-4 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50 hover:border-indigo-500/50 transition-all group"
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-700/50 group-hover:bg-indigo-600/20 transition-colors">
                        <Building2 className="h-5 w-5 text-zinc-400 group-hover:text-indigo-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-zinc-200 truncate group-hover:text-indigo-400 transition-colors">
                          {lead.company_name}
                        </p>
                        <p className="text-xs text-zinc-500">
                          {lead.industry} • {lead.city}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex items-center gap-1 text-amber-400">
                          <Star className="h-4 w-4 fill-current" />
                          <span className="text-sm font-medium">{lead.score}</span>
                        </div>
                        <StatusBadge status={lead.status} />
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Users className="h-12 w-12 text-zinc-600 mb-4" />
                  <p className="text-zinc-400">Лидов пока нет</p>
                  <Button
                    variant="outline"
                    className="mt-4"
                    onClick={() => setDiscoveryOpen(true)}
                  >
                    <Rocket className="mr-2 h-4 w-4" />
                    Запустить Discovery
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Warm Leads */}
          <Card className="border-orange-600/30">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-orange-400" />
                Тёплые лиды
                {warmLeads > 0 && (
                  <Badge variant="warning">{warmLeads} новых</Badge>
                )}
              </CardTitle>
              <Link href="/handoffs">
                <Button variant="ghost" size="sm" className="gap-1">
                  Все
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
            </CardHeader>
            <CardContent>
              {handoffs?.length ? (
                <div className="space-y-3">
                  {handoffs.slice(0, 5).map((handoff) => (
                    <Link
                      key={handoff.id}
                      href={`/leads/${handoff.lead_id}`}
                      className="flex items-center gap-4 p-3 rounded-lg bg-orange-600/10 border border-orange-500/30 hover:border-orange-500/50 transition-all group"
                    >
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-orange-600/20">
                        <CheckCircle className="h-5 w-5 text-orange-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-zinc-200 truncate">
                          {handoff.company_name}
                        </p>
                        <p className="text-xs text-zinc-400">
                          {handoff.contact_name} • {handoff.contact_email}
                        </p>
                      </div>
                      <Badge
                        variant={
                          handoff.interest_level === "HIGH"
                            ? "success"
                            : handoff.interest_level === "MEDIUM"
                            ? "warning"
                            : "secondary"
                        }
                      >
                        {handoff.interest_level === "HIGH"
                          ? "Высокий"
                          : handoff.interest_level === "MEDIUM"
                          ? "Средний"
                          : "Низкий"}
                      </Badge>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Zap className="h-12 w-12 text-zinc-600 mb-4" />
                  <p className="text-zinc-400">Тёплых лидов пока нет</p>
                  <p className="text-xs text-zinc-500 mt-1">
                    Они появятся после запуска рассылки
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions Footer */}
        <Card className="bg-gradient-to-r from-zinc-900 to-zinc-800/50">
          <CardContent className="py-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <h3 className="text-lg font-semibold text-zinc-100">
                  Готовы к следующему шагу?
                </h3>
                <p className="text-sm text-zinc-400">
                  Выберите действие для продолжения работы
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Button
                  variant="outline"
                  onClick={() => setDiscoveryOpen(true)}
                  className="gap-2"
                >
                  <Rocket className="h-4 w-4" />
                  Найти лидов
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setCampaignOpen(true)}
                  className="gap-2"
                >
                  <Mail className="h-4 w-4" />
                  Запустить рассылку
                </Button>
                <Link href="/analytics">
                  <Button variant="outline" className="gap-2">
                    <BarChart3 className="h-4 w-4" />
                    Аналитика
                  </Button>
                </Link>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Modals */}
      <DiscoveryModal open={discoveryOpen} onOpenChange={setDiscoveryOpen} />
      <CampaignModal open={campaignOpen} onOpenChange={setCampaignOpen} />
    </div>
  )
}

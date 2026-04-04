"use client"

import { useQuery } from "@tanstack/react-query"
import { Header } from "@/components/header"
import { KPICard } from "@/components/kpi-card"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { FunnelChart } from "@/components/charts/funnel-chart"
import { EmailPerformanceChart } from "@/components/charts/email-performance-chart"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { formatNumber, formatCurrency, formatPercent } from "@/lib/utils"
import {
  Users,
  Mail,
  TrendingUp,
  DollarSign,
  Target,
  BarChart3,
  PieChart,
  Zap,
} from "lucide-react"

export default function AnalyticsPage() {
  const { data: funnel, isLoading: funnelLoading } = useQuery({
    queryKey: ["funnel"],
    queryFn: api.getFunnel,
  })

  const { data: emailPerf, isLoading: emailLoading } = useQuery({
    queryKey: ["email-performance"],
    queryFn: api.getEmailPerformance,
  })

  const { data: costs, isLoading: costsLoading } = useQuery({
    queryKey: ["costs"],
    queryFn: api.getCosts,
  })

  // Calculate metrics
  const totalLeads = funnel?.reduce((sum, item) => sum + item.count, 0) || 0
  const convertedLeads =
    funnel?.find((f) => f.status === "CONVERTED")?.count || 0
  const conversionRate = totalLeads > 0 ? (convertedLeads / totalLeads) * 100 : 0

  const openRate =
    emailPerf && emailPerf.sent > 0
      ? (emailPerf.opened / emailPerf.sent) * 100
      : 0
  const replyRate =
    emailPerf && emailPerf.sent > 0
      ? (emailPerf.replied / emailPerf.sent) * 100
      : 0

  return (
    <div className="min-h-screen">
      <Header
        title="Аналитика"
        description="Детальная статистика и метрики"
      />

      <div className="p-6 space-y-6">
        {/* KPI Cards */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <KPICard
            title="Всего лидов"
            value={formatNumber(totalLeads)}
            change={12}
            changeLabel="за неделю"
            icon={Users}
            gradient="indigo"
          />
          <KPICard
            title="Конверсия"
            value={formatPercent(conversionRate)}
            change={5}
            changeLabel="за неделю"
            icon={Target}
            gradient="emerald"
          />
          <KPICard
            title="Open Rate"
            value={formatPercent(openRate)}
            change={-2}
            changeLabel="за неделю"
            icon={Mail}
            gradient="orange"
          />
          <KPICard
            title="Reply Rate"
            value={formatPercent(replyRate)}
            change={8}
            changeLabel="за неделю"
            icon={TrendingUp}
            gradient="rose"
          />
        </div>

        {/* Charts */}
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Funnel Chart */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5 text-indigo-400" />
                Воронка по статусам
              </CardTitle>
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

          {/* Email Performance */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-indigo-400" />
                Email метрики
              </CardTitle>
            </CardHeader>
            <CardContent>
              {emailLoading ? (
                <Skeleton className="h-[300px]" />
              ) : emailPerf ? (
                <EmailPerformanceChart data={emailPerf} />
              ) : (
                <div className="flex h-[300px] items-center justify-center text-zinc-500">
                  Нет данных
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Cost Analytics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-indigo-400" />
              Расходы на LLM
            </CardTitle>
          </CardHeader>
          <CardContent>
            {costsLoading ? (
              <div className="grid gap-4 md:grid-cols-4">
                {[1, 2, 3, 4].map((i) => (
                  <Skeleton key={i} className="h-28" />
                ))}
              </div>
            ) : costs ? (
              <div className="grid gap-4 md:grid-cols-4">
                <div className="rounded-xl bg-gradient-to-br from-indigo-600/20 to-indigo-600/5 p-4 border border-indigo-600/20">
                  <div className="flex items-center gap-2 mb-2">
                    <DollarSign className="h-5 w-5 text-indigo-400" />
                    <span className="text-sm text-zinc-400">Общие расходы</span>
                  </div>
                  <p className="text-3xl font-bold text-zinc-100">
                    {formatCurrency(costs.total_cost)}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    Период: {costs.period}
                  </p>
                </div>

                <div className="rounded-xl bg-gradient-to-br from-emerald-600/20 to-emerald-600/5 p-4 border border-emerald-600/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Users className="h-5 w-5 text-emerald-400" />
                    <span className="text-sm text-zinc-400">
                      Стоимость лида
                    </span>
                  </div>
                  <p className="text-3xl font-bold text-zinc-100">
                    {formatCurrency(costs.cost_per_lead)}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    За каждого найденного
                  </p>
                </div>

                <div className="rounded-xl bg-gradient-to-br from-orange-600/20 to-orange-600/5 p-4 border border-orange-600/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="h-5 w-5 text-orange-400" />
                    <span className="text-sm text-zinc-400">
                      Стоимость тёплого
                    </span>
                  </div>
                  <p className="text-3xl font-bold text-zinc-100">
                    {formatCurrency(costs.cost_per_warm_lead)}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    Готового к передаче
                  </p>
                </div>

                <div className="rounded-xl bg-gradient-to-br from-rose-600/20 to-rose-600/5 p-4 border border-rose-600/20">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="h-5 w-5 text-rose-400" />
                    <span className="text-sm text-zinc-400">LLM вызовов</span>
                  </div>
                  <p className="text-3xl font-bold text-zinc-100">
                    {formatNumber(costs.llm_calls)}
                  </p>
                  <p className="mt-1 text-xs text-zinc-500">
                    За выбранный период
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex h-28 items-center justify-center text-zinc-500">
                Нет данных
              </div>
            )}
          </CardContent>
        </Card>

        {/* Email Stats Details */}
        {emailPerf && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PieChart className="h-5 w-5 text-indigo-400" />
                Детальная статистика email
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-6">
                <div className="text-center p-4 rounded-lg bg-zinc-800/50">
                  <p className="text-3xl font-bold text-indigo-400">
                    {formatNumber(emailPerf.sent)}
                  </p>
                  <p className="mt-1 text-sm text-zinc-400">Отправлено</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-zinc-800/50">
                  <p className="text-3xl font-bold text-violet-400">
                    {formatNumber(emailPerf.delivered)}
                  </p>
                  <p className="mt-1 text-sm text-zinc-400">Доставлено</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-zinc-800/50">
                  <p className="text-3xl font-bold text-emerald-400">
                    {formatNumber(emailPerf.opened)}
                  </p>
                  <p className="mt-1 text-sm text-zinc-400">Открыто</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-zinc-800/50">
                  <p className="text-3xl font-bold text-orange-400">
                    {formatNumber(emailPerf.clicked)}
                  </p>
                  <p className="mt-1 text-sm text-zinc-400">Кликов</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-zinc-800/50">
                  <p className="text-3xl font-bold text-amber-400">
                    {formatNumber(emailPerf.replied)}
                  </p>
                  <p className="mt-1 text-sm text-zinc-400">Ответов</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-zinc-800/50">
                  <p className="text-3xl font-bold text-red-400">
                    {formatNumber(emailPerf.bounced)}
                  </p>
                  <p className="mt-1 text-sm text-zinc-400">Отказов</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

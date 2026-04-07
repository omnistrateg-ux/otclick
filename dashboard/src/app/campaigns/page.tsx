"use client"

import { useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { CampaignModal } from "@/components/campaign-modal"
import { api, Campaign } from "@/lib/api"
import { formatDate } from "@/lib/utils"
import {
  Plus,
  Mail,
  Users,
  Play,
  Pause,
  CheckCircle,
  TrendingUp,
  Clock,
  BarChart3,
  FileText,
} from "lucide-react"

export default function CampaignsPage() {
  const [campaignOpen, setCampaignOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: campaigns, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: api.getCampaigns,
  })

  const activeCampaigns = campaigns?.filter((c) => c.status === "active") || []
  const totalDiscovered = campaigns?.reduce((sum, c) => sum + c.leads_discovered, 0) || 0
  const totalQualified = campaigns?.reduce((sum, c) => sum + c.leads_qualified, 0) || 0
  const totalConverted = campaigns?.reduce((sum, c) => sum + c.leads_converted, 0) || 0

  const handleCampaignCreated = () => {
    queryClient.invalidateQueries({ queryKey: ["campaigns"] })
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="border-b border-zinc-800 bg-zinc-950">
        <div className="px-6 py-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold text-zinc-100">Кампании</h1>
              <p className="text-sm text-zinc-500">
                Управление email-рассылками
              </p>
            </div>
            <Button
              onClick={() => setCampaignOpen(true)}
              className="gap-2 bg-gradient-to-r from-indigo-600 to-indigo-500"
            >
              <Plus className="h-4 w-4" />
              Создать кампанию
            </Button>
          </div>

          {/* Stats */}
          <div className="grid gap-4 md:grid-cols-4">
            <div className="p-4 rounded-xl bg-gradient-to-br from-indigo-600/20 to-indigo-600/5 border border-indigo-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Активные</p>
                  <p className="text-3xl font-bold text-indigo-400 mt-1">
                    {activeCampaigns.length}
                  </p>
                </div>
                <Play className="h-8 w-8 text-indigo-400/50" />
              </div>
            </div>

            <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-600/20 to-emerald-600/5 border border-emerald-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Найдено</p>
                  <p className="text-3xl font-bold text-emerald-400 mt-1">
                    {totalDiscovered}
                  </p>
                </div>
                <Users className="h-8 w-8 text-emerald-400/50" />
              </div>
            </div>

            <div className="p-4 rounded-xl bg-gradient-to-br from-amber-600/20 to-amber-600/5 border border-amber-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Квалифицировано</p>
                  <p className="text-3xl font-bold text-amber-400 mt-1">
                    {totalQualified}
                  </p>
                </div>
                <CheckCircle className="h-8 w-8 text-amber-400/50" />
              </div>
            </div>

            <div className="p-4 rounded-xl bg-gradient-to-br from-orange-600/20 to-orange-600/5 border border-orange-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Конвертировано</p>
                  <p className="text-3xl font-bold text-orange-400 mt-1">
                    {totalConverted}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-orange-400/50" />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
        {isLoading ? (
          <div className="grid gap-6 md:grid-cols-2">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-64" />
            ))}
          </div>
        ) : campaigns && campaigns.length > 0 ? (
          <div className="grid gap-6 md:grid-cols-2">
            {campaigns.map((campaign) => (
              <Card
                key={campaign.id}
                className={`group transition-all hover:shadow-xl ${
                  campaign.status === "active"
                    ? "border-emerald-500/30 hover:border-emerald-500/50"
                    : campaign.status === "paused"
                    ? "border-amber-500/30 hover:border-amber-500/50"
                    : "border-zinc-700 hover:border-zinc-600"
                }`}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <CardTitle className="text-lg truncate">
                          {campaign.name}
                        </CardTitle>
                        {campaign.status === "active" && (
                          <span className="relative flex h-2 w-2">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                          </span>
                        )}
                      </div>
                      {campaign.industries.length > 0 && (
                        <p className="text-sm text-zinc-500 truncate">
                          {campaign.industries.join(", ")}
                        </p>
                      )}
                      {campaign.regions.length > 0 && (
                        <p className="text-xs text-zinc-600 truncate">
                          {campaign.regions.join(", ")}
                        </p>
                      )}
                    </div>
                    <Badge
                      variant={
                        campaign.status === "active"
                          ? "success"
                          : campaign.status === "paused"
                          ? "warning"
                          : campaign.status === "draft"
                          ? "secondary"
                          : "secondary"
                      }
                      className="ml-2"
                    >
                      {campaign.status === "active" && (
                        <Play className="h-3 w-3 mr-1" />
                      )}
                      {campaign.status === "paused" && (
                        <Pause className="h-3 w-3 mr-1" />
                      )}
                      {campaign.status === "draft" && (
                        <FileText className="h-3 w-3 mr-1" />
                      )}
                      {campaign.status === "completed" && (
                        <CheckCircle className="h-3 w-3 mr-1" />
                      )}
                      {campaign.status === "active"
                        ? "Активна"
                        : campaign.status === "paused"
                        ? "Пауза"
                        : campaign.status === "draft"
                        ? "Черновик"
                        : "Завершена"}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-4">
                  {/* Metrics Grid */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="text-center p-2 rounded-lg bg-zinc-800/50">
                      <div className="flex items-center justify-center gap-1 text-zinc-400 mb-1">
                        <Users className="h-3 w-3" />
                        <span className="text-xs">Найдено</span>
                      </div>
                      <p className="text-lg font-bold text-zinc-200">
                        {campaign.leads_discovered}
                      </p>
                    </div>
                    <div className="text-center p-2 rounded-lg bg-zinc-800/50">
                      <div className="flex items-center justify-center gap-1 text-zinc-400 mb-1">
                        <CheckCircle className="h-3 w-3" />
                        <span className="text-xs">Квалиф.</span>
                      </div>
                      <p className="text-lg font-bold text-emerald-400">
                        {campaign.leads_qualified}
                      </p>
                    </div>
                    <div className="text-center p-2 rounded-lg bg-zinc-800/50">
                      <div className="flex items-center justify-center gap-1 text-zinc-400 mb-1">
                        <TrendingUp className="h-3 w-3" />
                        <span className="text-xs">Конверт.</span>
                      </div>
                      <p className="text-lg font-bold text-amber-400">
                        {campaign.leads_converted}
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center justify-between pt-3 border-t border-zinc-800">
                    <span className="text-xs text-zinc-500 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDate(campaign.created_at)}
                    </span>
                    <div className="flex items-center gap-1">
                      <Link href={`/campaigns/${campaign.id}`}>
                        <Button variant="ghost" size="sm" className="gap-1">
                          <BarChart3 className="h-4 w-4" />
                          Подробнее
                        </Button>
                      </Link>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          /* Empty State */
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16">
              <div className="h-20 w-20 rounded-full bg-zinc-800 flex items-center justify-center mb-4">
                <Mail className="h-10 w-10 text-zinc-600" />
              </div>
              <h3 className="text-lg font-semibold text-zinc-200 mb-2">
                Нет кампаний
              </h3>
              <p className="text-zinc-500 text-center max-w-md mb-6">
                Создайте первую email-кампанию для отправки писем квалифицированным лидам
              </p>
              <Button onClick={() => setCampaignOpen(true)} className="gap-2">
                <Plus className="h-4 w-4" />
                Создать кампанию
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Tips */}
        {campaigns && campaigns.length > 0 && (
          <Card className="mt-6 border-indigo-600/20 bg-indigo-600/5">
            <CardContent className="py-4">
              <div className="flex items-start gap-3">
                <TrendingUp className="h-5 w-5 text-indigo-400 mt-0.5" />
                <div>
                  <h4 className="font-medium text-zinc-200">
                    Советы по улучшению показателей
                  </h4>
                  <ul className="mt-2 space-y-1 text-sm text-zinc-400">
                    <li>
                      • <strong>Open Rate {"<"} 20%:</strong> Попробуйте улучшить тему письма
                    </li>
                    <li>
                      • <strong>Reply Rate {"<"} 5%:</strong> Персонализируйте содержание под отрасль
                    </li>
                    <li>
                      • Лучшее время отправки: Вторник-Четверг, 10:00-14:00
                    </li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Campaign Modal */}
      <CampaignModal open={campaignOpen} onOpenChange={setCampaignOpen} />
    </div>
  )
}

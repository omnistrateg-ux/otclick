"use client"

import { use } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { Header } from "@/components/header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { formatDate, formatNumber } from "@/lib/utils"
import {
  ArrowLeft,
  Mail,
  Users,
  CheckCircle,
  TrendingUp,
  Play,
  Pause,
  Settings,
  BarChart3,
  FileText,
} from "lucide-react"

export default function CampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)

  const { data: campaign, isLoading } = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => api.getCampaign(id),
  })

  if (isLoading) {
    return (
      <div className="min-h-screen">
        <Header title="Загрузка..." />
        <div className="p-6 space-y-6">
          <Skeleton className="h-40" />
          <Skeleton className="h-60" />
        </div>
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="min-h-screen">
        <Header title="Кампания не найдена" />
        <div className="p-6">
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <p className="text-zinc-500">Кампания с ID {id} не найдена</p>
              <Link href="/campaigns">
                <Button variant="outline" className="mt-4">
                  <ArrowLeft className="mr-2 h-4 w-4" />
                  Вернуться к списку
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    )
  }

  const conversionRate = campaign.leads_discovered > 0
    ? (campaign.leads_converted / campaign.leads_discovered) * 100
    : 0

  return (
    <div className="min-h-screen">
      <Header
        title={campaign.name}
        description={campaign.description || "Email-кампания"}
      />

      <div className="p-6 space-y-6">
        {/* Back button & Actions */}
        <div className="flex items-center justify-between">
          <Link href="/campaigns">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Назад к списку
            </Button>
          </Link>
          <div className="flex gap-2">
            {campaign.status === "active" ? (
              <Button variant="outline">
                <Pause className="mr-2 h-4 w-4" />
                Приостановить
              </Button>
            ) : campaign.status === "paused" ? (
              <Button variant="outline">
                <Play className="mr-2 h-4 w-4" />
                Возобновить
              </Button>
            ) : campaign.status === "draft" ? (
              <Button variant="outline">
                <Play className="mr-2 h-4 w-4" />
                Запустить
              </Button>
            ) : null}
            <Button variant="outline">
              <Settings className="mr-2 h-4 w-4" />
              Настройки
            </Button>
          </div>
        </div>

        {/* Campaign Header Card */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600/20 to-orange-500/20">
                  <Mail className="h-8 w-8 text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-zinc-100">
                    {campaign.name}
                  </h2>
                  <div className="mt-1 flex items-center gap-2">
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
                    >
                      {campaign.status === "active" && <Play className="h-3 w-3 mr-1" />}
                      {campaign.status === "paused" && <Pause className="h-3 w-3 mr-1" />}
                      {campaign.status === "draft" && <FileText className="h-3 w-3 mr-1" />}
                      {campaign.status === "active"
                        ? "Активна"
                        : campaign.status === "paused"
                        ? "Пауза"
                        : campaign.status === "draft"
                        ? "Черновик"
                        : "Завершена"}
                    </Badge>
                    <span className="text-sm text-zinc-500">
                      Создана {formatDate(campaign.created_at)}
                    </span>
                  </div>
                  {(campaign.industries?.length > 0 || campaign.regions?.length > 0) && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {campaign.industries?.map((ind) => (
                        <Badge key={ind} variant="outline" className="text-xs">
                          {ind}
                        </Badge>
                      ))}
                      {campaign.regions?.map((reg) => (
                        <Badge key={reg} variant="outline" className="text-xs">
                          {reg}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stats Grid */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <Card className="bg-gradient-to-br from-indigo-600/20 to-indigo-600/5 border-indigo-600/20">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Найдено</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {formatNumber(campaign.leads_discovered)}
                  </p>
                </div>
                <Users className="h-8 w-8 text-indigo-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-emerald-600/20 to-emerald-600/5 border-emerald-600/20">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Квалифицировано</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {formatNumber(campaign.leads_qualified)}
                  </p>
                </div>
                <CheckCircle className="h-8 w-8 text-emerald-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-orange-600/20 to-orange-600/5 border-orange-600/20">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Конвертировано</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {formatNumber(campaign.leads_converted)}
                  </p>
                </div>
                <TrendingUp className="h-8 w-8 text-orange-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-amber-600/20 to-amber-600/5 border-amber-600/20">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Конверсия</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {conversionRate.toFixed(1)}%
                  </p>
                </div>
                <BarChart3 className="h-8 w-8 text-amber-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Performance Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-indigo-400" />
              Воронка кампании
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-zinc-400">Найдено → Квалифицировано</span>
                <span className="text-zinc-200">
                  {campaign.leads_qualified} / {campaign.leads_discovered} (
                  {campaign.leads_discovered > 0
                    ? Math.round((campaign.leads_qualified / campaign.leads_discovered) * 100)
                    : 0}
                  %)
                </span>
              </div>
              <Progress
                value={
                  campaign.leads_discovered > 0
                    ? (campaign.leads_qualified / campaign.leads_discovered) * 100
                    : 0
                }
              />
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-zinc-400">Квалифицировано → Конвертировано</span>
                <span className="text-zinc-200">
                  {campaign.leads_converted} / {campaign.leads_qualified} (
                  {campaign.leads_qualified > 0
                    ? Math.round((campaign.leads_converted / campaign.leads_qualified) * 100)
                    : 0}
                  %)
                </span>
              </div>
              <Progress
                value={
                  campaign.leads_qualified > 0
                    ? (campaign.leads_converted / campaign.leads_qualified) * 100
                    : 0
                }
              />
            </div>

            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-zinc-400">Общая конверсия</span>
                <span className="text-zinc-200">{conversionRate.toFixed(1)}%</span>
              </div>
              <Progress value={conversionRate} />
            </div>
          </CardContent>
        </Card>

        {/* Tips */}
        <Card className="border-indigo-600/20 bg-indigo-600/5">
          <CardContent className="pt-6">
            <h3 className="font-medium text-indigo-400 mb-2">
              Статус кампании
            </h3>
            <ul className="space-y-2 text-sm text-zinc-400">
              {campaign.leads_discovered === 0 && (
                <li>• Лиды ещё не найдены — запустите Discovery</li>
              )}
              {campaign.leads_discovered > 0 && campaign.leads_qualified === 0 && (
                <li>• Лиды найдены, но не квалифицированы — запустите обогащение и скоринг</li>
              )}
              {campaign.leads_qualified > 0 && campaign.leads_converted === 0 && (
                <li>• Есть квалифицированные лиды — запустите outreach</li>
              )}
              {campaign.leads_converted > 0 && (
                <li>• Отличные результаты! Есть конвертированные лиды</li>
              )}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

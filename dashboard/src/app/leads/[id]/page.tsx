"use client"

import { use } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { Header } from "@/components/header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { StatusBadge } from "@/components/status-badge"
import { LeadTimeline } from "@/components/lead-timeline"
import { ScoreBreakdown } from "@/components/charts/score-breakdown"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { formatDate, formatDateTime } from "@/lib/utils"
import {
  ArrowLeft,
  Building2,
  MapPin,
  Globe,
  Briefcase,
  User,
  Mail,
  Phone,
  Star,
  Send,
  ExternalLink,
} from "lucide-react"

export default function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = use(params)

  const { data: lead, isLoading } = useQuery({
    queryKey: ["lead", id],
    queryFn: () => api.getLead(id),
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

  if (!lead) {
    return (
      <div className="min-h-screen">
        <Header title="Лид не найден" />
        <div className="p-6">
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <p className="text-zinc-500">Лид с ID {id} не найден</p>
              <Link href="/leads">
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

  return (
    <div className="min-h-screen">
      <Header
        title={lead.company_name}
        description={`${lead.industry} • ${lead.city}`}
      />

      <div className="p-6 space-y-6">
        {/* Back button & Actions */}
        <div className="flex items-center justify-between">
          <Link href="/leads">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Назад к списку
            </Button>
          </Link>
          <div className="flex gap-2">
            <Button variant="outline">
              <Mail className="mr-2 h-4 w-4" />
              Написать письмо
            </Button>
            <Button>
              <Send className="mr-2 h-4 w-4" />
              Передать менеджеру
            </Button>
          </div>
        </div>

        {/* Main content grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left column - Company info */}
          <div className="space-y-6 lg:col-span-2">
            {/* Company Card */}
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600/20 to-orange-500/20">
                      <Building2 className="h-8 w-8 text-indigo-400" />
                    </div>
                    <div>
                      <CardTitle className="text-xl">
                        {lead.company_name}
                      </CardTitle>
                      <div className="mt-1 flex items-center gap-2">
                        <StatusBadge status={lead.status} />
                        <div className="flex items-center gap-1 text-amber-400">
                          <Star className="h-4 w-4 fill-current" />
                          <span className="font-medium">{lead.score}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="flex items-center gap-3 rounded-lg bg-zinc-800/50 p-3">
                    <Briefcase className="h-5 w-5 text-zinc-500" />
                    <div>
                      <p className="text-xs text-zinc-500">Отрасль</p>
                      <p className="font-medium text-zinc-200">{lead.industry}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 rounded-lg bg-zinc-800/50 p-3">
                    <MapPin className="h-5 w-5 text-zinc-500" />
                    <div>
                      <p className="text-xs text-zinc-500">Город</p>
                      <p className="font-medium text-zinc-200">{lead.city}</p>
                    </div>
                  </div>
                  {lead.website && (
                    <div className="flex items-center gap-3 rounded-lg bg-zinc-800/50 p-3">
                      <Globe className="h-5 w-5 text-zinc-500" />
                      <div>
                        <p className="text-xs text-zinc-500">Сайт</p>
                        <a
                          href={lead.website}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 font-medium text-indigo-400 hover:text-indigo-300"
                        >
                          {lead.website}
                          <ExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                    </div>
                  )}
                  {lead.vacancies_count !== undefined && (
                    <div className="flex items-center gap-3 rounded-lg bg-zinc-800/50 p-3">
                      <Briefcase className="h-5 w-5 text-zinc-500" />
                      <div>
                        <p className="text-xs text-zinc-500">Вакансий</p>
                        <p className="font-medium text-zinc-200">
                          {lead.vacancies_count}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Tabs for Timeline, Emails */}
            <Card>
              <Tabs defaultValue="timeline" className="w-full">
                <CardHeader>
                  <TabsList>
                    <TabsTrigger value="timeline">История</TabsTrigger>
                    <TabsTrigger value="emails">Письма</TabsTrigger>
                  </TabsList>
                </CardHeader>
                <CardContent>
                  <TabsContent value="timeline">
                    {lead.events?.length ? (
                      <LeadTimeline events={lead.events} />
                    ) : (
                      <p className="text-center text-zinc-500 py-8">
                        Нет событий
                      </p>
                    )}
                  </TabsContent>
                  <TabsContent value="emails">
                    {lead.emails?.length ? (
                      <div className="space-y-4">
                        {lead.emails.map((email) => (
                          <div
                            key={email.id}
                            className="rounded-lg border border-zinc-800 p-4"
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <p className="font-medium text-zinc-200">
                                  {email.subject}
                                </p>
                                <p className="mt-1 text-sm text-zinc-500">
                                  {email.sent_at
                                    ? `Отправлено: ${formatDateTime(email.sent_at)}`
                                    : "Черновик"}
                                </p>
                              </div>
                              <Badge
                                variant={
                                  email.status === "delivered"
                                    ? "success"
                                    : email.status === "opened"
                                    ? "default"
                                    : "secondary"
                                }
                              >
                                {email.status}
                              </Badge>
                            </div>
                            <p className="mt-3 text-sm text-zinc-400 line-clamp-3">
                              {email.body}
                            </p>
                            {email.opened_at && (
                              <p className="mt-2 text-xs text-emerald-400">
                                Открыто: {formatDateTime(email.opened_at)}
                              </p>
                            )}
                            {email.replied_at && (
                              <p className="mt-1 text-xs text-emerald-400">
                                Ответ: {formatDateTime(email.replied_at)}
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-center text-zinc-500 py-8">
                        Нет писем
                      </p>
                    )}
                  </TabsContent>
                </CardContent>
              </Tabs>
            </Card>
          </div>

          {/* Right column - Contacts & Score */}
          <div className="space-y-6">
            {/* Contacts */}
            <Card>
              <CardHeader>
                <CardTitle>Контакты</CardTitle>
              </CardHeader>
              <CardContent>
                {lead.contacts?.length ? (
                  <div className="space-y-4">
                    {lead.contacts.map((contact) => (
                      <div
                        key={contact.id}
                        className="rounded-lg border border-zinc-800 p-4"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600/20">
                            <User className="h-5 w-5 text-indigo-400" />
                          </div>
                          <div>
                            <p className="font-medium text-zinc-200">
                              {contact.name}
                            </p>
                            <p className="text-xs text-zinc-500">
                              {contact.role}
                            </p>
                          </div>
                        </div>
                        <div className="mt-3 space-y-2">
                          <a
                            href={`mailto:${contact.email}`}
                            className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300"
                          >
                            <Mail className="h-4 w-4" />
                            {contact.email}
                          </a>
                          {contact.phone && (
                            <a
                              href={`tel:${contact.phone}`}
                              className="flex items-center gap-2 text-sm text-indigo-400 hover:text-indigo-300"
                            >
                              <Phone className="h-4 w-4" />
                              {contact.phone}
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-center text-zinc-500 py-4">
                    Контакты не найдены
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Score Breakdown */}
            {lead.score_breakdown && (
              <Card>
                <CardHeader>
                  <CardTitle>Оценка Score</CardTitle>
                </CardHeader>
                <CardContent>
                  <ScoreBreakdown data={lead.score_breakdown} />
                  <div className="mt-4 space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">Активность найма</span>
                      <span className="text-zinc-200">
                        {lead.score_breakdown.hiring_intensity}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">Соответствие отрасли</span>
                      <span className="text-zinc-200">
                        {lead.score_breakdown.industry_fit}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">Качество контактов</span>
                      <span className="text-zinc-200">
                        {lead.score_breakdown.contact_quality}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-400">Размер компании</span>
                      <span className="text-zinc-200">
                        {lead.score_breakdown.company_size}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Meta info */}
            <Card>
              <CardContent className="pt-6">
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Создан</span>
                    <span className="text-zinc-300">
                      {formatDate(lead.created_at)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">Обновлён</span>
                    <span className="text-zinc-300">
                      {formatDate(lead.updated_at)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-500">ID</span>
                    <span className="font-mono text-xs text-zinc-500">
                      {lead.id.slice(0, 8)}...
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  )
}

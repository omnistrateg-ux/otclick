"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { StatusBadge } from "@/components/status-badge"
import { DiscoveryModal } from "@/components/discovery-modal"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { formatDate, formatNumber } from "@/lib/utils"
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Building2,
  MapPin,
  Star,
  Users,
  Rocket,
  X,
  SlidersHorizontal,
  Download,
  Mail,
  Calendar,
  Briefcase,
  TrendingUp,
} from "lucide-react"

const STATUSES = [
  { value: "all", label: "Все статусы" },
  { value: "LEAD_FOUND", label: "Найден" },
  { value: "ENRICHMENT_DONE", label: "Обогащён" },
  { value: "SCORED", label: "Оценён" },
  { value: "QUALIFIED", label: "Квалифицирован" },
  { value: "OUTREACH_SENT", label: "Письмо отправлено" },
  { value: "REPLY_RECEIVED", label: "Получен ответ" },
  { value: "INTEREST_DETECTED", label: "Интерес обнаружен" },
  { value: "HANDED_TO_MANAGER", label: "Передан менеджеру" },
]

const INDUSTRIES = [
  { value: "all", label: "Все отрасли" },
  { value: "it", label: "IT и Технологии" },
  { value: "retail", label: "Ритейл" },
  { value: "horeca", label: "HoReCa" },
  { value: "logistics", label: "Логистика" },
  { value: "manufacturing", label: "Производство" },
  { value: "finance", label: "Финансы" },
  { value: "healthcare", label: "Здравоохранение" },
]

const CITIES = [
  { value: "all", label: "Все города" },
  { value: "Москва", label: "Москва" },
  { value: "Санкт-Петербург", label: "Санкт-Петербург" },
  { value: "Новосибирск", label: "Новосибирск" },
  { value: "Екатеринбург", label: "Екатеринбург" },
  { value: "Казань", label: "Казань" },
]

function getScoreColor(score: number) {
  if (score >= 80) return "text-emerald-400"
  if (score >= 60) return "text-amber-400"
  if (score >= 40) return "text-orange-400"
  return "text-zinc-400"
}

function getScoreGradient(score: number) {
  if (score >= 80) return "from-emerald-600/20 to-emerald-600/5"
  if (score >= 60) return "from-amber-600/20 to-amber-600/5"
  if (score >= 40) return "from-orange-600/20 to-orange-600/5"
  return "from-zinc-700/20 to-zinc-700/5"
}

export default function LeadsPage() {
  const [discoveryOpen, setDiscoveryOpen] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("all")
  const [industry, setIndustry] = useState("all")
  const [city, setCity] = useState("all")
  const [scoreMin, setScoreMin] = useState(0)
  const [page, setPage] = useState(1)
  const [selectedLeads, setSelectedLeads] = useState<string[]>([])
  const limit = 12

  const { data, isLoading } = useQuery({
    queryKey: ["leads", { search, status, industry, city, scoreMin, page, limit }],
    queryFn: () =>
      api.getLeads({
        search: search || undefined,
        status: status !== "all" ? status : undefined,
        industry: industry !== "all" ? industry : undefined,
        city: city !== "all" ? city : undefined,
        score_min: scoreMin > 0 ? scoreMin : undefined,
        page,
        limit,
      }),
  })

  const activeFiltersCount = [
    status !== "all",
    industry !== "all",
    city !== "all",
    scoreMin > 0,
  ].filter(Boolean).length

  const clearFilters = () => {
    setStatus("all")
    setIndustry("all")
    setCity("all")
    setScoreMin(0)
    setSearch("")
  }

  const toggleLeadSelection = (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    setSelectedLeads((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  const selectAll = () => {
    if (data?.items) {
      setSelectedLeads(data.items.map((l) => l.id))
    }
  }

  const clearSelection = () => {
    setSelectedLeads([])
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Hero Header */}
      <div className="relative overflow-hidden border-b border-zinc-800">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/10 via-transparent to-orange-500/5" />
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-600/5 rounded-full blur-3xl" />

        <div className="relative px-4 sm:px-6 py-6 pt-16 lg:pt-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-zinc-100">База лидов</h1>
              <p className="text-zinc-400 mt-1 text-sm sm:text-base">
                Управление базой потенциальных клиентов
              </p>
            </div>
            <div className="flex items-center gap-2 sm:gap-3">
              <Button variant="outline" className="gap-2" size="sm">
                <Download className="h-4 w-4" />
                <span className="hidden sm:inline">Экспорт</span>
              </Button>
              <Button
                onClick={() => setDiscoveryOpen(true)}
                className="gap-2 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 shadow-lg shadow-indigo-500/25"
                size="sm"
              >
                <Rocket className="h-4 w-4" />
                Discovery
              </Button>
            </div>
          </div>

          {/* Search & Filters */}
          <div className="flex flex-col sm:flex-row flex-wrap gap-3">
            <div className="relative flex-1 min-w-0 sm:min-w-[240px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                placeholder="Поиск по компании..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 bg-zinc-900/50 border-zinc-700"
              />
            </div>

            <div className="flex flex-wrap gap-2 sm:gap-3">
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="w-[130px] sm:w-[160px] bg-zinc-900/50 border-zinc-700">
                  <SelectValue placeholder="Статус" />
                </SelectTrigger>
                <SelectContent>
                  {STATUSES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={industry} onValueChange={setIndustry}>
                <SelectTrigger className="w-[130px] sm:w-[160px] bg-zinc-900/50 border-zinc-700">
                  <SelectValue placeholder="Отрасль" />
                </SelectTrigger>
                <SelectContent>
                  {INDUSTRIES.map((i) => (
                    <SelectItem key={i.value} value={i.value}>
                      {i.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={city} onValueChange={setCity}>
                <SelectTrigger className="w-[130px] sm:w-[160px] bg-zinc-900/50 border-zinc-700">
                  <SelectValue placeholder="Город" />
                </SelectTrigger>
                <SelectContent>
                  {CITIES.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Button
                variant={showFilters ? "secondary" : "outline"}
                onClick={() => setShowFilters(!showFilters)}
                className="gap-2"
                size="sm"
              >
                <SlidersHorizontal className="h-4 w-4" />
                <span className="hidden sm:inline">Фильтры</span>
                {activeFiltersCount > 0 && (
                  <Badge variant="secondary" className="ml-1">
                    {activeFiltersCount}
                  </Badge>
                )}
              </Button>

              {activeFiltersCount > 0 && (
                <Button variant="ghost" onClick={clearFilters} className="gap-2" size="sm">
                  <X className="h-4 w-4" />
                  <span className="hidden sm:inline">Сбросить</span>
                </Button>
              )}
            </div>
          </div>

          {/* Extended Filters */}
          {showFilters && (
            <div className="mt-4 p-4 rounded-xl bg-zinc-900/50 border border-zinc-700">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label className="text-sm font-medium text-zinc-300 mb-2 block">
                    Минимальный Score: {scoreMin}
                  </label>
                  <Slider
                    value={scoreMin}
                    onValueChange={setScoreMin}
                    min={0}
                    max={100}
                  />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Selection Bar */}
        {selectedLeads.length > 0 && (
          <div className="px-6 py-3 bg-indigo-600/20 border-t border-indigo-500/30">
            <div className="flex items-center justify-between">
              <span className="text-sm text-indigo-300">
                Выбрано: {selectedLeads.length} лидов
              </span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" className="gap-2">
                  <Mail className="h-4 w-4" />
                  Добавить в рассылку
                </Button>
                <Button variant="ghost" size="sm" onClick={clearSelection}>
                  Отменить
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4 sm:p-6">
        {/* Stats Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-4">
            {data && (
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-indigo-400" />
                <span className="text-sm text-zinc-400">
                  Найдено: <strong className="text-zinc-200">{formatNumber(data.total)}</strong> лидов
                </span>
              </div>
            )}
            {selectedLeads.length === 0 && data?.items?.length ? (
              <Button variant="ghost" size="sm" onClick={selectAll}>
                Выбрать все
              </Button>
            ) : null}
          </div>
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <span>Страница {page}</span>
            {data && <span>из {data.pages || 1}</span>}
          </div>
        </div>

        {/* Leads Grid */}
        {isLoading ? (
          <div className="grid gap-4 sm:gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
              <Skeleton key={i} className="h-64 rounded-2xl" />
            ))}
          </div>
        ) : data?.items?.length ? (
          <>
            <div className="grid gap-4 sm:gap-6 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {data.items.map((lead) => {
                const isSelected = selectedLeads.includes(lead.id)

                return (
                  <Link key={lead.id} href={`/leads/${lead.id}`}>
                    <Card
                      className={`group relative overflow-hidden rounded-2xl border transition-all duration-300 hover:shadow-xl hover:shadow-indigo-500/10 hover:-translate-y-1 cursor-pointer h-full ${
                        isSelected
                          ? "border-indigo-500 bg-indigo-600/10"
                          : "border-zinc-800 bg-zinc-900/50 hover:border-indigo-500/50"
                      }`}
                    >
                      {/* Gradient Background */}
                      <div className={`absolute inset-0 bg-gradient-to-br ${getScoreGradient(lead.score)} opacity-50`} />

                      {/* Selection Checkbox */}
                      <div
                        onClick={(e) => toggleLeadSelection(e, lead.id)}
                        className={`absolute top-4 right-4 h-6 w-6 rounded-full border-2 flex items-center justify-center transition-all z-10 ${
                          isSelected
                            ? "border-indigo-500 bg-indigo-500"
                            : "border-zinc-600 hover:border-indigo-400 bg-zinc-900/80"
                        }`}
                      >
                        {isSelected && (
                          <svg
                            className="h-3 w-3 text-white"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={3}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        )}
                      </div>

                      <CardContent className="relative p-4 sm:p-5">
                        {/* Company Icon & Name */}
                        <div className="flex items-start gap-3 sm:gap-4 mb-4">
                          <div className="flex h-12 w-12 sm:h-14 sm:w-14 flex-shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600/20 to-orange-500/20 group-hover:from-indigo-600/30 group-hover:to-orange-500/30 transition-all">
                            <Building2 className="h-6 w-6 sm:h-7 sm:w-7 text-indigo-400" />
                          </div>
                          <div className="flex-1 min-w-0 pr-6">
                            <h3 className="font-bold text-base sm:text-lg text-zinc-100 break-words group-hover:text-indigo-400 transition-colors">
                              {lead.company_name}
                            </h3>
                            <StatusBadge status={lead.status} />
                          </div>
                        </div>

                        {/* Info Grid */}
                        <div className="space-y-2 sm:space-y-3 mb-4">
                          <div className="flex items-center gap-3 text-sm">
                            <div className="flex items-center justify-center h-8 w-8 flex-shrink-0 rounded-lg bg-zinc-800/50">
                              <Briefcase className="h-4 w-4 text-zinc-400" />
                            </div>
                            <span className="text-zinc-300 break-words">{lead.industry || "Не указано"}</span>
                          </div>
                          <div className="flex items-center gap-3 text-sm">
                            <div className="flex items-center justify-center h-8 w-8 flex-shrink-0 rounded-lg bg-zinc-800/50">
                              <MapPin className="h-4 w-4 text-zinc-400" />
                            </div>
                            <span className="text-zinc-300">{lead.city || "Не указан"}</span>
                          </div>
                          {lead.contacts?.[0] && (
                            <div className="flex items-center gap-3 text-sm">
                              <div className="flex items-center justify-center h-8 w-8 flex-shrink-0 rounded-lg bg-zinc-800/50">
                                <Users className="h-4 w-4 text-zinc-400" />
                              </div>
                              <span className="text-zinc-300 break-words">{lead.contacts[0].name}</span>
                            </div>
                          )}
                        </div>

                        {/* Footer */}
                        <div className="flex items-center justify-between pt-4 border-t border-zinc-800/50">
                          <div className="flex items-center gap-2">
                            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-zinc-800/50 ${getScoreColor(lead.score)}`}>
                              <Star className="h-4 w-4 fill-current" />
                              <span className="font-bold">{lead.score}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-1.5 text-xs text-zinc-500">
                            <Calendar className="h-3.5 w-3.5" />
                            {formatDate(lead.created_at)}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                )
              })}
            </div>

            {/* Pagination */}
            {(data.pages || 1) > 1 && (
              <div className="mt-8 flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="gap-1"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Назад
                </Button>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, data.pages || 1) }, (_, i) => {
                    const pageNum = i + 1
                    return (
                      <Button
                        key={pageNum}
                        variant={page === pageNum ? "default" : "ghost"}
                        size="sm"
                        onClick={() => setPage(pageNum)}
                        className={`w-10 ${page === pageNum ? "bg-indigo-600 hover:bg-indigo-500" : ""}`}
                      >
                        {pageNum}
                      </Button>
                    )
                  })}
                  {(data.pages || 1) > 5 && <span className="px-2 text-zinc-500">...</span>}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= (data.pages || 1)}
                  onClick={() => setPage((p) => p + 1)}
                  className="gap-1"
                >
                  Далее
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </>
        ) : (
          <Card className="border-zinc-800 bg-zinc-900/50">
            <CardContent className="flex flex-col items-center justify-center py-16">
              <div className="h-24 w-24 rounded-full bg-gradient-to-br from-indigo-600/20 to-orange-500/20 flex items-center justify-center mb-6">
                <Users className="h-12 w-12 text-zinc-500" />
              </div>
              <h3 className="text-xl font-semibold text-zinc-200 mb-2">
                Лиды не найдены
              </h3>
              <p className="text-zinc-500 text-center max-w-md mb-6">
                {search || activeFiltersCount > 0
                  ? "Попробуйте изменить параметры поиска или сбросить фильтры"
                  : "Запустите Discovery чтобы найти новых работодателей"}
              </p>
              {search || activeFiltersCount > 0 ? (
                <Button variant="outline" onClick={clearFilters} className="gap-2">
                  <X className="h-4 w-4" />
                  Сбросить фильтры
                </Button>
              ) : (
                <Button
                  onClick={() => setDiscoveryOpen(true)}
                  className="gap-2 bg-gradient-to-r from-indigo-600 to-indigo-500"
                >
                  <Rocket className="h-4 w-4" />
                  Запустить Discovery
                </Button>
              )}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Discovery Modal */}
      <DiscoveryModal open={discoveryOpen} onOpenChange={setDiscoveryOpen} />
    </div>
  )
}

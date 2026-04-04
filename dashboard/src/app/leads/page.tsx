"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
  Filter,
  Plus,
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
  ExternalLink,
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
  const limit = 20

  const { data, isLoading, refetch } = useQuery({
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

  const toggleLeadSelection = (id: string) => {
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
    <div className="min-h-screen">
      {/* Header */}
      <div className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur supports-[backdrop-filter]:bg-zinc-950/80">
        <div className="px-6 py-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-zinc-100">Лиды</h1>
              <p className="text-sm text-zinc-500">
                Управление базой потен��иальных клиентов
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="outline" className="gap-2">
                <Download className="h-4 w-4" />
                Экспорт
              </Button>
              <Button
                onClick={() => setDiscoveryOpen(true)}
                className="gap-2 bg-gradient-to-r from-indigo-600 to-indigo-500"
              >
                <Rocket className="h-4 w-4" />
                Discovery
              </Button>
            </div>
          </div>

          {/* Search & Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[240px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                placeholder="Поиск по названию компании..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>

            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="w-[160px]">
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
              <SelectTrigger className="w-[160px]">
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
              <SelectTrigger className="w-[160px]">
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
            >
              <SlidersHorizontal className="h-4 w-4" />
              Фильтры
              {activeFiltersCount > 0 && (
                <Badge variant="secondary" className="ml-1">
                  {activeFiltersCount}
                </Badge>
              )}
            </Button>

            {activeFiltersCount > 0 && (
              <Button variant="ghost" onClick={clearFilters} className="gap-2">
                <X className="h-4 w-4" />
                Сбросить
              </Button>
            )}
          </div>

          {/* Extended Filters */}
          {showFilters && (
            <div className="mt-4 p-4 rounded-lg bg-zinc-800/50 border border-zinc-700">
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
      <div className="p-6">
        {/* Stats Bar */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            {data && (
              <span className="text-sm text-zinc-400">
                Найдено: <strong className="text-zinc-200">{formatNumber(data.total)}</strong> лидов
              </span>
            )}
            {selectedLeads.length === 0 && data?.items.length ? (
              <Button variant="ghost" size="sm" onClick={selectAll}>
                Выбрать все
              </Button>
            ) : null}
          </div>
          <div className="flex items-center gap-2 text-sm text-zinc-500">
            <span>Страница {page}</span>
            {data && <span>из {data.pages}</span>}
          </div>
        </div>

        {/* Leads Grid */}
        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Skeleton key={i} className="h-48 rounded-xl" />
            ))}
          </div>
        ) : data?.items.length ? (
          <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {data.items.map((lead) => {
                const isSelected = selectedLeads.includes(lead.id)

                return (
                  <div
                    key={lead.id}
                    className={`group relative rounded-xl border p-4 transition-all cursor-pointer ${
                      isSelected
                        ? "border-indigo-500 bg-indigo-600/10"
                        : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700"
                    }`}
                    onClick={() => toggleLeadSelection(lead.id)}
                  >
                    {/* Selection indicator */}
                    <div
                      className={`absolute top-3 right-3 h-5 w-5 rounded-full border-2 flex items-center justify-center transition-all ${
                        isSelected
                          ? "border-indigo-500 bg-indigo-500"
                          : "border-zinc-600 group-hover:border-zinc-500"
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

                    {/* Company Header */}
                    <div className="flex items-start gap-3 mb-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-zinc-800 group-hover:bg-indigo-600/20 transition-colors">
                        <Building2 className="h-6 w-6 text-zinc-400 group-hover:text-indigo-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold text-zinc-100 truncate group-hover:text-indigo-400 transition-colors">
                          {lead.company_name}
                        </h3>
                        <div className="flex items-center gap-2 mt-1">
                          <StatusBadge status={lead.status} />
                        </div>
                      </div>
                    </div>

                    {/* Info */}
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center gap-2 text-zinc-400">
                        <Building2 className="h-4 w-4" />
                        {lead.industry}
                      </div>
                      <div className="flex items-center gap-2 text-zinc-400">
                        <MapPin className="h-4 w-4" />
                        {lead.city}
                      </div>
                      {lead.contacts[0] && (
                        <div className="flex items-center gap-2 text-zinc-400">
                          <Users className="h-4 w-4" />
                          {lead.contacts[0].name}
                        </div>
                      )}
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between mt-4 pt-3 border-t border-zinc-800">
                      <div className="flex items-center gap-1 text-amber-400">
                        <Star className="h-4 w-4 fill-current" />
                        <span className="font-semibold">{lead.score}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-500">
                          {formatDate(lead.created_at)}
                        </span>
                        <Link
                          href={`/leads/${lead.id}`}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <ExternalLink className="h-4 w-4" />
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Pagination */}
            {data.pages > 1 && (
              <div className="mt-6 flex items-center justify-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Назад
                </Button>
                <div className="flex items-center gap-1">
                  {Array.from({ length: Math.min(5, data.pages) }, (_, i) => {
                    const pageNum = i + 1
                    return (
                      <Button
                        key={pageNum}
                        variant={page === pageNum ? "default" : "ghost"}
                        size="sm"
                        onClick={() => setPage(pageNum)}
                        className="w-10"
                      >
                        {pageNum}
                      </Button>
                    )
                  })}
                  {data.pages > 5 && <span className="px-2 text-zinc-500">...</span>}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= data.pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Далее
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            )}
          </>
        ) : (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16">
              <div className="h-20 w-20 rounded-full bg-zinc-800 flex items-center justify-center mb-4">
                <Users className="h-10 w-10 text-zinc-600" />
              </div>
              <h3 className="text-lg font-semibold text-zinc-200 mb-2">
                Лиды не найдены
              </h3>
              <p className="text-zinc-500 text-center max-w-md mb-6">
                {search || activeFiltersCount > 0
                  ? "Попробуйте изменить параметры поиска или сбросить фильтры"
                  : "Запустите Discovery чтобы найти новых работодателей"}
              </p>
              {search || activeFiltersCount > 0 ? (
                <Button variant="outline" onClick={clearFilters}>
                  Сбросить фильтры
                </Button>
              ) : (
                <Button onClick={() => setDiscoveryOpen(true)} className="gap-2">
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

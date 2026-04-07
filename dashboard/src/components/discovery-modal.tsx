"use client"

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { api, DiscoverResponse } from "@/lib/api"
import {
  Rocket,
  Building2,
  MapPin,
  Users,
  Zap,
  CheckCircle,
  Loader2,
  AlertCircle,
  ExternalLink,
} from "lucide-react"

const INDUSTRIES = [
  { id: "retail", label: "Ритейл", icon: "🛒" },
  { id: "horeca", label: "Рестораны/Кафе", icon: "🍽️" },
  { id: "logistics", label: "Логистика", icon: "🚚" },
  { id: "warehouse", label: "Склад", icon: "📦" },
  { id: "construction", label: "Строительство", icon: "🏗️" },
  { id: "manufacturing", label: "Производство", icon: "🏭" },
  { id: "agriculture", label: "Агропром", icon: "🌾" },
]

const VACANCY_MAPPING: Record<string, string[]> = {
  retail: ["кассир", "продавец-кассир", "мерчандайзер"],
  horeca: ["повар", "официант", "бармен"],
  logistics: ["курьер", "водитель", "экспедитор"],
  warehouse: ["грузчик", "комплектовщик", "сборщик заказов"],
  construction: ["разнорабочий", "маляр", "штукатур"],
  manufacturing: ["оператор линии", "упаковщик", "сборщик", "наладчик"],
  agriculture: ["овощевод", "тепличный рабочий", "сборщик урожая"],
}

const CITIES = [
  "Москва",
  "Санкт-Петербург",
  "Новосибирск",
  "Екатеринбург",
  "Казань",
  "Нижний Новгород",
  "Челябинск",
  "Самара",
  "Ростов-на-Дону",
  "Уфа",
  "Красноярск",
  "Воронеж",
]

interface DiscoveryModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  campaignId?: string
}

export function DiscoveryModal({ open, onOpenChange, campaignId }: DiscoveryModalProps) {
  const [selectedIndustries, setSelectedIndustries] = useState<string[]>([])
  const [selectedVacancies, setSelectedVacancies] = useState<string[]>([])
  const [selectedCities, setSelectedCities] = useState<string[]>([])
  const [leadsCount, setLeadsCount] = useState(50)
  const [autoEnrich, setAutoEnrich] = useState(true)
  const [autoScore, setAutoScore] = useState(true)
  const [autoOutreach, setAutoOutreach] = useState(false)
  const [step, setStep] = useState<"config" | "loading" | "results" | "error">("config")
  const [result, setResult] = useState<DiscoverResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () =>
      api.discoverLeads({
        industry: selectedIndustries.join(",") || undefined,
        queries: selectedVacancies.length > 0 ? selectedVacancies : undefined,
        city: selectedCities.join(",") || undefined,
        max_leads: leadsCount,
        campaign_id: campaignId,
      }),
    onSuccess: (data) => {
      setResult(data)
      setStep("results")
      queryClient.invalidateQueries({ queryKey: ["leads"] })
      queryClient.invalidateQueries({ queryKey: ["funnel"] })
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Ошибка запуска Discovery")
      setStep("error")
    },
  })

  const toggleIndustry = (id: string) => {
    setSelectedIndustries((prev) => {
      const isRemoving = prev.includes(id)
      if (isRemoving) {
        // Remove vacancies for this industry
        const industryVacancies = VACANCY_MAPPING[id] || []
        setSelectedVacancies((v) => v.filter((vac) => !industryVacancies.includes(vac)))
        return prev.filter((i) => i !== id)
      } else {
        // Add all vacancies for this industry
        const industryVacancies = VACANCY_MAPPING[id] || []
        setSelectedVacancies((v) => [...new Set([...v, ...industryVacancies])])
        return [...prev, id]
      }
    })
  }

  const toggleVacancy = (vacancy: string) => {
    setSelectedVacancies((prev) =>
      prev.includes(vacancy) ? prev.filter((v) => v !== vacancy) : [...prev, vacancy]
    )
  }

  const toggleCity = (city: string) => {
    setSelectedCities((prev) =>
      prev.includes(city) ? prev.filter((c) => c !== city) : [...prev, city]
    )
  }

  const handleLaunch = () => {
    setStep("loading")
    setError(null)
    mutation.mutate()
  }

  const handleClose = () => {
    onOpenChange(false)
    setTimeout(() => {
      setStep("config")
      setResult(null)
      setError(null)
      setSelectedIndustries([])
      setSelectedVacancies([])
      setSelectedCities([])
      setLeadsCount(50)
    }, 300)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        {step === "config" && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-xl">
                <Rocket className="h-6 w-6 text-indigo-400" />
                Запуск Discovery
              </DialogTitle>
              <DialogDescription>
                Настройте параметры поиска новых работодателей
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-6 py-4">
              {/* Industries */}
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-3">
                  <Building2 className="h-4 w-4 text-indigo-400" />
                  Отрасли
                  {selectedIndustries.length > 0 && (
                    <Badge variant="secondary" className="ml-auto">
                      {selectedIndustries.length} выбрано
                    </Badge>
                  )}
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {INDUSTRIES.map((industry) => (
                    <button
                      key={industry.id}
                      onClick={() => toggleIndustry(industry.id)}
                      className={`flex items-center gap-2 p-3 rounded-lg border transition-all text-left ${
                        selectedIndustries.includes(industry.id)
                          ? "border-indigo-500 bg-indigo-500/20 text-indigo-300"
                          : "border-zinc-700 bg-zinc-800/50 text-zinc-300 hover:border-zinc-600"
                      }`}
                    >
                      <span className="text-lg">{industry.icon}</span>
                      <span className="text-sm font-medium">{industry.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Vacancies - shown when industries with vacancies are selected */}
              {selectedIndustries.some((ind) => VACANCY_MAPPING[ind]) && (
                <div>
                  <label className="text-sm font-medium text-zinc-300 mb-2 block">
                    Вакансии для поиска
                    {selectedVacancies.length > 0 && (
                      <Badge variant="secondary" className="ml-2">
                        {selectedVacancies.length} выбрано
                      </Badge>
                    )}
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {selectedIndustries
                      .flatMap((ind) => VACANCY_MAPPING[ind] || [])
                      .filter((v, i, arr) => arr.indexOf(v) === i)
                      .map((vacancy) => (
                        <label
                          key={vacancy}
                          className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all ${
                            selectedVacancies.includes(vacancy)
                              ? "border-indigo-500 bg-indigo-500/20"
                              : "border-zinc-700 bg-zinc-800/50 hover:border-zinc-600"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={selectedVacancies.includes(vacancy)}
                            onChange={() => toggleVacancy(vacancy)}
                            className="h-4 w-4 rounded border-zinc-600 bg-zinc-800 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-0"
                          />
                          <span className="text-sm text-zinc-300">{vacancy}</span>
                        </label>
                      ))}
                  </div>
                </div>
              )}

              {/* Cities */}
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-3">
                  <MapPin className="h-4 w-4 text-indigo-400" />
                  Города
                  {selectedCities.length > 0 && (
                    <Badge variant="secondary" className="ml-auto">
                      {selectedCities.length} выбрано
                    </Badge>
                  )}
                </label>
                <div className="flex flex-wrap gap-2">
                  {CITIES.map((city) => (
                    <button
                      key={city}
                      onClick={() => toggleCity(city)}
                      className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                        selectedCities.includes(city)
                          ? "bg-indigo-500 text-white"
                          : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                      }`}
                    >
                      {city}
                    </button>
                  ))}
                </div>
              </div>

              {/* Leads Count */}
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-3">
                  <Users className="h-4 w-4 text-indigo-400" />
                  Количество лидов
                  <span className="ml-auto text-2xl font-bold text-indigo-400">
                    {leadsCount}
                  </span>
                </label>
                <Slider
                  value={leadsCount}
                  onValueChange={setLeadsCount}
                  min={10}
                  max={500}
                />
                <div className="flex justify-between mt-2 text-xs text-zinc-500">
                  <span>10</span>
                  <span>250</span>
                  <span>500</span>
                </div>
              </div>

              {/* Automation Options */}
              <div className="space-y-4 p-4 rounded-lg bg-zinc-800/50 border border-zinc-700">
                <h4 className="flex items-center gap-2 text-sm font-medium text-zinc-300">
                  <Zap className="h-4 w-4 text-orange-400" />
                  Автоматизация
                </h4>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-300">Авто-обогащение</p>
                    <p className="text-xs text-zinc-500">
                      Автоматически искать контакты
                    </p>
                  </div>
                  <Switch checked={autoEnrich} onCheckedChange={setAutoEnrich} />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-300">Авто-скоринг</p>
                    <p className="text-xs text-zinc-500">
                      Оценивать лидов автоматически
                    </p>
                  </div>
                  <Switch checked={autoScore} onCheckedChange={setAutoScore} />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-300">Авто-рассылка</p>
                    <p className="text-xs text-zinc-500">
                      Отправлять письма квалифицированным
                    </p>
                  </div>
                  <Switch
                    checked={autoOutreach}
                    onCheckedChange={setAutoOutreach}
                  />
                </div>
              </div>

              {/* Cost Estimate */}
              <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-indigo-600/20 to-orange-500/20 border border-indigo-500/30">
                <div>
                  <p className="text-sm font-medium text-zinc-200">
                    Примерная стоимость
                  </p>
                  <p className="text-xs text-zinc-400">
                    {leadsCount} лидов × $0.05 за лида
                  </p>
                </div>
                <p className="text-2xl font-bold text-indigo-400">
                  ${(leadsCount * 0.05).toFixed(2)}
                </p>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>
                Отмена
              </Button>
              <Button
                onClick={handleLaunch}
                disabled={
                  selectedIndustries.length === 0 && selectedCities.length === 0
                }
                className="gap-2"
              >
                <Rocket className="h-4 w-4" />
                Запустить Discovery
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "loading" && (
          <div className="py-12 text-center">
            <div className="flex justify-center mb-6">
              <div className="relative">
                <div className="h-20 w-20 rounded-full bg-indigo-600/20 flex items-center justify-center">
                  <Loader2 className="h-10 w-10 text-indigo-400 animate-spin" />
                </div>
              </div>
            </div>
            <h3 className="text-xl font-semibold text-zinc-100 mb-2">
              Ищем работодателей...
            </h3>
            <p className="text-zinc-400">
              Это может занять несколько секунд
            </p>
          </div>
        )}

        {step === "results" && result && (
          <div className="py-6">
            <div className="flex justify-center mb-6">
              <div className="h-16 w-16 rounded-full bg-emerald-600/20 flex items-center justify-center">
                <CheckCircle className="h-8 w-8 text-emerald-400" />
              </div>
            </div>

            <h3 className="text-xl font-semibold text-zinc-100 mb-2 text-center">
              Discovery завершён
            </h3>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-4 my-6">
              <div className="p-4 rounded-lg bg-zinc-800/50 border border-zinc-700 text-center">
                <p className="text-3xl font-bold text-indigo-400">{result.leads_found}</p>
                <p className="text-sm text-zinc-400">Найдено</p>
              </div>
              <div className="p-4 rounded-lg bg-zinc-800/50 border border-zinc-700 text-center">
                <p className="text-3xl font-bold text-emerald-400">{result.leads_created}</p>
                <p className="text-sm text-zinc-400">Создано</p>
              </div>
            </div>

            {/* Companies list */}
            {result.companies && result.companies.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-zinc-300 mb-3">
                  Найденные компании ({result.companies.length})
                </h4>
                <div className="max-h-60 overflow-y-auto space-y-2">
                  {result.companies.map((company, idx) => (
                    <div
                      key={company.lead_id || idx}
                      className="flex items-center justify-between p-3 rounded-lg bg-zinc-800/50 border border-zinc-700"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <Building2 className="h-4 w-4 text-zinc-500 shrink-0" />
                        <div className="min-w-0">
                          <p className="font-medium text-zinc-200 truncate">
                            {company.name}
                          </p>
                          <p className="text-xs text-zinc-500 truncate">
                            {company.vacancy}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Badge
                          variant={company.status === "created" ? "success" : "secondary"}
                          className="text-xs"
                        >
                          {company.status === "created" ? "Новый" : "Существует"}
                        </Badge>
                        {company.lead_id && company.status === "created" && (
                          <Link
                            href={`/leads/${company.lead_id}`}
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
                              <ExternalLink className="h-3.5 w-3.5" />
                            </Button>
                          </Link>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-6 flex justify-center">
              <Button onClick={handleClose}>Закрыть</Button>
            </div>
          </div>
        )}

        {step === "error" && (
          <div className="py-12 text-center">
            <div className="flex justify-center mb-6">
              <div className="h-20 w-20 rounded-full bg-red-600/20 flex items-center justify-center">
                <AlertCircle className="h-10 w-10 text-red-400" />
              </div>
            </div>
            <h3 className="text-xl font-semibold text-zinc-100 mb-2">
              Ошибка
            </h3>
            <p className="text-zinc-400 mb-6">
              {error || "Не удалось запустить Discovery"}
            </p>
            <div className="flex justify-center gap-3">
              <Button variant="outline" onClick={handleClose}>
                Закрыть
              </Button>
              <Button onClick={() => setStep("config")}>
                Попробовать снова
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

"use client"

import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import {
  Rocket,
  Building2,
  MapPin,
  Users,
  Zap,
  AlertCircle,
  CheckCircle,
  Loader2,
} from "lucide-react"

const INDUSTRIES = [
  { id: "it", label: "IT и Технологии", icon: "💻" },
  { id: "retail", label: "Ритейл", icon: "🛒" },
  { id: "horeca", label: "HoReCa", icon: "🍽️" },
  { id: "logistics", label: "Логистика", icon: "🚚" },
  { id: "manufacturing", label: "Производство", icon: "🏭" },
  { id: "finance", label: "Финансы", icon: "💰" },
  { id: "healthcare", label: "Здравоохранение", icon: "🏥" },
  { id: "construction", label: "Строительство", icon: "🏗️" },
  { id: "education", label: "Образование", icon: "📚" },
  { id: "services", label: "Услуги", icon: "🛎️" },
]

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
}

export function DiscoveryModal({ open, onOpenChange }: DiscoveryModalProps) {
  const [selectedIndustries, setSelectedIndustries] = useState<string[]>([])
  const [selectedCities, setSelectedCities] = useState<string[]>([])
  const [leadsCount, setLeadsCount] = useState(50)
  const [autoEnrich, setAutoEnrich] = useState(true)
  const [autoScore, setAutoScore] = useState(true)
  const [autoOutreach, setAutoOutreach] = useState(false)
  const [step, setStep] = useState(1)

  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: () =>
      api.discoverLeads({
        industry: selectedIndustries.join(","),
        city: selectedCities.join(","),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] })
      queryClient.invalidateQueries({ queryKey: ["funnel"] })
      setStep(3)
    },
    onError: () => {
      setStep(1)
    },
  })

  const toggleIndustry = (id: string) => {
    setSelectedIndustries((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  const toggleCity = (city: string) => {
    setSelectedCities((prev) =>
      prev.includes(city) ? prev.filter((c) => c !== city) : [...prev, city]
    )
  }

  const handleLaunch = () => {
    setStep(2)
    mutation.mutate()
  }

  const handleClose = () => {
    onOpenChange(false)
    setTimeout(() => {
      setStep(1)
      setSelectedIndustries([])
      setSelectedCities([])
      setLeadsCount(50)
    }, 300)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        {step === 1 && (
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

        {step === 2 && (
          <div className="py-12 text-center">
            <div className="flex justify-center mb-6">
              <div className="relative">
                <div className="h-20 w-20 rounded-full bg-indigo-600/20 flex items-center justify-center">
                  <Loader2 className="h-10 w-10 text-indigo-400 animate-spin" />
                </div>
                <div className="absolute inset-0 rounded-full border-4 border-indigo-500/30 animate-ping" />
              </div>
            </div>
            <h3 className="text-xl font-semibold text-zinc-100 mb-2">
              Запускаем Discovery...
            </h3>
            <p className="text-zinc-400">
              Поиск работодателей по заданным критериям
            </p>
            <div className="mt-6 space-y-2 text-sm text-zinc-500">
              <p>Отрасли: {selectedIndustries.length}</p>
              <p>Города: {selectedCities.length}</p>
              <p>Цель: {leadsCount} лидов</p>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="py-12 text-center">
            <div className="flex justify-center mb-6">
              <div className="h-20 w-20 rounded-full bg-emerald-600/20 flex items-center justify-center">
                <CheckCircle className="h-10 w-10 text-emerald-400" />
              </div>
            </div>
            <h3 className="text-xl font-semibold text-zinc-100 mb-2">
              Discovery запущен!
            </h3>
            <p className="text-zinc-400 mb-6">
              Задача добавлена в очередь обработки
            </p>
            <Button onClick={handleClose}>Закрыть</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

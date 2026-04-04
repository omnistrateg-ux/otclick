"use client"

import { useState } from "react"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Mail,
  Clock,
  Users,
  Zap,
  CheckCircle,
  Loader2,
  Calendar,
  Settings,
} from "lucide-react"

interface CampaignModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const EMAIL_TEMPLATES = [
  { id: "intro", name: "Знакомство", description: "Первое касание с компанией" },
  { id: "followup", name: "Follow-up", description: "Напоминание о себе" },
  { id: "offer", name: "Коммерческое", description: "Предложение услуг" },
  { id: "case", name: "Кейс", description: "Успешный пример работы" },
]

export function CampaignModal({ open, onOpenChange }: CampaignModalProps) {
  const [step, setStep] = useState(1)
  const [name, setName] = useState("")
  const [template, setTemplate] = useState("")
  const [dailyLimit, setDailyLimit] = useState(50)
  const [delayHours, setDelayHours] = useState(24)
  const [trackOpens, setTrackOpens] = useState(true)
  const [trackClicks, setTrackClicks] = useState(true)
  const [autoFollowup, setAutoFollowup] = useState(true)
  const [isLaunching, setIsLaunching] = useState(false)

  const handleLaunch = () => {
    setIsLaunching(true)
    setTimeout(() => {
      setIsLaunching(false)
      setStep(2)
    }, 2000)
  }

  const handleClose = () => {
    onOpenChange(false)
    setTimeout(() => {
      setStep(1)
      setName("")
      setTemplate("")
    }, 300)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-2xl">
        {step === 1 && (
          <>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-xl">
                <Mail className="h-6 w-6 text-indigo-400" />
                Создать кампанию
              </DialogTitle>
              <DialogDescription>
                Настройте email-рассылку для квалифицированных лидов
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-6 py-4">
              {/* Campaign Name */}
              <div>
                <label className="text-sm font-medium text-zinc-300 mb-2 block">
                  Название кампании
                </label>
                <Input
                  placeholder="Например: IT компании Москвы - Апрель 2024"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>

              {/* Template Selection */}
              <div>
                <label className="text-sm font-medium text-zinc-300 mb-2 block">
                  Шаблон письма
                </label>
                <div className="grid grid-cols-2 gap-3">
                  {EMAIL_TEMPLATES.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setTemplate(t.id)}
                      className={`p-4 rounded-lg border text-left transition-all ${
                        template === t.id
                          ? "border-indigo-500 bg-indigo-500/20"
                          : "border-zinc-700 bg-zinc-800/50 hover:border-zinc-600"
                      }`}
                    >
                      <p className="font-medium text-zinc-200">{t.name}</p>
                      <p className="text-xs text-zinc-500 mt-1">{t.description}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Sending Settings */}
              <div className="space-y-4 p-4 rounded-lg bg-zinc-800/50 border border-zinc-700">
                <h4 className="flex items-center gap-2 text-sm font-medium text-zinc-300">
                  <Settings className="h-4 w-4 text-indigo-400" />
                  Настройки отправки
                </h4>

                {/* Daily Limit */}
                <div>
                  <div className="flex justify-between mb-2">
                    <span className="text-sm text-zinc-400">
                      Писем в день
                    </span>
                    <span className="text-lg font-bold text-indigo-400">
                      {dailyLimit}
                    </span>
                  </div>
                  <Slider
                    value={dailyLimit}
                    onValueChange={setDailyLimit}
                    min={10}
                    max={200}
                  />
                </div>

                {/* Delay Between Emails */}
                <div>
                  <label className="text-sm text-zinc-400 mb-2 block">
                    Задержка между письмами
                  </label>
                  <Select
                    value={String(delayHours)}
                    onValueChange={(v) => setDelayHours(Number(v))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="12">12 часов</SelectItem>
                      <SelectItem value="24">24 часа</SelectItem>
                      <SelectItem value="48">48 часов</SelectItem>
                      <SelectItem value="72">72 часа</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Tracking Options */}
              <div className="space-y-4 p-4 rounded-lg bg-zinc-800/50 border border-zinc-700">
                <h4 className="flex items-center gap-2 text-sm font-medium text-zinc-300">
                  <Zap className="h-4 w-4 text-orange-400" />
                  Трекинг и автоматизация
                </h4>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-300">Отслеживать открытия</p>
                    <p className="text-xs text-zinc-500">
                      Узнавать когда письмо открыто
                    </p>
                  </div>
                  <Switch checked={trackOpens} onCheckedChange={setTrackOpens} />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-300">Отслеживать клики</p>
                    <p className="text-xs text-zinc-500">
                      Узнавать когда кликнули по ссылке
                    </p>
                  </div>
                  <Switch
                    checked={trackClicks}
                    onCheckedChange={setTrackClicks}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-zinc-300">Авто follow-up</p>
                    <p className="text-xs text-zinc-500">
                      Отправлять повторное письмо если нет ответа
                    </p>
                  </div>
                  <Switch
                    checked={autoFollowup}
                    onCheckedChange={setAutoFollowup}
                  />
                </div>
              </div>

              {/* Summary */}
              <div className="flex items-center justify-between p-4 rounded-lg bg-gradient-to-r from-emerald-600/20 to-emerald-500/10 border border-emerald-500/30">
                <div className="flex items-center gap-3">
                  <Users className="h-5 w-5 text-emerald-400" />
                  <div>
                    <p className="text-sm font-medium text-zinc-200">
                      Доступно для рассылки
                    </p>
                    <p className="text-xs text-zinc-400">
                      Квалифицированные лиды с email
                    </p>
                  </div>
                </div>
                <p className="text-2xl font-bold text-emerald-400">247</p>
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={handleClose}>
                Отмена
              </Button>
              <Button
                onClick={handleLaunch}
                disabled={!name || !template || isLaunching}
                className="gap-2"
              >
                {isLaunching ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Mail className="h-4 w-4" />
                )}
                {isLaunching ? "Запускаем..." : "Запустить рассылку"}
              </Button>
            </DialogFooter>
          </>
        )}

        {step === 2 && (
          <div className="py-12 text-center">
            <div className="flex justify-center mb-6">
              <div className="h-20 w-20 rounded-full bg-emerald-600/20 flex items-center justify-center">
                <CheckCircle className="h-10 w-10 text-emerald-400" />
              </div>
            </div>
            <h3 className="text-xl font-semibold text-zinc-100 mb-2">
              Кампания запущена!
            </h3>
            <p className="text-zinc-400 mb-2">"{name}"</p>
            <p className="text-sm text-zinc-500 mb-6">
              Первые письма будут отправлены в ближайшие минуты
            </p>
            <div className="flex justify-center gap-3">
              <Button variant="outline" onClick={handleClose}>
                Закрыть
              </Button>
              <Button onClick={() => {
                handleClose()
                window.location.href = "/campaigns"
              }}>
                Перейти к кампаниям
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

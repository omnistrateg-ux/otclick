"use client"

import { Header } from "@/components/header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Settings,
  Key,
  Bell,
  Users,
  Mail,
  Globe,
  Shield,
  Database,
  RefreshCw,
} from "lucide-react"

export default function SettingsPage() {
  return (
    <div className="min-h-screen">
      <Header
        title="Настройки"
        description="Конфигурация системы"
      />

      <div className="p-6 space-y-6 max-w-4xl">
        {/* API Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Key className="h-5 w-5 text-indigo-400" />
              API Ключи
            </CardTitle>
            <CardDescription>
              Управление ключами для внешних сервисов
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-800/50">
              <div className="flex items-center gap-3">
                <Globe className="h-5 w-5 text-zinc-500" />
                <div>
                  <p className="font-medium text-zinc-200">OpenAI API</p>
                  <p className="text-sm text-zinc-500">GPT-4 для генерации писем</p>
                </div>
              </div>
              <Badge variant="success">Подключен</Badge>
            </div>

            <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-800/50">
              <div className="flex items-center gap-3">
                <Database className="h-5 w-5 text-zinc-500" />
                <div>
                  <p className="font-medium text-zinc-200">Hunter.io</p>
                  <p className="text-sm text-zinc-500">Поиск email-адресов</p>
                </div>
              </div>
              <Badge variant="success">Подключен</Badge>
            </div>

            <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-800/50">
              <div className="flex items-center gap-3">
                <Mail className="h-5 w-5 text-zinc-500" />
                <div>
                  <p className="font-medium text-zinc-200">SendGrid</p>
                  <p className="text-sm text-zinc-500">Отправка email</p>
                </div>
              </div>
              <Badge variant="success">Подключен</Badge>
            </div>

            <Button variant="outline" className="w-full">
              <Key className="mr-2 h-4 w-4" />
              Добавить новый ключ
            </Button>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-indigo-400" />
              Уве��омления
            </CardTitle>
            <CardDescription>
              Настройка оповещений
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-zinc-200">Новые тёплые лиды</p>
                <p className="text-sm text-zinc-500">
                  Уведомлять когда лид готов к передаче
                </p>
              </div>
              <Button variant="outline" size="sm">
                Включено
              </Button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-zinc-200">Ответы на письма</p>
                <p className="text-sm text-zinc-500">
                  Уведомлять о входящих ответах
                </p>
              </div>
              <Button variant="outline" size="sm">
                Включено
              </Button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-zinc-200">Ежедневная сводка</p>
                <p className="text-sm text-zinc-500">
                  Отчёт о работе системы за день
                </p>
              </div>
              <Button variant="ghost" size="sm">
                Отключено
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Team */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5 text-indigo-400" />
              Команда
            </CardTitle>
            <CardDescription>
              Управление пользователями
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between p-4 rounded-lg bg-zinc-800/50">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600">
                  <span className="text-sm font-medium text-white">АП</span>
                </div>
                <div>
                  <p className="font-medium text-zinc-200">Артём Побединский</p>
                  <p className="text-sm text-zinc-500">admin@otclick.ru</p>
                </div>
              </div>
              <Badge>Админ</Badge>
            </div>

            <Button variant="outline" className="w-full">
              <Users className="mr-2 h-4 w-4" />
              Пригласить пользователя
            </Button>
          </CardContent>
        </Card>

        {/* System */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5 text-indigo-400" />
              Система
            </CardTitle>
            <CardDescription>
              Технические настройки
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-zinc-200">API Backend</p>
                <p className="text-sm text-zinc-500">
                  http://176.126.166.94:8000
                </p>
              </div>
              <Badge variant="success">Online</Badge>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-zinc-200">Версия системы</p>
                <p className="text-sm text-zinc-500">
                  Employer Acquisition Engine v1.0.0
                </p>
              </div>
              <Button variant="ghost" size="sm">
                <RefreshCw className="mr-2 h-4 w-4" />
                Проверить
              </Button>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-zinc-200">База данных</p>
                <p className="text-sm text-zinc-500">PostgreSQL</p>
              </div>
              <Badge variant="success">Подключена</Badge>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-zinc-200">Redis</p>
                <p className="text-sm text-zinc-500">Кэш и очереди</p>
              </div>
              <Badge variant="success">Подключен</Badge>
            </div>
          </CardContent>
        </Card>

        {/* Security */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-indigo-400" />
              Безопасность
            </CardTitle>
            <CardDescription>
              Настройки безопасности аккаунта
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-zinc-300">
                Текущий пароль
              </label>
              <Input type="password" className="mt-1" placeholder="••••••••" />
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-300">
                Новый пароль
              </label>
              <Input type="password" className="mt-1" placeholder="••••••••" />
            </div>
            <div>
              <label className="text-sm font-medium text-zinc-300">
                Подтверждение пароля
              </label>
              <Input type="password" className="mt-1" placeholder="••••••••" />
            </div>
            <Button>Обновить пароль</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

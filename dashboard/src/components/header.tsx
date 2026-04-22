"use client"

import { useEffect, useState, useRef } from "react"
import Link from "next/link"
import { Bell, Search, User, Mail, AlertTriangle, UserCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api, NotificationCounts } from "@/lib/api"

interface HeaderProps {
  title: string
  description?: string
}

export function Header({ title, description }: HeaderProps) {
  const [counts, setCounts] = useState<NotificationCounts | null>(null)
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    async function fetchCounts() {
      try {
        const data = await api.getNotificationCounts()
        setCounts(data)
      } catch (e) {
        console.error("Failed to fetch notification counts:", e)
      }
    }

    fetchCounts()
    const interval = setInterval(fetchCounts, 30000)
    return () => clearInterval(interval)
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const totalCount = counts?.total_unread || 0

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-zinc-800 bg-zinc-950/80 px-6 backdrop-blur-sm">
      <div>
        <h1 className="text-xl font-semibold text-zinc-100">{title}</h1>
        {description && (
          <p className="text-sm text-zinc-500">{description}</p>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <Input
            placeholder="Поиск..."
            className="w-64 pl-9"
          />
        </div>

        {/* Notification Bell */}
        <div className="relative" ref={dropdownRef}>
          <Button
            variant="ghost"
            size="icon"
            className="relative"
            onClick={() => setIsOpen(!isOpen)}
          >
            <Bell className="h-5 w-5" />
            {totalCount > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-orange-500 px-1 text-xs font-semibold text-white">
                {totalCount > 99 ? "99+" : totalCount}
              </span>
            )}
          </Button>

          {/* Dropdown */}
          {isOpen && (
            <div className="absolute right-0 top-full mt-2 w-72 rounded-lg border border-zinc-800 bg-zinc-900 shadow-xl">
              <div className="border-b border-zinc-800 px-4 py-3">
                <h3 className="text-sm font-semibold text-zinc-100">Уведомления</h3>
              </div>
              <div className="max-h-80 overflow-y-auto">
                {totalCount === 0 ? (
                  <div className="px-4 py-6 text-center text-sm text-zinc-500">
                    Нет новых уведомлений
                  </div>
                ) : (
                  <div className="py-2">
                    {counts && counts.unread_replies > 0 && (
                      <Link
                        href="/emails?filter=replied"
                        onClick={() => setIsOpen(false)}
                        className="flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-800/50 transition-colors"
                      >
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-500/20">
                          <Mail className="h-4 w-4 text-blue-400" />
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-zinc-100">
                            Новые ответы
                          </p>
                          <p className="text-xs text-zinc-500">
                            {counts.unread_replies} {counts.unread_replies === 1 ? "письмо" : "писем"} за 24ч
                          </p>
                        </div>
                        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-blue-500 px-1.5 text-xs font-semibold text-white">
                          {counts.unread_replies}
                        </span>
                      </Link>
                    )}

                    {counts && counts.new_bounces > 0 && (
                      <Link
                        href="/emails?filter=bounced"
                        onClick={() => setIsOpen(false)}
                        className="flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-800/50 transition-colors"
                      >
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-red-500/20">
                          <AlertTriangle className="h-4 w-4 text-red-400" />
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-zinc-100">
                            Отказы доставки
                          </p>
                          <p className="text-xs text-zinc-500">
                            {counts.new_bounces} bounce за 24ч
                          </p>
                        </div>
                        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-xs font-semibold text-white">
                          {counts.new_bounces}
                        </span>
                      </Link>
                    )}

                    {counts && counts.pending_handoffs > 0 && (
                      <Link
                        href="/handoffs"
                        onClick={() => setIsOpen(false)}
                        className="flex items-center gap-3 px-4 py-2.5 hover:bg-zinc-800/50 transition-colors"
                      >
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-green-500/20">
                          <UserCheck className="h-4 w-4 text-green-400" />
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-zinc-100">
                            Тёплые лиды
                          </p>
                          <p className="text-xs text-zinc-500">
                            Ожидают обработки
                          </p>
                        </div>
                        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-green-500 px-1.5 text-xs font-semibold text-white">
                          {counts.pending_handoffs}
                        </span>
                      </Link>
                    )}
                  </div>
                )}
              </div>
              {totalCount > 0 && (
                <div className="border-t border-zinc-800 px-4 py-2">
                  <Link
                    href="/emails"
                    onClick={() => setIsOpen(false)}
                    className="block text-center text-sm text-indigo-400 hover:text-indigo-300"
                  >
                    Посмотреть все
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>

        <Button variant="ghost" size="icon">
          <User className="h-5 w-5" />
        </Button>
      </div>
    </header>
  )
}

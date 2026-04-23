"use client"

import { useState, useRef, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import { api, ThreadSummary } from "@/lib/api"
import { formatDateTime, formatNumber } from "@/lib/utils"
import {
  Search,
  Send,
  Mail,
  MailOpen,
  MessageSquare,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Building2,
  User,
  Clock,
  ArrowUpRight,
  ArrowDownLeft,
  X,
  MessagesSquare,
  Loader2,
} from "lucide-react"

const EMAIL_STATUSES = [
  { value: "all", label: "Все статусы" },
  { value: "sent", label: "Отправлено" },
  { value: "opened", label: "Открыто" },
  { value: "replied", label: "Ответили" },
  { value: "bounced", label: "Ошибка" },
]

const statusConfig: Record<string, { label: string; icon: typeof Send; color: string; bgColor: string }> = {
  sent: { label: "Отправлено", icon: Send, color: "text-zinc-400", bgColor: "bg-zinc-500/20" },
  delivered: { label: "Доставлено", icon: Mail, color: "text-blue-400", bgColor: "bg-blue-500/20" },
  opened: { label: "Открыто", icon: MailOpen, color: "text-emerald-400", bgColor: "bg-emerald-500/20" },
  replied: { label: "Ответили", icon: MessageSquare, color: "text-amber-400", bgColor: "bg-amber-500/20" },
  bounced: { label: "Ошибка", icon: AlertCircle, color: "text-red-400", bgColor: "bg-red-500/20" },
}

export default function EmailsPage() {
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState("all")
  const [page, setPage] = useState(1)
  const [selectedThread, setSelectedThread] = useState<ThreadSummary | null>(null)
  const [replyText, setReplyText] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()
  const limit = 20

  // Fetch threads (grouped by lead)
  const { data, isLoading } = useQuery({
    queryKey: ["email-threads", { search, status, page, limit }],
    queryFn: () =>
      api.getThreads({
        search: search || undefined,
        status: status !== "all" ? status : undefined,
        page,
        limit,
      }),
  })

  // Fetch stats
  const { data: emailStats } = useQuery({
    queryKey: ["email-stats"],
    queryFn: () => api.getEmailStats(),
    staleTime: 30000,
  })

  // Fetch thread messages when dialog opens
  const { data: threadData, isLoading: threadLoading } = useQuery({
    queryKey: ["email-thread", selectedThread?.lead_id],
    queryFn: () => api.getEmailThread(selectedThread!.lead_id),
    enabled: !!selectedThread,
  })

  // Send reply mutation
  const replyMutation = useMutation({
    mutationFn: (data: { lead_id: string; body: string }) => api.sendReply(data),
    onSuccess: (result) => {
      if (result.success) {
        setReplyText("")
        // Refresh thread
        queryClient.invalidateQueries({ queryKey: ["email-thread", selectedThread?.lead_id] })
        queryClient.invalidateQueries({ queryKey: ["email-threads"] })
      }
    },
  })

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (threadData?.thread && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [threadData?.thread])

  const handleCloseDialog = () => {
    setSelectedThread(null)
    setReplyText("")
  }

  const handleSendReply = () => {
    if (!selectedThread || !replyText.trim()) return
    replyMutation.mutate({
      lead_id: selectedThread.lead_id,
      body: replyText.trim(),
    })
  }

  const getStatusBadge = (threadStatus: string) => {
    const config = statusConfig[threadStatus] || statusConfig.sent
    const Icon = config.icon
    return (
      <Badge variant="outline" className={`gap-1.5 ${config.color} ${config.bgColor} border-0`}>
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    )
  }

  const stats = {
    total: emailStats?.total_sent || 0,
    sent: emailStats?.total_delivered || 0,
    opened: emailStats?.total_opened || 0,
    replied: emailStats?.total_replied || 0,
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Hero Header */}
      <div className="relative overflow-hidden border-b border-zinc-800">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/10 via-transparent to-orange-500/5" />
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-indigo-600/5 rounded-full blur-3xl" />

        <div className="relative px-4 sm:px-6 py-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-zinc-100">Письма</h1>
              <p className="text-zinc-400 mt-1 text-sm sm:text-base">
                Переписка с компаниями
              </p>
            </div>
            <Link href="/test-email" className="hidden sm:block">
              <Button className="gap-2 bg-indigo-600 hover:bg-indigo-700">
                <Send className="h-4 w-4" />
                Тестовое письмо
              </Button>
            </Link>
          </div>

          {/* Stats */}
          <div className="grid gap-3 sm:gap-4 grid-cols-2 md:grid-cols-4 mb-6">
            <div className="p-3 sm:p-4 rounded-xl bg-gradient-to-br from-indigo-600/20 to-indigo-600/5 border border-indigo-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs sm:text-sm text-zinc-400">Всего писем</p>
                  <p className="text-xl sm:text-2xl font-bold text-indigo-400 mt-1">
                    {formatNumber(stats.total)}
                  </p>
                </div>
                <Mail className="h-6 w-6 sm:h-8 sm:w-8 text-indigo-400/50" />
              </div>
            </div>

            <div className="p-3 sm:p-4 rounded-xl bg-gradient-to-br from-blue-600/20 to-blue-600/5 border border-blue-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs sm:text-sm text-zinc-400">Доставлено</p>
                  <p className="text-xl sm:text-2xl font-bold text-blue-400 mt-1">
                    {formatNumber(stats.sent)}
                  </p>
                </div>
                <Send className="h-6 w-6 sm:h-8 sm:w-8 text-blue-400/50" />
              </div>
            </div>

            <div className="p-3 sm:p-4 rounded-xl bg-gradient-to-br from-emerald-600/20 to-emerald-600/5 border border-emerald-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs sm:text-sm text-zinc-400">Открыто</p>
                  <p className="text-xl sm:text-2xl font-bold text-emerald-400 mt-1">
                    {formatNumber(stats.opened)}
                  </p>
                </div>
                <MailOpen className="h-6 w-6 sm:h-8 sm:w-8 text-emerald-400/50" />
              </div>
            </div>

            <div className="p-3 sm:p-4 rounded-xl bg-gradient-to-br from-amber-600/20 to-amber-600/5 border border-amber-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs sm:text-sm text-zinc-400">Ответили</p>
                  <p className="text-xl sm:text-2xl font-bold text-amber-400 mt-1">
                    {formatNumber(stats.replied)}
                  </p>
                </div>
                <MessageSquare className="h-6 w-6 sm:h-8 sm:w-8 text-amber-400/50" />
              </div>
            </div>
          </div>

          {/* Search & Filters */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                placeholder="Поиск по компании..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 bg-zinc-900/50 border-zinc-700"
              />
            </div>

            <div className="flex gap-2">
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger className="w-full sm:w-[180px] bg-zinc-900/50 border-zinc-700">
                  <SelectValue placeholder="Статус" />
                </SelectTrigger>
                <SelectContent>
                  {EMAIL_STATUSES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {(search || status !== "all") && (
                <Button
                  variant="ghost"
                  onClick={() => {
                    setSearch("")
                    setStatus("all")
                  }}
                  className="gap-2 shrink-0"
                >
                  <X className="h-4 w-4" />
                  <span className="hidden sm:inline">Сбросить</span>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Thread List */}
      <div className="p-4 sm:p-6 pb-24 sm:pb-6">
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessagesSquare className="h-5 w-5 text-indigo-400" />
              Переписки
              {data?.total ? (
                <span className="text-sm font-normal text-zinc-500">
                  ({data.total} компаний)
                </span>
              ) : null}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-2">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-20" />
                ))}
              </div>
            ) : data?.items?.length ? (
              <>
                <div className="divide-y divide-zinc-800">
                  {data.items.map((thread) => (
                    <div
                      key={thread.lead_id}
                      className="py-4 px-2 -mx-2 cursor-pointer hover:bg-zinc-800/50 rounded-lg transition-colors"
                      onClick={() => setSelectedThread(thread)}
                    >
                      <div className="flex items-start gap-3">
                        {/* Avatar */}
                        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600/30 to-indigo-500/10">
                          <Building2 className="h-5 w-5 text-indigo-400" />
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="font-semibold text-zinc-100 truncate">
                                {thread.company_name || "—"}
                              </span>
                              {thread.message_count > 1 && (
                                <Badge variant="outline" className="text-xs text-zinc-400 bg-zinc-800 border-zinc-700 shrink-0">
                                  {thread.message_count}
                                </Badge>
                              )}
                            </div>
                            <span className="text-xs text-zinc-500 shrink-0">
                              {thread.last_message_at ? formatDateTime(thread.last_message_at) : "—"}
                            </span>
                          </div>

                          <div className="flex items-center gap-2 mb-1.5">
                            <User className="h-3.5 w-3.5 text-zinc-500 shrink-0" />
                            <span className="text-sm text-zinc-400 truncate">
                              {thread.contact_name || thread.contact_email || "—"}
                            </span>
                          </div>

                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <p className={`text-sm truncate ${thread.has_reply ? "font-medium text-zinc-200" : "text-zinc-400"}`}>
                                {thread.last_subject}
                              </p>
                              <p className="text-xs text-zinc-500 truncate mt-0.5">
                                {thread.last_snippet}
                              </p>
                            </div>
                            <div className="shrink-0">
                              {getStatusBadge(thread.status)}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Pagination */}
                {(data.pages || 1) > 1 && (
                  <div className="mt-6 flex items-center justify-center gap-2">
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
                    <span className="text-sm text-zinc-500 px-4">
                      Страница {page} из {data.pages || 1}
                    </span>
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
              <div className="flex flex-col items-center justify-center py-16">
                <div className="h-20 w-20 rounded-full bg-gradient-to-br from-indigo-600/20 to-orange-500/20 flex items-center justify-center mb-6">
                  <Mail className="h-10 w-10 text-zinc-500" />
                </div>
                <h3 className="text-lg font-semibold text-zinc-200 mb-2">
                  Переписок пока нет
                </h3>
                <p className="text-zinc-500 text-center max-w-md">
                  {search || status !== "all"
                    ? "Попробуйте изменить параметры поиска"
                    : "Переписки появятся после запуска email-кампаний"}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Mobile FAB */}
      <Link
        href="/test-email"
        className="sm:hidden fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-700 active:scale-95 transition-all"
      >
        <Send className="h-6 w-6" />
      </Link>

      {/* Thread Dialog - Messenger Style */}
      <Dialog open={!!selectedThread} onOpenChange={handleCloseDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] sm:max-h-[85vh] flex flex-col bg-zinc-900 border-zinc-700 mx-2 sm:mx-auto rounded-xl p-0 overflow-hidden">
          {selectedThread && (
            <>
              {/* Header */}
              <DialogHeader className="p-4 border-b border-zinc-800 shrink-0">
                <DialogTitle className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600/30 to-indigo-500/10">
                    <Building2 className="h-5 w-5 text-indigo-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <Link
                      href={`/leads/${selectedThread.lead_id}`}
                      className="text-lg font-semibold text-zinc-100 hover:text-indigo-400 transition-colors truncate block"
                    >
                      {selectedThread.company_name || "—"}
                    </Link>
                    <p className="text-sm text-zinc-500 truncate">
                      {selectedThread.contact_name || ""}{" "}
                      {selectedThread.contact_email && (
                        <span className="text-zinc-600">
                          • {selectedThread.contact_email}
                        </span>
                      )}
                    </p>
                  </div>
                  {getStatusBadge(selectedThread.status)}
                </DialogTitle>
              </DialogHeader>

              {/* Chat Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-zinc-950/50">
                {threadLoading ? (
                  <div className="flex flex-col gap-4">
                    <div className="flex justify-end">
                      <Skeleton className="h-24 w-3/4 rounded-2xl rounded-br-md" />
                    </div>
                    <div className="flex justify-start">
                      <Skeleton className="h-16 w-2/3 rounded-2xl rounded-bl-md" />
                    </div>
                  </div>
                ) : threadData?.thread && threadData.thread.length > 0 ? (
                  threadData.thread.map((message) => (
                    <div
                      key={message.id}
                      className={`flex ${message.direction === "outbound" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[85%] sm:max-w-[75%] ${
                          message.direction === "outbound"
                            ? "bg-indigo-600 text-white rounded-2xl rounded-br-md"
                            : "bg-zinc-800 text-zinc-100 rounded-2xl rounded-bl-md"
                        }`}
                      >
                        {/* Message Header */}
                        <div
                          className={`px-4 pt-3 pb-1 flex items-center gap-2 ${
                            message.direction === "outbound"
                              ? "text-indigo-200"
                              : "text-zinc-400"
                          }`}
                        >
                          {message.direction === "outbound" ? (
                            <ArrowUpRight className="h-3.5 w-3.5" />
                          ) : (
                            <ArrowDownLeft className="h-3.5 w-3.5" />
                          )}
                          <span className="text-xs font-medium">
                            {message.direction === "outbound" ? "Вы" : threadData.contact_name || "Ответ"}
                          </span>
                          <span className="text-xs opacity-70">
                            {formatDateTime(message.sent_at)}
                          </span>
                        </div>

                        {/* Subject (if not Re:) */}
                        {message.subject && !message.subject.startsWith("Re:") && (
                          <div
                            className={`px-4 pb-1 text-xs font-medium ${
                              message.direction === "outbound"
                                ? "text-indigo-100"
                                : "text-zinc-300"
                            }`}
                          >
                            {message.subject}
                          </div>
                        )}

                        {/* Message Body */}
                        <div
                          className={`px-4 pb-3 text-sm leading-relaxed prose prose-sm max-w-none ${
                            message.direction === "outbound"
                              ? "prose-invert prose-p:text-white prose-strong:text-white"
                              : "prose-invert prose-p:text-zinc-200"
                          }`}
                          dangerouslySetInnerHTML={{ __html: message.body || "" }}
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-zinc-500 py-8">
                    Нет сообщений
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Reply Input */}
              <div className="p-3 border-t border-zinc-800 shrink-0 bg-zinc-900 space-y-3">
                {replyMutation.error && (
                  <div className="text-sm text-red-400 bg-red-500/10 px-3 py-2 rounded-lg">
                    Ошибка: {replyMutation.error instanceof Error ? replyMutation.error.message : "Не удалось отправить"}
                  </div>
                )}
                {replyMutation.data && !replyMutation.data.success && (
                  <div className="text-sm text-red-400 bg-red-500/10 px-3 py-2 rounded-lg">
                    {replyMutation.data.error || "Не удалось отправить"}
                  </div>
                )}
                <div className="flex gap-2">
                  <Textarea
                    placeholder="Написать ответ..."
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    className="min-h-[60px] max-h-[120px] bg-zinc-800 border-zinc-700 resize-none"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                        e.preventDefault()
                        handleSendReply()
                      }
                    }}
                  />
                  <Button
                    onClick={handleSendReply}
                    disabled={!replyText.trim() || replyMutation.isPending}
                    className="shrink-0 bg-indigo-600 hover:bg-indigo-700 self-end"
                  >
                    {replyMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
                  <span className="text-zinc-600">От: Владислав Наков</span>
                  <span className="text-zinc-700">•</span>
                  <span className="text-zinc-600">Ctrl+Enter для отправки</span>
                  <Link
                    href={`/leads/${selectedThread.lead_id}`}
                    className="ml-auto text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                  >
                    Карточка лида →
                  </Link>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

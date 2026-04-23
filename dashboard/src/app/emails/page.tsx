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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { api, Email, EmailThreadResponse } from "@/lib/api"
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
  FlaskConical,
  Reply,
} from "lucide-react"

// Strip HTML tags for plain text preview
function stripHtml(html: string | undefined): string {
  if (!html) return ""
  return html.replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim()
}

const EMAIL_STATUSES = [
  { value: "all", label: "Все статусы" },
  { value: "sent", label: "Отправлено" },
  { value: "delivered", label: "Доставлено" },
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
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null)
  const [selectedLeadId, setSelectedLeadId] = useState<string | null>(null)
  const limit = 20

  const { data, isLoading } = useQuery({
    queryKey: ["emails", { search, status, page, limit }],
    queryFn: () =>
      api.getEmails({
        search: search || undefined,
        status: status !== "all" ? status : undefined,
        page,
        limit,
      }),
  })

  // Fetch real stats from API
  const { data: emailStats } = useQuery({
    queryKey: ["email-stats"],
    queryFn: () => api.getEmailStats(),
    staleTime: 30000, // 30 seconds
  })

  // Fetch thread when email is selected
  const { data: threadData, isLoading: threadLoading } = useQuery({
    queryKey: ["email-thread", selectedLeadId],
    queryFn: () => api.getEmailThread(selectedLeadId!),
    enabled: !!selectedLeadId,
  })

  const handleEmailClick = (email: Email) => {
    setSelectedEmail(email)
    setSelectedLeadId(email.lead_id)
  }

  const handleCloseDialog = () => {
    setSelectedEmail(null)
    setSelectedLeadId(null)
  }

  const getStatusBadge = (emailStatus: string, hasReply?: boolean) => {
    const config = statusConfig[emailStatus] || statusConfig.sent
    const Icon = config.icon
    return (
      <div className="flex items-center gap-1.5">
        <Badge variant="outline" className={`gap-1.5 ${config.color} ${config.bgColor} border-0`}>
          <Icon className="h-3 w-3" />
          {config.label}
        </Badge>
        {hasReply && emailStatus !== "replied" && (
          <Badge variant="outline" className="gap-1 text-amber-400 bg-amber-500/20 border-0 text-xs">
            <MessageSquare className="h-3 w-3" />
          </Badge>
        )}
      </div>
    )
  }

  const stats = {
    total: emailStats?.total_sent || data?.total || 0,
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
                История email-коммуникаций
              </p>
            </div>
            {/* Desktop: Test Email Button */}
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
                  <p className="text-xs sm:text-sm text-zinc-400">Отправлено</p>
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
                placeholder="Поиск по компании, контакту..."
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

      {/* Content */}
      <div className="p-4 sm:p-6 pb-24 sm:pb-6">
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-indigo-400" />
              История писем
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-16" />
                ))}
              </div>
            ) : data?.items?.length ? (
              <>
                <div className="overflow-x-auto -mx-4 sm:mx-0">
                <Table className="min-w-[800px] sm:min-w-0">
                  <TableHeader>
                    <TableRow className="border-zinc-800 hover:bg-transparent">
                      <TableHead className="text-zinc-400">Компания</TableHead>
                      <TableHead className="text-zinc-400">Контакт</TableHead>
                      <TableHead className="text-zinc-400">Тема</TableHead>
                      <TableHead className="text-zinc-400">Текст</TableHead>
                      <TableHead className="text-zinc-400">Статус</TableHead>
                      <TableHead className="text-zinc-400">Дата</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((email) => (
                      <TableRow
                        key={email.id}
                        className="border-zinc-800 cursor-pointer hover:bg-zinc-800/50 transition-colors"
                        onClick={() => handleEmailClick(email)}
                      >
                        <TableCell>
                          <Link
                            href={`/leads/${email.lead_id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="flex items-center gap-2 text-zinc-200 hover:text-indigo-400 transition-colors"
                          >
                            <Building2 className="h-4 w-4 text-zinc-500" />
                            <span className="font-medium truncate max-w-[150px]">
                              {email.company_name || email.contact_email || "—"}
                            </span>
                          </Link>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2 text-zinc-300">
                            <User className="h-4 w-4 text-zinc-500" />
                            <div className="truncate max-w-[120px]">
                              <p className="truncate">{email.contact_name || email.contact_email || "—"}</p>
                              {email.contact_name && email.contact_email && (
                                <p className="text-xs text-zinc-500 truncate">
                                  {email.contact_email}
                                </p>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-zinc-200 truncate block max-w-[180px]">
                              {email.subject}
                            </span>
                            {email.email_type === "test" && (
                              <Badge variant="outline" className="gap-1 text-purple-400 bg-purple-500/20 border-0 text-xs shrink-0">
                                <FlaskConical className="h-3 w-3" />
                                Тест
                              </Badge>
                            )}
                            {email.email_type === "auto_reply" && (
                              <Badge variant="outline" className="gap-1 text-cyan-400 bg-cyan-500/20 border-0 text-xs shrink-0">
                                <Reply className="h-3 w-3" />
                                Авто
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="text-zinc-400 truncate block max-w-[200px]">
                            {stripHtml(email.body).slice(0, 60)}...
                          </span>
                        </TableCell>
                        <TableCell>
                          {getStatusBadge(email.status, !!email.replied_at)}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1.5 text-zinc-500 text-sm">
                            <Clock className="h-3.5 w-3.5" />
                            {formatDateTime(email.sent_at)}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
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
                  Писем пока нет
                </h3>
                <p className="text-zinc-500 text-center max-w-md">
                  {search || status !== "all"
                    ? "Попробуйте изменить параметры поиска"
                    : "Письма появятся после запуска email-кампаний"}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Mobile FAB: Test Email Button */}
      <Link
        href="/test-email"
        className="sm:hidden fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-700 active:scale-95 transition-all"
      >
        <Send className="h-6 w-6" />
      </Link>

      {/* Email Thread Dialog - Messenger Style */}
      <Dialog open={!!selectedEmail} onOpenChange={handleCloseDialog}>
        <DialogContent className="max-w-2xl max-h-[90vh] sm:max-h-[85vh] flex flex-col bg-zinc-900 border-zinc-700 mx-2 sm:mx-auto rounded-xl p-0 overflow-hidden">
          {selectedEmail && (
            <>
              {/* Header */}
              <DialogHeader className="p-4 border-b border-zinc-800 shrink-0">
                <DialogTitle className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600/30 to-indigo-500/10">
                    <Building2 className="h-5 w-5 text-indigo-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <Link
                      href={`/leads/${selectedEmail.lead_id}`}
                      className="text-lg font-semibold text-zinc-100 hover:text-indigo-400 transition-colors truncate block"
                    >
                      {threadData?.company_name || selectedEmail.company_name || "—"}
                    </Link>
                    <p className="text-sm text-zinc-500 truncate">
                      {threadData?.contact_name || selectedEmail.contact_name || ""}{" "}
                      {(threadData?.contact_email || selectedEmail.contact_email) && (
                        <span className="text-zinc-600">
                          • {threadData?.contact_email || selectedEmail.contact_email}
                        </span>
                      )}
                    </p>
                  </div>
                  {getStatusBadge(selectedEmail.status, !!selectedEmail.replied_at)}
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

                        {/* Subject (if different from Re:) */}
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
                  // Fallback: show current email if no thread data
                  <div className="flex justify-end">
                    <div className="max-w-[85%] sm:max-w-[75%] bg-indigo-600 text-white rounded-2xl rounded-br-md">
                      <div className="px-4 pt-3 pb-1 flex items-center gap-2 text-indigo-200">
                        <ArrowUpRight className="h-3.5 w-3.5" />
                        <span className="text-xs font-medium">Вы</span>
                        <span className="text-xs opacity-70">
                          {formatDateTime(selectedEmail.sent_at)}
                        </span>
                      </div>
                      <div className="px-4 pb-1 text-xs font-medium text-indigo-100">
                        {selectedEmail.subject}
                      </div>
                      <div
                        className="px-4 pb-3 text-sm leading-relaxed prose prose-sm max-w-none prose-invert prose-p:text-white"
                        dangerouslySetInnerHTML={{ __html: selectedEmail.body || "" }}
                      />
                    </div>
                  </div>
                )}
              </div>

              {/* Footer with meta info */}
              <div className="p-3 border-t border-zinc-800 shrink-0 bg-zinc-900">
                <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500">
                  {selectedEmail.opened_at && (
                    <div className="flex items-center gap-1.5 text-emerald-400">
                      <MailOpen className="h-3.5 w-3.5" />
                      <span>Открыто {formatDateTime(selectedEmail.opened_at)}</span>
                    </div>
                  )}
                  {selectedEmail.replied_at && (
                    <div className="flex items-center gap-1.5 text-amber-400">
                      <MessageSquare className="h-3.5 w-3.5" />
                      <span>Ответ {formatDateTime(selectedEmail.replied_at)}</span>
                    </div>
                  )}
                  {threadData?.thread && threadData.thread.length > 1 && (
                    <div className="flex items-center gap-1.5 text-zinc-400">
                      <Mail className="h-3.5 w-3.5" />
                      <span>{threadData.thread.length} сообщений</span>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

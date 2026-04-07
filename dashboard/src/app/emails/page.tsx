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
import { api, Email } from "@/lib/api"
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
} from "lucide-react"

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

  const getStatusBadge = (emailStatus: string) => {
    const config = statusConfig[emailStatus] || statusConfig.sent
    const Icon = config.icon
    return (
      <Badge variant="outline" className={`gap-1.5 ${config.color} ${config.bgColor} border-0`}>
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    )
  }

  const stats = {
    total: data?.total || 0,
    sent: data?.items?.filter(e => e.status === "sent").length || 0,
    opened: data?.items?.filter(e => e.status === "opened").length || 0,
    replied: data?.items?.filter(e => e.status === "replied").length || 0,
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Hero Header */}
      <div className="relative overflow-hidden border-b border-zinc-800">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/10 via-transparent to-orange-500/5" />
        <div className="absolute top-0 right-1/4 w-96 h-96 bg-indigo-600/5 rounded-full blur-3xl" />

        <div className="relative px-6 py-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-3xl font-bold text-zinc-100">Письма</h1>
              <p className="text-zinc-400 mt-1">
                История email-коммуникаций
              </p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid gap-4 md:grid-cols-4 mb-6">
            <div className="p-4 rounded-xl bg-gradient-to-br from-indigo-600/20 to-indigo-600/5 border border-indigo-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Всего писем</p>
                  <p className="text-2xl font-bold text-indigo-400 mt-1">
                    {formatNumber(stats.total)}
                  </p>
                </div>
                <Mail className="h-8 w-8 text-indigo-400/50" />
              </div>
            </div>

            <div className="p-4 rounded-xl bg-gradient-to-br from-blue-600/20 to-blue-600/5 border border-blue-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Отправлено</p>
                  <p className="text-2xl font-bold text-blue-400 mt-1">
                    {formatNumber(stats.sent)}
                  </p>
                </div>
                <Send className="h-8 w-8 text-blue-400/50" />
              </div>
            </div>

            <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-600/20 to-emerald-600/5 border border-emerald-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Открыто</p>
                  <p className="text-2xl font-bold text-emerald-400 mt-1">
                    {formatNumber(stats.opened)}
                  </p>
                </div>
                <MailOpen className="h-8 w-8 text-emerald-400/50" />
              </div>
            </div>

            <div className="p-4 rounded-xl bg-gradient-to-br from-amber-600/20 to-amber-600/5 border border-amber-500/20">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Ответили</p>
                  <p className="text-2xl font-bold text-amber-400 mt-1">
                    {formatNumber(stats.replied)}
                  </p>
                </div>
                <MessageSquare className="h-8 w-8 text-amber-400/50" />
              </div>
            </div>
          </div>

          {/* Search & Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[240px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                placeholder="Поиск по компании, контакту или теме..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 bg-zinc-900/50 border-zinc-700"
              />
            </div>

            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger className="w-[180px] bg-zinc-900/50 border-zinc-700">
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
                className="gap-2"
              >
                <X className="h-4 w-4" />
                Сбросить
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="p-6">
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
                <Table>
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
                        onClick={() => setSelectedEmail(email)}
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
                          <span className="font-medium text-zinc-200 truncate block max-w-[200px]">
                            {email.subject}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className="text-zinc-400 truncate block max-w-[200px]">
                            {email.body?.slice(0, 60)}...
                          </span>
                        </TableCell>
                        <TableCell>
                          {getStatusBadge(email.status)}
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

      {/* Email Detail Dialog */}
      <Dialog open={!!selectedEmail} onOpenChange={() => setSelectedEmail(null)}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto bg-zinc-900 border-zinc-700">
          {selectedEmail && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-600/20 to-orange-500/20">
                    <Mail className="h-5 w-5 text-indigo-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-lg font-semibold text-zinc-100 truncate">
                      {selectedEmail.subject}
                    </p>
                    <p className="text-sm text-zinc-500">
                      {selectedEmail.company_name || selectedEmail.contact_email || "—"}
                    </p>
                  </div>
                  {getStatusBadge(selectedEmail.status)}
                </DialogTitle>
              </DialogHeader>

              <div className="space-y-6 mt-4">
                {/* Meta Info */}
                <div className="grid grid-cols-2 gap-4 p-4 rounded-xl bg-zinc-800/50">
                  <div className="flex items-center gap-3">
                    <Building2 className="h-5 w-5 text-zinc-500" />
                    <div>
                      <p className="text-xs text-zinc-500">Компания</p>
                      <Link
                        href={`/leads/${selectedEmail.lead_id}`}
                        className="text-sm text-indigo-400 hover:text-indigo-300"
                      >
                        {selectedEmail.company_name || selectedEmail.contact_email || "—"}
                      </Link>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <User className="h-5 w-5 text-zinc-500" />
                    <div>
                      <p className="text-xs text-zinc-500">Контакт</p>
                      <p className="text-sm text-zinc-200">{selectedEmail.contact_name || selectedEmail.contact_email || "—"}</p>
                      {selectedEmail.contact_name && selectedEmail.contact_email && (
                        <p className="text-xs text-zinc-400">{selectedEmail.contact_email}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Clock className="h-5 w-5 text-zinc-500" />
                    <div>
                      <p className="text-xs text-zinc-500">Отправлено</p>
                      <p className="text-sm text-zinc-200">
                        {formatDateTime(selectedEmail.sent_at)}
                      </p>
                    </div>
                  </div>
                  {selectedEmail.opened_at && (
                    <div className="flex items-center gap-3">
                      <MailOpen className="h-5 w-5 text-emerald-500" />
                      <div>
                        <p className="text-xs text-zinc-500">Открыто</p>
                        <p className="text-sm text-emerald-400">
                          {formatDateTime(selectedEmail.opened_at)}
                        </p>
                      </div>
                    </div>
                  )}
                  {selectedEmail.replied_at && (
                    <div className="flex items-center gap-3">
                      <MessageSquare className="h-5 w-5 text-amber-500" />
                      <div>
                        <p className="text-xs text-zinc-500">Ответ получен</p>
                        <p className="text-sm text-amber-400">
                          {formatDateTime(selectedEmail.replied_at)}
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                {/* Email Body */}
                <div>
                  <h4 className="text-sm font-medium text-zinc-400 mb-3">Текст письма</h4>
                  <div className="p-4 rounded-xl bg-zinc-800/50 border border-zinc-700">
                    <p className="text-zinc-200 whitespace-pre-wrap leading-relaxed">
                      {selectedEmail.body}
                    </p>
                  </div>
                </div>

                {/* Thread */}
                {selectedEmail.thread && selectedEmail.thread.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-zinc-400 mb-3">
                      История переписки ({selectedEmail.thread.length})
                    </h4>
                    <div className="space-y-3">
                      {selectedEmail.thread.map((message) => (
                        <div
                          key={message.id}
                          className={`p-4 rounded-xl border ${
                            message.direction === "inbound"
                              ? "bg-amber-600/10 border-amber-500/30"
                              : "bg-zinc-800/50 border-zinc-700"
                          }`}
                        >
                          <div className="flex items-center gap-2 mb-2">
                            {message.direction === "inbound" ? (
                              <ArrowDownLeft className="h-4 w-4 text-amber-400" />
                            ) : (
                              <ArrowUpRight className="h-4 w-4 text-indigo-400" />
                            )}
                            <span className="text-sm font-medium text-zinc-200">
                              {message.direction === "inbound" ? "Входящее" : "Исходящее"}
                            </span>
                            <span className="text-xs text-zinc-500">
                              {formatDateTime(message.sent_at)}
                            </span>
                          </div>
                          <p className="text-sm font-medium text-zinc-300 mb-1">
                            {message.subject}
                          </p>
                          <p className="text-sm text-zinc-400 whitespace-pre-wrap">
                            {message.body}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

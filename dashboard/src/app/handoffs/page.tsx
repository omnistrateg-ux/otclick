"use client"

import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { Header } from "@/components/header"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Skeleton } from "@/components/ui/skeleton"
import { api } from "@/lib/api"
import { formatDateTime } from "@/lib/utils"
import {
  UserCheck,
  Building2,
  ExternalLink,
  CheckCircle,
  Clock,
  AlertCircle,
  User,
  MessageSquare,
} from "lucide-react"

const priorityConfig: Record<
  string,
  { label: string; color: string; bgColor: string; icon: typeof CheckCircle }
> = {
  high: { label: "Высокий", color: "text-emerald-400", bgColor: "bg-emerald-500/20", icon: CheckCircle },
  normal: { label: "Обычный", color: "text-amber-400", bgColor: "bg-amber-500/20", icon: Clock },
  low: { label: "Низкий", color: "text-zinc-400", bgColor: "bg-zinc-500/20", icon: AlertCircle },
}

const statusConfig: Record<string, { label: string; variant: "default" | "warning" | "success" }> = {
  pending: { label: "Ожидает", variant: "warning" },
  accepted: { label: "Принят", variant: "default" },
  completed: { label: "Завершён", variant: "success" },
  rejected: { label: "Отклонён", variant: "default" },
}

export default function HandoffsPage() {
  const { data: handoffs, isLoading } = useQuery({
    queryKey: ["handoffs"],
    queryFn: api.getHandoffs,
  })

  return (
    <div className="min-h-screen">
      <Header
        title="Тёплые лиды"
        description="Лиды, готовые к передаче менеджеру"
      />

      <div className="p-6 space-y-6">
        {/* Stats */}
        <div className="grid gap-4 md:grid-cols-3">
          <Card className="bg-gradient-to-br from-emerald-600/20 to-emerald-600/5 border-emerald-600/20">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Высокий приоритет</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {handoffs?.filter((h) => h.priority === "high").length || 0}
                  </p>
                </div>
                <CheckCircle className="h-8 w-8 text-emerald-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-amber-600/20 to-amber-600/5 border-amber-600/20">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Ожидают принятия</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {handoffs?.filter((h) => h.status === "pending").length || 0}
                  </p>
                </div>
                <Clock className="h-8 w-8 text-amber-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-gradient-to-br from-indigo-600/20 to-indigo-600/5 border-indigo-600/20">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-zinc-400">Всего передач</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {handoffs?.length || 0}
                  </p>
                </div>
                <UserCheck className="h-8 w-8 text-indigo-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Handoffs Table */}
        <Card>
          <CardHeader>
            <CardTitle>Список передач менеджерам</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <Skeleton key={i} className="h-16" />
                ))}
              </div>
            ) : handoffs?.length ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Компания</TableHead>
                    <TableHead>Менеджер</TableHead>
                    <TableHead>Приоритет</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead>Тезисы</TableHead>
                    <TableHead>Дата</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {handoffs.map((handoff) => {
                    const prioConfig = priorityConfig[handoff.priority] || priorityConfig.normal
                    const PrioIcon = prioConfig.icon
                    const statConfig = statusConfig[handoff.status] || statusConfig.pending

                    return (
                      <TableRow key={handoff.id}>
                        <TableCell>
                          <Link
                            href={`/leads/${handoff.lead_id}`}
                            className="flex items-center gap-2 font-medium text-zinc-100 hover:text-indigo-400 transition-colors"
                          >
                            <Building2 className="h-4 w-4 text-zinc-500" />
                            {handoff.company_name}
                          </Link>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2 text-zinc-300">
                            <User className="h-4 w-4 text-zinc-500" />
                            {handoff.manager_id || "—"}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className={`gap-1.5 ${prioConfig.color} ${prioConfig.bgColor} border-0`}>
                            <PrioIcon className="h-3 w-3" />
                            {prioConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={statConfig.variant}>
                            {statConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {handoff.talking_points?.length > 0 ? (
                            <div className="flex items-center gap-1 text-zinc-400">
                              <MessageSquare className="h-3 w-3" />
                              <span className="text-sm">{handoff.talking_points.length} тезисов</span>
                            </div>
                          ) : (
                            <span className="text-zinc-500">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-zinc-500">
                          {formatDateTime(handoff.created_at)}
                        </TableCell>
                        <TableCell>
                          <Link href={`/leads/${handoff.lead_id}`}>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          </Link>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            ) : (
              <div className="flex flex-col items-center justify-center py-12">
                <UserCheck className="h-12 w-12 text-zinc-600 mb-4" />
                <p className="text-zinc-400 text-lg font-medium">
                  Нет передач менеджерам
                </p>
                <p className="text-zinc-500 text-sm mt-1">
                  Лиды с высоким интересом появятся здесь автоматически
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Notes/Tips */}
        <Card className="border-indigo-600/20 bg-indigo-600/5">
          <CardContent className="pt-6">
            <h3 className="font-medium text-indigo-400 mb-2">
              Как работать с передачами
            </h3>
            <ul className="space-y-2 text-sm text-zinc-400">
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-emerald-400 mt-0.5" />
                <span>
                  <strong className="text-zinc-300">Высокий приоритет:</strong>{" "}
                  Свяжитесь в течение 24 часов
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Clock className="h-4 w-4 text-amber-400 mt-0.5" />
                <span>
                  <strong className="text-zinc-300">Обычный приоритет:</strong>{" "}
                  Свяжитесь в течение 48 часов
                </span>
              </li>
              <li className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-zinc-400 mt-0.5" />
                <span>
                  <strong className="text-zinc-300">Низкий приоритет:</strong>{" "}
                  Добавьте в follow-up последовательность
                </span>
              </li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

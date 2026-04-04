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
  Mail,
  Phone,
  ExternalLink,
  CheckCircle,
  Clock,
  AlertCircle,
} from "lucide-react"

const interestLevelConfig: Record<
  string,
  { label: string; color: string; icon: typeof CheckCircle }
> = {
  HIGH: { label: "Высокий", color: "text-emerald-400", icon: CheckCircle },
  MEDIUM: { label: "Средний", color: "text-amber-400", icon: Clock },
  LOW: { label: "Низкий", color: "text-zinc-400", icon: AlertCircle },
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
                  <p className="text-sm text-zinc-400">Высокий интерес</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {handoffs?.filter((h) => h.interest_level === "HIGH").length || 0}
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
                  <p className="text-sm text-zinc-400">Средний интерес</p>
                  <p className="mt-1 text-3xl font-bold text-zinc-100">
                    {handoffs?.filter((h) => h.interest_level === "MEDIUM").length || 0}
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
                  <p className="text-sm text-zinc-400">Всего тёплых</p>
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
            <CardTitle>Список тёплых лидов</CardTitle>
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
                    <TableHead>Контакт</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Интерес</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead>Дата</TableHead>
                    <TableHead></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {handoffs.map((handoff) => {
                    const interestConfig =
                      interestLevelConfig[handoff.interest_level] ||
                      interestLevelConfig.LOW
                    const InterestIcon = interestConfig.icon

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
                        <TableCell className="text-zinc-300">
                          {handoff.contact_name}
                        </TableCell>
                        <TableCell>
                          <a
                            href={`mailto:${handoff.contact_email}`}
                            className="flex items-center gap-1 text-indigo-400 hover:text-indigo-300"
                          >
                            <Mail className="h-3 w-3" />
                            {handoff.contact_email}
                          </a>
                        </TableCell>
                        <TableCell>
                          <span
                            className={`flex items-center gap-1 ${interestConfig.color}`}
                          >
                            <InterestIcon className="h-4 w-4" />
                            {interestConfig.label}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              handoff.status === "pending"
                                ? "warning"
                                : handoff.status === "contacted"
                                ? "default"
                                : "success"
                            }
                          >
                            {handoff.status === "pending"
                              ? "Ожидает"
                              : handoff.status === "contacted"
                              ? "Связались"
                              : "Закрыт"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-zinc-500">
                          {formatDateTime(handoff.created_at)}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <Phone className="h-4 w-4" />
                            </Button>
                            <Link href={`/leads/${handoff.lead_id}`}>
                              <Button variant="ghost" size="icon" className="h-8 w-8">
                                <ExternalLink className="h-4 w-4" />
                              </Button>
                            </Link>
                          </div>
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
                  Нет тёплых лидов
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
              Как работать с тёплыми лидами
            </h3>
            <ul className="space-y-2 text-sm text-zinc-400">
              <li className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-emerald-400 mt-0.5" />
                <span>
                  <strong className="text-zinc-300">Высокий интерес:</strong>{" "}
                  Свяжитесь в течение 24 часов
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Clock className="h-4 w-4 text-amber-400 mt-0.5" />
                <span>
                  <strong className="text-zinc-300">Средний интерес:</strong>{" "}
                  Свяжитесь в течение 48 часов
                </span>
              </li>
              <li className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-zinc-400 mt-0.5" />
                <span>
                  <strong className="text-zinc-300">Низкий интерес:</strong>{" "}
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

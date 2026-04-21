"use client"

import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { Header } from "@/components/header"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import {
  Send,
  Mail,
  CheckCircle2,
  XCircle,
  Loader2,
  User,
  FileText,
  Clock,
} from "lucide-react"

export default function TestEmailPage() {
  const [toEmail, setToEmail] = useState("")
  const [subject, setSubject] = useState("Тестовое письмо от Отклик")
  const [body, setBody] = useState(`Здравствуйте!

Это тестовое письмо для проверки работы email-рассылки.

Если вы получили это письмо — система работает корректно.

С уважением,
Команда Отклик`)
  const [fromName, setFromName] = useState("Отклик")

  const sendMutation = useMutation({
    mutationFn: () =>
      api.sendTestEmail({
        to_email: toEmail,
        subject,
        body,
        from_name: fromName,
      }),
  })

  const handleSend = () => {
    if (!toEmail || !subject || !body) return
    sendMutation.mutate()
  }

  const isValid = toEmail.includes("@") && subject.length > 0 && body.length > 0

  return (
    <div className="min-h-screen">
      <Header
        title="Тестовая отправка"
        description="Отправьте тестовое письмо на свой адрес"
      />

      <div className="p-6 max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-indigo-400" />
              Отправить тестовое письмо
            </CardTitle>
            <CardDescription>
              Проверьте работу email перед запуском кампании.
              Введите свой адрес и отредактируйте текст при необходимости.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* From Name */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                <User className="h-4 w-4 text-zinc-500" />
                Имя отправителя
              </label>
              <Input
                value={fromName}
                onChange={(e) => setFromName(e.target.value)}
                placeholder="Отклик"
              />
            </div>

            {/* To Email */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                <Mail className="h-4 w-4 text-zinc-500" />
                Email получателя
              </label>
              <Input
                type="email"
                value={toEmail}
                onChange={(e) => setToEmail(e.target.value)}
                placeholder="your@email.com"
              />
              <p className="text-xs text-zinc-500">
                Введите ваш email для тестовой отправки
              </p>
            </div>

            {/* Subject */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                <FileText className="h-4 w-4 text-zinc-500" />
                Тема письма
              </label>
              <Input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Тема письма"
              />
            </div>

            {/* Body */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300 flex items-center gap-2">
                <FileText className="h-4 w-4 text-zinc-500" />
                Текст письма
              </label>
              <Textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Текст письма..."
                className="min-h-[200px]"
              />
              <p className="text-xs text-zinc-500">
                {body.split(/\s+/).filter(Boolean).length} слов
              </p>
            </div>

            {/* Send Button */}
            <div className="flex items-center gap-4">
              <Button
                onClick={handleSend}
                disabled={!isValid || sendMutation.isPending}
                className="w-full sm:w-auto"
              >
                {sendMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Отправка...
                  </>
                ) : (
                  <>
                    <Send className="mr-2 h-4 w-4" />
                    Отправить тестовое письмо
                  </>
                )}
              </Button>

              {!isValid && (
                <p className="text-sm text-zinc-500">
                  Заполните все поля
                </p>
              )}
            </div>

            {/* Result */}
            {sendMutation.isSuccess && sendMutation.data && (
              <div className={`p-4 rounded-lg ${
                sendMutation.data.success
                  ? "bg-emerald-500/10 border border-emerald-500/20"
                  : "bg-red-500/10 border border-red-500/20"
              }`}>
                <div className="flex items-start gap-3">
                  {sendMutation.data.success ? (
                    <CheckCircle2 className="h-5 w-5 text-emerald-400 mt-0.5" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-400 mt-0.5" />
                  )}
                  <div className="flex-1">
                    <p className={`font-medium ${
                      sendMutation.data.success ? "text-emerald-400" : "text-red-400"
                    }`}>
                      {sendMutation.data.success
                        ? "Письмо успешно отправлено!"
                        : "Ошибка отправки"
                      }
                    </p>
                    {sendMutation.data.success ? (
                      <div className="mt-2 space-y-1 text-sm text-zinc-400">
                        <p className="flex items-center gap-2">
                          <Mail className="h-4 w-4" />
                          Получатель: {toEmail}
                        </p>
                        {sendMutation.data.sent_at && (
                          <p className="flex items-center gap-2">
                            <Clock className="h-4 w-4" />
                            Время: {new Date(sendMutation.data.sent_at).toLocaleString("ru-RU")}
                          </p>
                        )}
                        <p className="mt-2 text-zinc-500">
                          Проверьте папку &quot;Входящие&quot; или &quot;Спам&quot;
                        </p>
                      </div>
                    ) : (
                      <p className="mt-1 text-sm text-red-300">
                        {sendMutation.data.error || "Неизвестная ошибка"}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {sendMutation.isError && (
              <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20">
                <div className="flex items-start gap-3">
                  <XCircle className="h-5 w-5 text-red-400 mt-0.5" />
                  <div>
                    <p className="font-medium text-red-400">Ошибка</p>
                    <p className="mt-1 text-sm text-red-300">
                      {sendMutation.error instanceof Error
                        ? sendMutation.error.message
                        : "Не удалось отправить письмо"
                      }
                    </p>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tips */}
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-lg">Советы</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-zinc-400">
            <p>
              <Badge variant="outline" className="mr-2">1</Badge>
              Введите свой личный email для тестирования
            </p>
            <p>
              <Badge variant="outline" className="mr-2">2</Badge>
              Проверьте папку &quot;Спам&quot;, если письмо не пришло во входящие
            </p>
            <p>
              <Badge variant="outline" className="mr-2">3</Badge>
              Отредактируйте текст письма перед отправкой для проверки форматирования
            </p>
            <p>
              <Badge variant="outline" className="mr-2">4</Badge>
              Убедитесь, что SMTP-сервер настроен корректно в настройках системы
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

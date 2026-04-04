"use client"

import { useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { AlertTriangle, RefreshCw } from "lucide-react"

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <Card className="max-w-md w-full">
        <CardContent className="pt-6">
          <div className="flex flex-col items-center text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600/20 mb-4">
              <AlertTriangle className="h-8 w-8 text-red-400" />
            </div>
            <h2 className="text-xl font-semibold text-zinc-100 mb-2">
              Что-то пошло не так
            </h2>
            <p className="text-zinc-400 mb-6">
              Произошла ошибка при загрузке страницы. Попробуйте обновить или вернуться позже.
            </p>
            {error.message && (
              <p className="text-xs text-zinc-500 bg-zinc-800/50 rounded-lg p-3 mb-6 w-full font-mono">
                {error.message}
              </p>
            )}
            <Button onClick={reset}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Попробовать снова
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

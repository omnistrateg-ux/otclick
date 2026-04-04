import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { FileQuestion, Home } from "lucide-react"

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <Card className="max-w-md w-full">
        <CardContent className="pt-6">
          <div className="flex flex-col items-center text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-indigo-600/20 mb-4">
              <FileQuestion className="h-8 w-8 text-indigo-400" />
            </div>
            <h2 className="text-xl font-semibold text-zinc-100 mb-2">
              Страница не найдена
            </h2>
            <p className="text-zinc-400 mb-6">
              Запрашиваемая страница не существует или была перемещена.
            </p>
            <Link href="/">
              <Button>
                <Home className="mr-2 h-4 w-4" />
                На главную
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

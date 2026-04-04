"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import {
  Search,
  Mail,
  Database,
  Calculator,
  Pause,
  Play,
  X,
  CheckCircle,
  Loader2,
} from "lucide-react"

interface Task {
  id: string
  type: "discovery" | "enrichment" | "scoring" | "outreach"
  name: string
  progress: number
  total: number
  status: "running" | "paused" | "completed"
  startedAt: Date
}

// Симуляция активных задач
const MOCK_TASKS: Task[] = [
  {
    id: "1",
    type: "discovery",
    name: "IT компании Москвы",
    progress: 45,
    total: 100,
    status: "running",
    startedAt: new Date(Date.now() - 1000 * 60 * 15),
  },
  {
    id: "2",
    type: "enrichment",
    name: "Обогащение контактов",
    progress: 78,
    total: 150,
    status: "running",
    startedAt: new Date(Date.now() - 1000 * 60 * 30),
  },
  {
    id: "3",
    type: "outreach",
    name: "Рассылка: Ритейл Апрель",
    progress: 120,
    total: 200,
    status: "running",
    startedAt: new Date(Date.now() - 1000 * 60 * 60),
  },
]

const typeConfig = {
  discovery: { icon: Search, color: "text-indigo-400", bg: "bg-indigo-600/20" },
  enrichment: { icon: Database, color: "text-violet-400", bg: "bg-violet-600/20" },
  scoring: { icon: Calculator, color: "text-amber-400", bg: "bg-amber-600/20" },
  outreach: { icon: Mail, color: "text-emerald-400", bg: "bg-emerald-600/20" },
}

export function ActiveTasks() {
  const [tasks, setTasks] = useState<Task[]>(MOCK_TASKS)

  // Симуляция прогресса
  useEffect(() => {
    const interval = setInterval(() => {
      setTasks((prev) =>
        prev.map((task) => {
          if (task.status !== "running") return task
          const newProgress = Math.min(task.progress + Math.random() * 2, task.total)
          return {
            ...task,
            progress: newProgress,
            status: newProgress >= task.total ? "completed" : "running",
          }
        })
      )
    }, 1000)

    return () => clearInterval(interval)
  }, [])

  const toggleTask = (id: string) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.id === id
          ? {
              ...task,
              status: task.status === "running" ? "paused" : "running",
            }
          : task
      )
    )
  }

  const cancelTask = (id: string) => {
    setTasks((prev) => prev.filter((task) => task.id !== id))
  }

  const runningTasks = tasks.filter((t) => t.status === "running")

  if (tasks.length === 0) {
    return null
  }

  return (
    <Card className="border-indigo-600/30 bg-gradient-to-br from-indigo-600/10 to-transparent">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between text-base">
          <span className="flex items-center gap-2">
            <div className="relative">
              <Loader2 className="h-5 w-5 text-indigo-400 animate-spin" />
            </div>
            Активные задачи
          </span>
          <Badge variant="secondary">{runningTasks.length} выполняется</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {tasks.map((task) => {
          const config = typeConfig[task.type]
          const Icon = config.icon
          const percentage = Math.round((task.progress / task.total) * 100)

          return (
            <div
              key={task.id}
              className="p-3 rounded-lg bg-zinc-800/50 border border-zinc-700/50"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-md ${config.bg}`}>
                    <Icon className={`h-4 w-4 ${config.color}`} />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-zinc-200">
                      {task.name}
                    </p>
                    <p className="text-xs text-zinc-500">
                      {task.progress} / {task.total}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {task.status === "completed" ? (
                    <CheckCircle className="h-5 w-5 text-emerald-400" />
                  ) : (
                    <>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        onClick={() => toggleTask(task.id)}
                      >
                        {task.status === "running" ? (
                          <Pause className="h-4 w-4" />
                        ) : (
                          <Play className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-zinc-500 hover:text-red-400"
                        onClick={() => cancelTask(task.id)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Progress value={percentage} className="flex-1" />
                <span className="text-xs text-zinc-400 w-10 text-right">
                  {percentage}%
                </span>
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

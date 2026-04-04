"use client"

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import type { EmailPerformance } from "@/lib/api"

interface EmailPerformanceChartProps {
  data: EmailPerformance
}

export function EmailPerformanceChart({ data }: EmailPerformanceChartProps) {
  const chartData = [
    { name: "Отправлено", value: data.sent, fill: "#6366f1" },
    { name: "Доставлено", value: data.delivered, fill: "#8b5cf6" },
    { name: "Открыто", value: data.opened, fill: "#22c55e" },
    { name: "Клики", value: data.clicked, fill: "#f97316" },
    { name: "Ответы", value: data.replied, fill: "#eab308" },
    { name: "Отказы", value: data.bounced, fill: "#ef4444" },
  ]

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis dataKey="name" stroke="#71717a" fontSize={12} />
        <YAxis stroke="#71717a" fontSize={12} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#18181b",
            border: "1px solid #27272a",
            borderRadius: "8px",
          }}
          labelStyle={{ color: "#fafafa" }}
          itemStyle={{ color: "#a1a1aa" }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

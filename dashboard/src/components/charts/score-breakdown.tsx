"use client"

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from "recharts"

interface ScoreBreakdownProps {
  data: {
    hiring_intensity: number
    industry_fit: number
    contact_quality: number
    company_size: number
  }
}

export function ScoreBreakdown({ data }: ScoreBreakdownProps) {
  const chartData = [
    { subject: "Найм", value: data.hiring_intensity, fullMark: 100 },
    { subject: "Отрасль", value: data.industry_fit, fullMark: 100 },
    { subject: "Контакты", value: data.contact_quality, fullMark: 100 },
    { subject: "Размер", value: data.company_size, fullMark: 100 },
  ]

  return (
    <ResponsiveContainer width="100%" height={250}>
      <RadarChart data={chartData}>
        <PolarGrid stroke="#27272a" />
        <PolarAngleAxis dataKey="subject" stroke="#71717a" fontSize={12} />
        <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="#27272a" fontSize={10} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#18181b",
            border: "1px solid #27272a",
            borderRadius: "8px",
          }}
          labelStyle={{ color: "#fafafa" }}
        />
        <Radar
          name="Score"
          dataKey="value"
          stroke="#6366f1"
          fill="#6366f1"
          fillOpacity={0.4}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}

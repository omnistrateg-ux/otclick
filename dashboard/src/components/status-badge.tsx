import { Badge } from "@/components/ui/badge"

const statusConfig: Record<
  string,
  { label: string; variant: "default" | "secondary" | "success" | "warning" | "destructive" }
> = {
  LEAD_FOUND: { label: "Найден", variant: "secondary" },
  ENRICHMENT_DONE: { label: "Обогащён", variant: "default" },
  SCORED: { label: "Оценён", variant: "default" },
  QUALIFIED: { label: "Квалифицирован", variant: "success" },
  OUTREACH_SENT: { label: "Письмо отправлено", variant: "warning" },
  REPLY_RECEIVED: { label: "Получен ответ", variant: "success" },
  INTEREST_DETECTED: { label: "Интерес обнаружен", variant: "success" },
  HANDED_TO_MANAGER: { label: "Передан менеджеру", variant: "success" },
  CONVERTED: { label: "Конверсия", variant: "success" },
  ARCHIVED: { label: "Архив", variant: "secondary" },
  OPTED_OUT: { label: "Отписался", variant: "destructive" },
  DUPLICATE: { label: "Дубликат", variant: "destructive" },
  COOLDOWN: { label: "Пауза", variant: "warning" },
}

interface StatusBadgeProps {
  status: string
}

export function StatusBadge({ status }: StatusBadgeProps) {
  // Normalize status to uppercase for lookup (API may return lowercase like "lead_found")
  const normalizedStatus = status?.toUpperCase() || ""
  const config = statusConfig[normalizedStatus] || { label: status || "Неизвестно", variant: "secondary" as const }

  return <Badge variant={config.variant}>{config.label}</Badge>
}

import { Badge } from "@/components/ui/badge"

const statusConfig: Record<
  string,
  { label: string; variant: "default" | "secondary" | "success" | "warning" | "destructive" }
> = {
  LEAD_FOUND: { label: "Найден", variant: "secondary" },
  ENRICHED: { label: "Досье собрано", variant: "default" },
  ENRICHMENT_DONE: { label: "Досье собрано", variant: "default" },
  SCORED: { label: "Оценён", variant: "default" },
  EMAIL_READY: { label: "Письмо готово", variant: "default" },
  QUALIFIED: { label: "Горячий лид", variant: "success" },
  OUTREACH_SENT: { label: "Отправлено", variant: "warning" },
  REPLY_RECEIVED: { label: "Получен ответ", variant: "success" },
  INTEREST_DETECTED: { label: "Заинтересован", variant: "success" },
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

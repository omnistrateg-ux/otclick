import { formatDateTime } from "@/lib/utils"
import type { LeadEvent } from "@/lib/api"
import {
  Search,
  Database,
  Calculator,
  CheckCircle,
  Mail,
  MessageSquare,
  Heart,
  UserCheck,
  Archive,
  XCircle,
  Copy,
  Clock,
} from "lucide-react"

const eventIcons: Record<string, typeof Search> = {
  LEAD_DISCOVERED: Search,
  LEAD_ENRICHED: Database,
  LEAD_SCORED: Calculator,
  LEAD_QUALIFIED: CheckCircle,
  EMAIL_SENT: Mail,
  EMAIL_OPENED: Mail,
  EMAIL_CLICKED: Mail,
  REPLY_RECEIVED: MessageSquare,
  INTEREST_DETECTED: Heart,
  HANDED_TO_MANAGER: UserCheck,
  LEAD_ARCHIVED: Archive,
  LEAD_OPTED_OUT: XCircle,
  DUPLICATE_FOUND: Copy,
  COOLDOWN_STARTED: Clock,
}

interface LeadTimelineProps {
  events: LeadEvent[]
}

export function LeadTimeline({ events }: LeadTimelineProps) {
  return (
    <div className="relative space-y-4">
      {/* Vertical line */}
      <div className="absolute left-4 top-0 h-full w-px bg-zinc-800" />

      {events.map((event, index) => {
        const Icon = eventIcons[event.event_type] || Clock
        const isLast = index === events.length - 1

        return (
          <div key={event.id} className="relative flex gap-4 pb-4">
            <div className="relative z-10 flex h-8 w-8 items-center justify-center rounded-full bg-zinc-800 ring-4 ring-zinc-950">
              <Icon className="h-4 w-4 text-indigo-400" />
            </div>
            <div className="flex-1 pt-1">
              <p className="text-sm font-medium text-zinc-200">
                {event.description}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {formatDateTime(event.created_at)}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://176.126.166.94:8001/api/v1"

async function fetcher<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  })

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }

  return res.json()
}

// Types
export interface Lead {
  id: string
  company_name: string
  industry: string
  vacancy?: string
  city: string
  status: string
  score: number
  website?: string
  vacancies_count?: number
  created_at: string
  updated_at: string
  contacts: Contact[]
}

export interface Contact {
  id: string
  name: string
  role: string
  email: string
  phone?: string
}

export interface Campaign {
  id: string
  name: string
  description?: string
  status: string
  industries: string[]
  regions: string[]
  leads_discovered: number
  leads_qualified: number
  leads_converted: number
  created_at: string
  updated_at: string
}

export interface CampaignCreateRequest {
  name: string
  industries?: string[]
  vacancies?: string[]
  regions?: string[]
  daily_discovery_limit?: number
  auto_start?: boolean
}

export interface FunnelData {
  status: string
  count: number
  label: string
}

export interface EmailPerformance {
  sent: number
  delivered: number
  opened: number
  clicked: number
  replied: number
  bounced: number
}

export interface CostAnalytics {
  total_cost: number
  cost_per_lead: number
  cost_per_warm_lead: number
  llm_calls: number
  period: string
}

export interface Handoff {
  id: string
  lead_id: string
  company_name: string
  contact_name: string
  contact_email: string
  status: string
  interest_level: string
  notes?: string
  created_at: string
}

export interface LeadEvent {
  id: string
  event_type: string
  description: string
  created_at: string
  metadata?: Record<string, unknown>
}

export interface LeadEmail {
  id: string
  subject: string
  body: string
  status: string
  sent_at?: string
  opened_at?: string
  replied_at?: string
}

export interface Email {
  id: string
  lead_id: string
  company_name: string
  contact_name: string
  contact_email: string
  subject: string
  body: string
  status: "sent" | "delivered" | "opened" | "replied" | "bounced"
  sent_at: string
  opened_at?: string
  replied_at?: string
  thread?: EmailThread[]
}

export interface EmailThread {
  id: string
  direction: "outbound" | "inbound"
  subject: string
  body: string
  sent_at: string
}

export interface EmailsFilters {
  status?: string
  search?: string
  page?: number
  limit?: number
}

export interface EmailsResponse {
  items: Email[]
  total: number
  page: number
  limit: number
  pages: number
}

export interface LeadDetail extends Lead {
  events: LeadEvent[]
  emails: LeadEmail[]
  score_breakdown?: {
    hiring_intensity: number
    industry_fit: number
    contact_quality: number
    company_size: number
  }
}

export interface HealthStatus {
  status: string
  version?: string
  uptime?: number
}

export interface DiscoverCompany {
  name: string
  vacancy: string
  lead_id: string
  status: "created" | "exists" | "error"
}

export interface DiscoverResponse {
  task_id: string
  status: string
  leads_found: number
  leads_created: number
  companies: DiscoverCompany[]
}

export interface LeadsFilters {
  status?: string
  industry?: string
  city?: string
  score_min?: number
  score_max?: number
  search?: string
  page?: number
  limit?: number
}

export interface LeadsResponse {
  items: Lead[]
  total: number
  page: number
  limit: number
  pages: number
}

// Response wrappers for paginated endpoints
interface PaginatedResponse<T> {
  items: T[]
  total: number
}

// Funnel response from API (object with status keys)
interface FunnelResponse {
  funnel: Record<string, number>
}

// Status labels for funnel
const STATUS_LABELS: Record<string, string> = {
  discovered: "Найдено",
  lead_found: "Найдено",
  enrichment_done: "Обогащено",
  scored: "Оценено",
  qualified: "Квалифицировано",
  outreach_sent: "Отправлено",
  reply_received: "Получен ответ",
  interest_detected: "Интерес",
  handed_to_manager: "Передано",
  converted: "Конвертировано",
  archived: "В архиве",
  opted_out: "Отказ",
  duplicate: "Дубликат",
  cooldown: "Кулдаун",
}

// API functions
export const api = {
  // Health
  getHealth: () => fetcher<HealthStatus>("/health"),

  // Leads
  getLeads: (filters?: LeadsFilters) => {
    const params = new URLSearchParams()
    if (filters?.status) params.set("status", filters.status)
    if (filters?.industry) params.set("industry", filters.industry)
    if (filters?.city) params.set("city", filters.city)
    if (filters?.score_min) params.set("score_min", String(filters.score_min))
    if (filters?.score_max) params.set("score_max", String(filters.score_max))
    if (filters?.search) params.set("search", filters.search)
    if (filters?.page) params.set("page", String(filters.page))
    if (filters?.limit) params.set("limit", String(filters.limit))

    const query = params.toString()
    return fetcher<LeadsResponse>(`/leads${query ? `?${query}` : ""}`)
  },

  getLead: (id: string) => fetcher<LeadDetail>(`/leads/${id}`),

  discoverLeads: (params: { industry?: string; queries?: string[]; city?: string; max_leads?: number; campaign_id?: string }) =>
    fetcher<DiscoverResponse>("/leads/discover", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  sendCampaignEmails: (params: { campaign_id: string; subject: string; body: string }) =>
    fetcher<{ total: number; sent: number }>("/leads/send-campaign", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  // Campaigns - extract items from paginated response
  getCampaigns: async (): Promise<Campaign[]> => {
    const response = await fetcher<PaginatedResponse<Campaign>>("/campaigns")
    return response.items || []
  },
  getCampaign: (id: string) => fetcher<Campaign>(`/campaigns/${id}`),
  createCampaign: (data: CampaignCreateRequest) =>
    fetcher<Campaign>("/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // Analytics
  getFunnel: async (): Promise<FunnelData[]> => {
    const response = await fetcher<FunnelResponse>("/analytics/funnel")
    // Transform object {status: count} to array [{status, count, label}]
    // API returns object directly, not wrapped in {funnel: ...}
    const funnelObj = response.funnel || response || {}
    return Object.entries(funnelObj).map(([status, count]) => ({
      status: status.toUpperCase(),
      count,
      label: STATUS_LABELS[status.toLowerCase()] || status,
    }))
  },
  getEmailPerformance: () => fetcher<EmailPerformance>("/analytics/email-performance"),
  getCosts: () => fetcher<CostAnalytics>("/analytics/costs"),

  // Handoffs - extract items from paginated response
  getHandoffs: async (): Promise<Handoff[]> => {
    const response = await fetcher<PaginatedResponse<Handoff>>("/handoffs")
    return response.items || []
  },

  // Emails
  getEmails: (filters?: EmailsFilters) => {
    const params = new URLSearchParams()
    if (filters?.status) params.set("status", filters.status)
    if (filters?.search) params.set("search", filters.search)
    if (filters?.page) params.set("page", String(filters.page))
    if (filters?.limit) params.set("limit", String(filters.limit))

    const query = params.toString()
    return fetcher<EmailsResponse>(`/emails${query ? `?${query}` : ""}`)
  },

  getEmail: (id: string) => fetcher<Email>(`/emails/${id}`),
}

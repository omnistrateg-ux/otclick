const API_BASE = "http://176.126.166.94:8000/api/v1"

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
  leads_count: number
  emails_sent: number
  open_rate: number
  reply_rate: number
  created_at: string
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

  discoverLeads: (params: { industry?: string; city?: string }) =>
    fetcher<{ task_id: string }>("/leads/discover", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  // Campaigns
  getCampaigns: () => fetcher<Campaign[]>("/campaigns"),
  getCampaign: (id: string) => fetcher<Campaign>(`/campaigns/${id}`),

  // Analytics
  getFunnel: () => fetcher<FunnelData[]>("/analytics/funnel"),
  getEmailPerformance: () => fetcher<EmailPerformance>("/analytics/email-perf"),
  getCosts: () => fetcher<CostAnalytics>("/analytics/costs"),

  // Handoffs
  getHandoffs: () => fetcher<Handoff[]>("/handoffs"),
}

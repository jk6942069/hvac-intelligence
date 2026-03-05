import axios from 'axios'
import { supabase } from '../lib/supabase'
import type {
  Deal,
  DealFeedResponse,
  DashboardStats,
  CompDeal,
  MemoItem,
  DossierItem,
  PipelineStatus,
  PipelineRun,
  WorkflowStatus,
} from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ? `${import.meta.env.VITE_API_URL}/api` : '/api',
  timeout: 30_000,
})

// Attach Supabase JWT to every request
api.interceptors.request.use(async (config) => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// --- Deal Desk ---
export interface DealFeedParams {
  limit?: number
  offset?: number
  minConviction?: number | null
  maxConviction?: number | null
  state?: string
  workflowStatus?: string
  search?: string
  sortBy?: string
  sortOrder?: string
}

export const fetchDealFeed = (params: DealFeedParams = {}): Promise<DealFeedResponse> => {
  const q: Record<string, string | number> = {}
  if (params.limit) q.limit = params.limit
  if (params.offset) q.offset = params.offset
  if (params.minConviction != null) q.min_conviction = params.minConviction
  if (params.maxConviction != null) q.max_conviction = params.maxConviction
  if (params.state) q.state = params.state
  if (params.workflowStatus) q.workflow_status = params.workflowStatus
  if (params.search) q.search = params.search
  if (params.sortBy) q.sort_by = params.sortBy
  if (params.sortOrder) q.sort_order = params.sortOrder
  return api.get('/dealdesk/feed', { params: q }).then(r => r.data)
}

export const fetchTop5 = (): Promise<{ topDeals: Deal[] }> =>
  api.get('/dealdesk/top5').then(r => r.data)

export const fetchTearsheet = (companyId: string): Promise<Deal> =>
  api.get(`/dealdesk/tearsheet/${companyId}`).then(r => r.data)

// --- Workflow ---
export const updateWorkflow = (
  companyId: string,
  status: WorkflowStatus,
  notes?: string,
  contactDate?: string,
): Promise<void> =>
  api.put(`/workflow/${companyId}`, { status, notes, contact_date: contactDate }).then(r => r.data)

// --- Companies (legacy) ---
export interface ListCompaniesParams {
  page?: number; limit?: number; sortBy?: string; sortOrder?: string
  minScore?: number | null; maxScore?: number | null; state?: string
  status?: string; search?: string
}
export const fetchCompanies = (params: ListCompaniesParams = {}) => {
  const q: Record<string, string | number> = {}
  if (params.page) q.page = params.page
  if (params.limit) q.limit = params.limit
  if (params.sortBy) q.sort_by = params.sortBy
  if (params.sortOrder) q.sort_order = params.sortOrder
  if (params.minScore != null) q.min_score = params.minScore
  if (params.maxScore != null) q.max_score = params.maxScore
  if (params.state) q.state = params.state
  if (params.status) q.status = params.status
  if (params.search) q.search = params.search
  return api.get('/companies', { params: q }).then(r => r.data)
}

export const fetchCompany = (id: string): Promise<Deal> =>
  api.get(`/companies/${id}`).then(r => r.data)

// --- Comps ---
export const fetchComps = (): Promise<{ comps: CompDeal[] }> =>
  api.get('/comps').then(r => r.data)

// --- Memos ---
export const fetchMemos = (companyId: string): Promise<{ memos: MemoItem[] }> =>
  api.get(`/memos/${companyId}`).then(r => r.data)

export const generateMemo = (companyId: string): Promise<{ memoId: string; version: number }> =>
  api.post(`/memos/${companyId}/generate`).then(r => r.data)

export const updateMemo = (memoId: string, content: string, title?: string): Promise<void> =>
  api.put(`/memos/${memoId}`, { content, title }).then(r => r.data)

// --- Dossiers ---
export const generateDossier = (companyId: string): Promise<void> =>
  api.post(`/dossiers/${companyId}/generate`).then(r => r.data)

export const fetchDossiers = (page: number = 1, limit: number = 50): Promise<{ dossiers: DossierItem[]; total: number; pages: number }> =>
  api.get('/dossiers', { params: { page, limit } }).then(r => r.data)

// --- Feedback ---
export const submitFeedback = (companyId: string, outcome: string, notes: string): Promise<void> =>
  api.put(`/companies/${companyId}/feedback`, { outcome, notes }).then(r => r.data)

// --- Pipeline ---
export interface RunPipelineParams {
  cities?: string[]; states?: string[]; maxCompanies?: number; generateDossiersForTop?: number
}
export const startPipeline = (params: RunPipelineParams = {}) =>
  api.post('/pipeline/run', {
    cities: params.cities, states: params.states,
    max_companies: params.maxCompanies ?? 200,
    generate_dossiers_for_top: params.generateDossiersForTop ?? 20,
  }).then(r => r.data)

export const fetchPipelineStatus = (): Promise<PipelineStatus> =>
  api.get('/pipeline/status').then(r => r.data)

export const fetchPipelineHistory = (): Promise<PipelineRun[]> =>
  api.get('/pipeline/history').then(r => r.data)

// --- Stats ---
export const fetchDashboardStats = (): Promise<DashboardStats> =>
  api.get('/stats/dashboard').then(r => r.data)

// --- Config ---
export const fetchConfig = () => api.get('/config').then(r => r.data)
export const updateConfig = (config: {
  googlePlacesApiKey?: string; anthropicApiKey?: string; useMockData?: boolean
}) => api.put('/config', config).then(r => r.data)

// --- WebSocket ---
export const createPipelineSocket = async (
  onMessage: (data: Record<string, unknown>) => void,
  onClose?: () => void
): Promise<WebSocket> => {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token ?? ''
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const apiBase = import.meta.env.VITE_API_URL ?? ''
  const wsHost = apiBase
    ? new URL(apiBase.replace(/^https?/, 'ws')).host
    : window.location.host
  const ws = new WebSocket(`${proto}//${wsHost}/api/pipeline/ws?token=${token}`)
  ws.onmessage = e => { try { onMessage(JSON.parse(e.data)) } catch { } }
  ws.onclose = onClose ?? (() => {})
  return ws
}

// --- Billing ---
export const fetchBillingStatus = () =>
  api.get('/billing/status').then(r => r.data)

export const createCheckout = (plan: 'starter' | 'professional') =>
  api.post('/billing/create-checkout', { plan }).then(r => r.data)

export const openBillingPortal = () =>
  api.post('/billing/portal').then(r => r.data)

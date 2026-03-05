export interface Signal {
  type: string
  label: string
  severity: 'high' | 'medium' | 'low'
  description: string
  points: number
}

export interface ValuationBand {
  low: number
  mid: number
  high: number
  multipleRange: string
  basis: string
  disclaimer?: string
}

export interface ScoreExplanation {
  transitionFactors: string[]
  qualityFactors: string[]
  platformFactors: string[]
  thesisBullets: string[]
  keyRisks: string[]
  valuationBand: ValuationBand
  recommendedAction: string
  subscores: {
    transition: number
    quality: number
    platform: number
  }
}

export type WorkflowStatus =
  | 'not_contacted'
  | 'contacted'
  | 'responded'
  | 'interested'
  | 'not_interested'
  | 'follow_up'
  | 'closed_lost'
  | 'closed_won'

export interface WorkflowEvent {
  id: string
  fromStatus: WorkflowStatus
  toStatus: WorkflowStatus
  notes: string | null
  createdAt: string | null
}

export interface Company {
  id: string
  name: string
  address: string
  city: string
  state: string
  phone: string
  website: string
  email?: string
  googlePlaceId?: string
  googleRating: number | null
  googleReviewCount: number | null
  category?: string
  domain?: string
  domainAgeYears: number | null
  sslValid: boolean | null
  sslExpiry?: string | null
  techStack?: string[]
  websiteActive: boolean | null
  websiteLoadTimeMs?: number | null
  websiteLastChecked?: string | null
  hasFacebook: boolean | null
  hasInstagram: boolean | null
  websiteOutdated?: boolean | null
  signals: Signal[]
  // Old score fields (backward compat)
  score: number
  scoreBreakdown?: Record<string, number>
  // New scoring
  convictionScore: number
  transitionScore: number
  qualityScore: number
  platformScore: number
  scoreExplanation?: ScoreExplanation
  // Thesis / risks
  thesisBullets: string[]
  keyRisks: string[]
  valuationBand: ValuationBand
  recommendedAction: string
  transitionFactors: string[]
  qualityFactors: string[]
  platformFactors: string[]
  // Workflow
  workflowStatus: WorkflowStatus
  workflowNotes?: string | null
  outreachDate?: string | null
  lastContactDate?: string | null
  // Status
  status: string
  rank: number | null
  hasDossier: boolean
  hasMemo: boolean
  createdAt: string | null
  updatedAt: string | null
}

export interface Deal extends Company {}

export interface DossierDetail {
  id: string
  content: string
  generatedAt: string | null
  modelUsed: string
}

export interface MemoItem {
  id: string
  companyId: string
  version: number
  title: string
  content: string
  status: 'draft' | 'final' | 'generating'
  generatedAt?: string | null
  updatedAt: string | null
  modelUsed?: string
}

export interface CompDeal {
  id: string
  dealName: string
  dealYear: number
  geography: string
  dealType: string
  revenueRange: string
  ebitdaMultipleLow: number
  ebitdaMultipleHigh: number
  sdeMultipleLow: number
  sdeMultipleHigh: number
  notes: string
  source: string
}

export interface DealFeedResponse {
  deals: Deal[]
  total: number
  offset: number
  limit: number
}

export interface PipelineRun {
  id: string
  status: 'running' | 'completed' | 'failed'
  stage: string
  total: number
  processed: number
  startedAt: string | null
  completedAt: string | null
  error: string | null
}

export interface PipelineStatus {
  isRunning: boolean
  currentRunId: string | null
  lastRun: PipelineRun | null
}

export interface DashboardStats {
  totalCompanies: number
  highScoreCompanies: number
  topCandidates: number
  dossiersGenerated: number
  avgScore: number
  pipelineRuns: number
  scoreDistribution: { range: string; count: number }[]
  topStates: { state: string; count: number }[]
  recentTargets: Deal[]
}

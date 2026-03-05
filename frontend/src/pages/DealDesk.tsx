import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  RefreshCw, Star, Globe, Phone, ChevronDown,
  Target, ShieldAlert, DollarSign, FileText,
  Clock, Zap, MapPin
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchDealFeed, fetchTop5, fetchTearsheet, updateWorkflow, generateMemo, fetchComps
} from '../api/client'
import type { Deal, WorkflowStatus, MemoItem } from '../types'
import ReactMarkdown from 'react-markdown'

const fmtDollar = (n: number) =>
  n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` :
  n >= 1_000 ? `$${(n / 1_000).toFixed(0)}K` : `$${n}`

const scoreColor = (s: number) =>
  s >= 60 ? 'text-terminal-green' : s >= 40 ? 'text-terminal-amber' : 'text-terminal-red'

const scoreBg = (s: number) =>
  s >= 60 ? 'bg-terminal-green/10 border-terminal-green/20' :
  s >= 40 ? 'bg-terminal-amber/10 border-terminal-amber/20' :
  'bg-terminal-red/10 border-terminal-red/20'

const WORKFLOW_LABELS: Record<string, string> = {
  not_contacted: 'Not Contacted',
  contacted: 'Contacted',
  responded: 'Responded',
  interested: 'Interested',
  not_interested: 'Not Interested',
  follow_up: 'Follow-Up',
  closed_lost: 'Closed Lost',
  closed_won: 'Closed Won',
}

const WORKFLOW_STATUSES = Object.keys(WORKFLOW_LABELS) as WorkflowStatus[]

const US_STATES = [
  'AL','AZ','AR','CA','CO','CT','DE','FL','GA','ID','IL','IN','IA','KS',
  'KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
  'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT',
  'VT','VA','WA','WV','WI','WY',
]
function ConvictionScoreBadge({ score }: { score: number }) {
  return (
    <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border font-mono font-semibold text-base ${scoreBg(score)} ${scoreColor(score)}`}>
      {score}
      <span className="text-xs font-normal opacity-60">/100</span>
    </div>
  )
}

function SubScorePill({ label, value, max, color }: { label: string; value: number; max: number; color: string }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div className="flex items-center gap-2">
      <span className="terminal-label w-20 shrink-0">{label}</span>
      <div className="flex-1 h-1 bg-surface-600 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`font-mono text-xs w-8 text-right ${color.replace("bg-", "text-").replace("/20","")}`}>{value}</span>
    </div>
  )
}

function WorkflowBadge({ status }: { status: string }) {
  return <span className={`badge workflow-${status}`}>{WORKFLOW_LABELS[status] || status}</span>
}

function SignalChip({ sig }: { sig: { type: string; label: string; severity: string } }) {
  const colors: Record<string, string> = { high: "badge-high", medium: "badge-medium", low: "badge-neutral" }
  return <span className={`badge ${colors[sig.severity] || "badge-neutral"}`}>{sig.label}</span>
}

interface ScreenerFilters {
  search: string
  state: string
  minConviction: number
  workflowStatus: string
  sortBy: string
}

function ScreenerPanel({ filters, onChange, total }: {
  filters: ScreenerFilters
  onChange: (f: Partial<ScreenerFilters>) => void
  total: number
}) {
  return (
    <div className="w-52 shrink-0 flex flex-col h-full border-r border-surface-600 bg-navy-800">
      <div className="px-4 py-3 border-b border-surface-600">
        <div className="terminal-label text-[10px] mb-2">DEAL FILTER</div>
        <input
          type="text"
          placeholder="Search targets..."
          value={filters.search}
          onChange={e => onChange({ search: e.target.value })}
          className="w-full bg-surface-700 border border-surface-500 rounded px-3 py-1.5 text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-accent/50 font-mono"
        />
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5">
        <div>
          <div className="terminal-label text-[10px] mb-2">SORT BY</div>
          <select value={filters.sortBy} onChange={e => onChange({ sortBy: e.target.value })} className="w-full bg-surface-700 border border-surface-500 rounded px-2 py-1.5 text-xs text-slate-300 outline-none">
            <option value="conviction_score">Conviction Score</option>
            <option value="transition_score">Transition Pressure</option>
            <option value="quality_score">Business Quality</option>
            <option value="platform_score">Platform Fit</option>
            <option value="google_rating">Rating</option>
            <option value="google_review_count">Review Count</option>
          </select>
        </div>
        <div>
          <div className="terminal-label text-[10px] mb-2">MIN CONVICTION: <span className="text-accent">{filters.minConviction}</span></div>
          <input type="range" min={0} max={80} step={5} value={filters.minConviction} onChange={e => onChange({ minConviction: Number(e.target.value) })} className="w-full accent-accent" />
          <div className="flex justify-between text-[10px] text-slate-600 font-mono mt-1"><span>0</span><span>40</span><span>80</span></div>
        </div>
        <div>
          <div className="terminal-label text-[10px] mb-2">MARKET (STATE)</div>
          <select value={filters.state} onChange={e => onChange({ state: e.target.value })} className="w-full bg-surface-700 border border-surface-500 rounded px-2 py-1.5 text-xs text-slate-300 outline-none">
            <option value="">All Markets</option>
            <optgroup label="Premium (Sun Belt)">{["AZ","TX","FL","TN","NC","GA","SC","NV"].map(s => <option key={s} value={s}>{s}</option>)}</optgroup>
            <optgroup label="All States">{US_STATES.map(s => <option key={s} value={s}>{s}</option>)}</optgroup>
          </select>
        </div>
        <div>
          <div className="terminal-label text-[10px] mb-2">WORKFLOW STATUS</div>
          <select value={filters.workflowStatus} onChange={e => onChange({ workflowStatus: e.target.value })} className="w-full bg-surface-700 border border-surface-500 rounded px-2 py-1.5 text-xs text-slate-300 outline-none">
            <option value="">All Statuses</option>
            {WORKFLOW_STATUSES.map(s => <option key={s} value={s}>{WORKFLOW_LABELS[s]}</option>)}
          </select>
        </div>
        <div className="pt-2 border-t border-surface-600">
          <div className="terminal-label text-[10px]">TARGETS</div>
          <div className="font-mono text-lg text-accent font-semibold">{total}</div>
        </div>
      </div>
    </div>
  )
}

function DealFeedItem({ deal, selected, onClick, index }: { deal: Deal; selected: boolean; onClick: () => void; index: number }) {
  return (
    <div className={`deal-row ${selected ? "selected" : ""}`} onClick={onClick}>
      <div className="w-6 shrink-0 pt-0.5">
        <span className="terminal-label text-[10px]">{String(index + 1).padStart(2, "0")}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-sm font-medium text-slate-200 truncate leading-tight">{deal.name}</div>
            <div className="flex items-center gap-1.5 mt-0.5">
              <MapPin size={10} className="text-slate-600 shrink-0" />
              <span className="text-xs text-slate-500 font-mono">{deal.city}, {deal.state}</span>
            </div>
          </div>
          <div className={`font-mono text-base font-bold shrink-0 ${scoreColor(deal.convictionScore)}`}>{deal.convictionScore}</div>
        </div>
        <div className="flex items-center gap-3 mt-1.5">
          {deal.googleRating != null && (
            <span className="flex items-center gap-1 text-xs text-slate-400">
              <Star size={10} className="text-terminal-amber" />
              <span className="font-mono">{deal.googleRating?.toFixed(1)}</span>
            </span>
          )}
          {deal.googleReviewCount != null && <span className="text-xs text-slate-500 font-mono">{deal.googleReviewCount}rev</span>}
          {deal.domainAgeYears != null && <span className="text-xs text-slate-500 font-mono">{Math.round(deal.domainAgeYears)}yr</span>}
          <WorkflowBadge status={deal.workflowStatus} />
          {deal.councilAnalyzed && (
            <span className="text-[10px] font-mono text-accent/70">&#x2696;</span>
          )}
          {deal.discoverySource === "firecrawl_search" && (
            <span className="text-[10px] font-mono text-slate-600">live</span>
          )}
        </div>
        {deal.thesisBullets?.[0] && <div className="mt-1.5 text-xs text-slate-500 leading-snug line-clamp-1 italic">{deal.thesisBullets[0]}</div>}
      </div>
    </div>
  )
}

type TearsheetTab = "thesis" | "signals" | "valuation" | "workflow" | "memo"

function DecisionPane({ deal, onWorkflowUpdate }: {
  deal: Deal | null
  onWorkflowUpdate: (id: string, status: WorkflowStatus, notes?: string) => void
}) {
  const [activeTab, setActiveTab] = useState<TearsheetTab>("thesis")
  const [workflowOpen, setWorkflowOpen] = useState(false)
  const [wfNotes, setWfNotes] = useState("")
  const [generatingMemo, setGeneratingMemo] = useState(false)
  const queryClient = useQueryClient()

  const { data: tearsheet } = useQuery({
    queryKey: ["tearsheet", deal?.id],
    queryFn: () => fetchTearsheet(deal!.id),
    enabled: !!deal,
    staleTime: 30_000,
  })

  const { data: compsData } = useQuery({
    queryKey: ["comps"],
    queryFn: fetchComps,
    staleTime: 300_000,
  })

  const activeDeal = tearsheet || deal
  useEffect(() => { setActiveTab("thesis"); setWfNotes("") }, [deal?.id])

  if (!deal) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-navy-gradient text-slate-600">
        <Target size={32} className="mb-3 opacity-30" />
        <p className="text-sm font-display">Select a target to view decision pane</p>
        <p className="text-xs mt-1 font-mono">Ctrl+K to search</p>
      </div>
    )
  }

  const vb = activeDeal?.valuationBand
  const tabs: { id: TearsheetTab; label: string; icon: typeof Target }[] = [
    { id: "thesis", label: "Thesis", icon: Target },
    { id: "signals", label: "Signals", icon: Zap },
    { id: "valuation", label: "Valuation", icon: DollarSign },
    { id: "workflow", label: "Workflow", icon: Clock },
    { id: "memo", label: "Memo", icon: FileText },
  ]

  return (
    <div className="flex flex-col h-full bg-navy-gradient border-l border-surface-600">
      <div className="px-5 pt-4 pb-3 border-b border-surface-600 shrink-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-display font-semibold text-slate-100 leading-tight truncate">{activeDeal?.name}</h2>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="flex items-center gap-1 text-xs text-slate-400 font-mono"><MapPin size={10} />{activeDeal?.city}, {activeDeal?.state}</span>
              {activeDeal?.googleRating && <span className="flex items-center gap-1 text-xs text-slate-400 font-mono"><Star size={10} className="text-terminal-amber" />{activeDeal.googleRating.toFixed(1)} ({activeDeal.googleReviewCount} rev)</span>}
            </div>
          </div>
          <ConvictionScoreBadge score={activeDeal?.convictionScore || 0} />
        </div>
        <div className="mt-3 space-y-1.5">
          <SubScorePill label="Transition" value={activeDeal?.transitionScore || 0} max={40} color="bg-terminal-amber/60" />
          <SubScorePill label="Quality" value={activeDeal?.qualityScore || 0} max={35} color="bg-terminal-green/60" />
          <SubScorePill label="Platform" value={activeDeal?.platformScore || 0} max={25} color="bg-blue-400/60" />
        </div>
        <div className="flex gap-2 mt-3">
          {activeDeal?.phone && <a href={`tel:${activeDeal.phone}`} className="btn-ghost text-xs flex items-center gap-1.5 py-1.5 px-2"><Phone size={12} /> Call</a>}
          {activeDeal?.website && <a href={activeDeal.website} target="_blank" rel="noopener noreferrer" className="btn-ghost text-xs flex items-center gap-1.5 py-1.5 px-2"><Globe size={12} /> Website</a>}
          <button
            onClick={() => {
              setGeneratingMemo(true)
              generateMemo(deal.id).finally(() => {
                setGeneratingMemo(false)
                queryClient.invalidateQueries({ queryKey: ["tearsheet", deal.id] })
                setActiveTab("memo")
              })
            }}
            disabled={generatingMemo}
            className="btn-secondary text-xs flex items-center gap-1.5 py-1.5 px-2 ml-auto"
          >
            <FileText size={12} />
            {generatingMemo ? "Generating..." : "Gen Memo"}
          </button>
        </div>
      </div>

      <div className="flex gap-0 border-b border-surface-600 shrink-0 px-5">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-2.5 text-xs border-b-2 transition-colors -mb-px ${
              activeTab === tab.id ? "border-accent text-accent" : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            <tab.icon size={11} />{tab.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {activeTab === "thesis" && (
          <div className="space-y-5">
            {/* Council consensus badge */}
            {activeDeal?.councilAnalyzed && (
              <div className="glass-card p-3 border-accent/30 bg-accent/5">
                <div className="flex items-center gap-2">
                  <span className="text-accent text-xs font-mono font-semibold">&#x2696; COUNCIL ANALYSIS</span>
                  <span className="text-xs text-slate-500 ml-auto font-mono">3-model deliberation complete</span>
                </div>
                <p className="text-xs text-slate-400 mt-1">View the full council investment thesis in the Memo tab.</p>
              </div>
            )}
            {/* existing thesis content follows */}
            <div className="glass-card p-4 border-accent/20 bg-accent/5">
              <div className="terminal-label text-[10px] mb-2 text-accent">RECOMMENDED ACTION</div>
              <p className="text-sm text-slate-200 font-medium">{activeDeal?.recommendedAction}</p>
            </div>
            <div>
              <div className="terminal-label text-[10px] mb-3 flex items-center gap-1.5">
                <Target size={10} className="text-terminal-green" />WHY BUY - ACQUISITION THESIS
              </div>
              <ul className="space-y-2">
                {(activeDeal?.thesisBullets || []).map((bullet, i) => (
                  <li key={i} className="flex gap-2.5 text-sm text-slate-300 leading-snug">
                    <span className="text-terminal-green shrink-0 mt-0.5">&#x25B8;</span>
                    <span>{bullet}</span>
                  </li>
                ))}
                {(!activeDeal?.thesisBullets?.length) && <li className="text-sm text-slate-600 italic">Run pipeline to generate thesis</li>}
              </ul>
            </div>
            <div>
              <div className="terminal-label text-[10px] mb-3 flex items-center gap-1.5">
                <ShieldAlert size={10} className="text-terminal-red" />KEY RISKS
              </div>
              <ul className="space-y-2">
                {(activeDeal?.keyRisks || []).map((risk, i) => (
                  <li key={i} className="flex gap-2.5 text-sm text-slate-400 leading-snug">
                    <span className="text-terminal-red/70 shrink-0 mt-0.5">&#x25B8;</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="glass-card p-4">
              <div className="terminal-label text-[10px] mb-3">SCOUT SUMMARY</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                {[
                  ["Market", `${activeDeal?.city}, ${activeDeal?.state}`],
                  ["Tenure", activeDeal?.domainAgeYears ? `${Math.round(activeDeal.domainAgeYears)}+ years` : "Unknown"],
                  ["Rating", activeDeal?.googleRating ? `${activeDeal.googleRating.toFixed(1)} stars (${activeDeal.googleReviewCount} reviews)` : "No data"],
                  ["Digital", activeDeal?.websiteActive ? "Website active" : "Website down"],
                  ["Social", (activeDeal?.hasFacebook || activeDeal?.hasInstagram) ? "Present" : "None detected"],
                  ["Workflow", WORKFLOW_LABELS[activeDeal?.workflowStatus || "not_contacted"]],
                ].map(([label, value]) => (
                  <div key={label} className="flex gap-2">
                    <span className="terminal-label text-[10px] w-14 shrink-0">{label}</span>
                    <span className="text-slate-300 font-mono text-xs">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "signals" && (
          <div className="space-y-4">
            <div className="terminal-label text-[10px] mb-3">OWNERSHIP LIFECYCLE SIGNALS</div>
            {(activeDeal?.signals || []).length === 0 && <p className="text-sm text-slate-600 italic">No signals detected - run enrichment pipeline.</p>}
            <div className="space-y-2">
              {(activeDeal?.signals || []).map((sig, i) => (
                <div key={i} className="glass-card p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <SignalChip sig={sig} />
                    <span className="ml-auto font-mono text-xs text-slate-500">+{sig.points}pts</span>
                  </div>
                  <p className="text-xs text-slate-400 leading-snug">{sig.description}</p>
                </div>
              ))}
            </div>
            {(activeDeal?.techStack || []).length > 0 && (
              <div className="mt-4">
                <div className="terminal-label text-[10px] mb-2">TECH STACK</div>
                <div className="flex flex-wrap gap-1.5">{activeDeal?.techStack?.map(t => <span key={t} className="badge badge-neutral">{t}</span>)}</div>
              </div>
            )}
          </div>
        )}

        {activeTab === "valuation" && (
          <div className="space-y-5">
            {vb && (
              <>
                <div className="glass-card p-5">
                  <div className="terminal-label text-[10px] mb-4">VALUATION BAND</div>
                  <div className="flex items-end gap-3 justify-between">
                    <div className="text-center"><div className="terminal-label text-[10px]">LOW</div><div className="font-display text-lg font-semibold text-slate-400">{fmtDollar(vb.low)}</div></div>
                    <div className="text-center flex-1"><div className="terminal-label text-[10px] text-accent">MID</div><div className="font-display text-2xl font-bold text-accent">{fmtDollar(vb.mid)}</div></div>
                    <div className="text-center"><div className="terminal-label text-[10px]">HIGH</div><div className="font-display text-lg font-semibold text-slate-400">{fmtDollar(vb.high)}</div></div>
                  </div>
                  <div className="mt-4 h-1.5 bg-surface-600 rounded-full overflow-hidden"><div className="h-full score-bar-fill rounded-full" style={{ width: "70%" }} /></div>
                  <div className="mt-3 flex items-center justify-between">
                    <span className="terminal-label text-[10px]">MULTIPLE RANGE</span>
                    <span className="font-mono text-xs text-slate-300">{vb.multipleRange}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-2 italic">{vb.basis}</p>
                  {vb.disclaimer && <p className="text-xs text-terminal-amber/70 mt-1">{vb.disclaimer}</p>}
                </div>
                {(compsData?.comps || []).length > 0 && (
                  <div>
                    <div className="terminal-label text-[10px] mb-3">PROXY COMPARABLE DEALS</div>
                    <div className="space-y-2">
                      {(compsData?.comps || []).slice(0, 4).map(comp => (
                        <div key={comp.id} className="glass-card p-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs text-slate-300 font-medium">{comp.dealName}</span>
                            <span className="badge badge-neutral">{comp.dealYear}</span>
                          </div>
                          <div className="flex gap-3 text-xs text-slate-500">
                            <span className="font-mono">{comp.geography}</span>
                            <span>|</span>
                            <span className="font-mono">{comp.sdeMultipleLow}x-{comp.sdeMultipleHigh}x SDE</span>
                            <span>|</span>
                            <span className="font-mono">{comp.revenueRange}</span>
                          </div>
                          {comp.notes && <p className="text-xs text-slate-600 mt-1 italic">{comp.notes}</p>}
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-slate-600 mt-2 italic">Proxy comps only - source: HVAC industry transaction databases. Verify with broker data.</p>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {activeTab === "workflow" && (
          <div className="space-y-4">
            <div className="terminal-label text-[10px] mb-3">CRM STATUS</div>
            <div className="flex items-center gap-3 mb-4">
              <WorkflowBadge status={activeDeal?.workflowStatus || "not_contacted"} />
              <button onClick={() => setWorkflowOpen(!workflowOpen)} className="btn-ghost text-xs py-1 flex items-center gap-1.5">
                Update <ChevronDown size={12} className={workflowOpen ? "rotate-180 transition-transform" : "transition-transform"} />
              </button>
            </div>
            {workflowOpen && (
              <div className="glass-card p-4 space-y-3">
                <div className="terminal-label text-[10px]">SET STATUS</div>
                <div className="grid grid-cols-2 gap-2">
                  {WORKFLOW_STATUSES.map(s => (
                    <button
                      key={s}
                      onClick={() => { onWorkflowUpdate(deal.id, s, wfNotes || undefined); setWorkflowOpen(false) }}
                      className={`text-xs px-3 py-2 rounded border transition-colors text-left workflow-${s} hover:opacity-80`}
                    >
                      {WORKFLOW_LABELS[s]}
                    </button>
                  ))}
                </div>
                <textarea value={wfNotes} onChange={e => setWfNotes(e.target.value)} placeholder="Add notes (optional)..." className="w-full bg-surface-700 border border-surface-500 rounded px-3 py-2 text-xs text-slate-300 placeholder-slate-600 outline-none resize-none h-20 font-mono" />
              </div>
            )}
            {activeDeal?.workflowNotes && (
              <div className="glass-card p-3">
                <div className="terminal-label text-[10px] mb-1.5">LAST NOTES</div>
                <p className="text-xs text-slate-400">{activeDeal.workflowNotes}</p>
              </div>
            )}
            {(tearsheet as any)?.workflowEvents?.length > 0 && (
              <div>
                <div className="terminal-label text-[10px] mb-2">ACTIVITY TIMELINE</div>
                <div className="space-y-2">
                  {((tearsheet as any).workflowEvents as any[]).map((ev: any) => (
                    <div key={ev.id} className="flex gap-3 text-xs">
                      <div className="w-1.5 h-1.5 rounded-full bg-accent/50 mt-1 shrink-0" />
                      <div>
                        <span className="text-slate-400">{ev.fromStatus} to {ev.toStatus}</span>
                        {ev.notes && <p className="text-slate-600 italic">{ev.notes}</p>}
                        <p className="text-slate-600 font-mono">{ev.createdAt ? new Date(ev.createdAt).toLocaleDateString() : ""}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="mt-4">
              <div className="terminal-label text-[10px] mb-3">OUTREACH ANGLES</div>
              {[
                { angle: "Legacy and Succession", msg: `Hi [Owner], I work with investors who specialize in HVAC business acquisitions. I noticed ${activeDeal?.name} has been serving ${activeDeal?.city} for many years, and I was curious whether you have ever considered what a transition might look like for you...` },
                { angle: "Operational Lift", msg: `Hi [Owner], our firm has helped HVAC operators like you add $200K+ in value through maintenance contract programs and technician scaling. Happy to share what that could look like for ${activeDeal?.name}...` },
              ].map(({ angle, msg }) => (
                <div key={angle} className="glass-card p-3 mb-2">
                  <div className="terminal-label text-[10px] mb-1.5">{angle}</div>
                  <p className="text-xs text-slate-400 italic leading-relaxed">{msg}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "memo" && (
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="terminal-label text-[10px] flex items-center gap-2">
                INVESTMENT MEMO
                {(tearsheet as any)?.memos?.[0]?.modelUsed === "council-v1" && (
                  <span className="text-accent text-[10px] font-mono">&#x2696; COUNCIL</span>
                )}
              </div>
              <button
                onClick={() => {
                  setGeneratingMemo(true)
                  generateMemo(deal.id).finally(() => {
                    setGeneratingMemo(false)
                    queryClient.invalidateQueries({ queryKey: ["tearsheet", deal.id] })
                  })
                }}
                disabled={generatingMemo}
                className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
              >
                <FileText size={12} />
                {generatingMemo ? "Generating..." : (tearsheet as any)?.memos?.length > 0 ? "Regen" : "Generate"}
              </button>
            </div>
            {(tearsheet as any)?.memos?.length > 0 ? (
              <MemoViewer companyId={deal.id} memoMeta={(tearsheet as any).memos[0]} />
            ) : (
              <div className="text-center py-8 text-slate-600">
                <FileText size={24} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">No memo yet</p>
                <p className="text-xs mt-1">Click Generate to create an IC-style memo</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function MemoViewer({ companyId, memoMeta }: { companyId: string; memoMeta: any }) {
  const { data, isLoading } = useQuery({
    queryKey: ["memo", companyId],
    queryFn: async () => { const res = await fetch(`/api/memos/${companyId}`); return res.json() },
    staleTime: 30_000,
  })
  const memo: MemoItem | undefined = data?.memos?.[0]
  if (isLoading) return <div className="text-sm text-slate-500 py-4">Loading memo...</div>
  if (!memo) return <div className="text-sm text-slate-600 py-4 italic">Memo not found</div>
  if (memo.status === "generating") return (
    <div className="text-sm text-slate-500 py-4 flex items-center gap-2">
      <span className="pulse-dot inline-block w-2 h-2 rounded-full bg-accent" />
      Generating memo...
    </div>
  )
  return <div className="memo-content"><ReactMarkdown>{memo.content || ""}</ReactMarkdown></div>
}

// ─── Top 5 Hero Section ───────────────────────────────────────────────────────

function Top5Card({ deal, rank, onSelect }: { deal: Deal; rank: number; onSelect: (id: string) => void }) {
  const vb = deal.valuationBand
  return (
    <div
      className="glass-card p-4 hover:border-accent/40 transition-all cursor-pointer group"
      onClick={() => onSelect(deal.id)}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="font-mono text-xl font-bold text-accent/25 leading-none pt-0.5 shrink-0 w-7">
            {String(rank).padStart(2, '0')}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-display font-semibold text-slate-100 leading-tight group-hover:text-accent transition-colors truncate">
              {deal.name}
            </div>
            <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
              <MapPin size={10} className="text-slate-600 shrink-0" />
              <span className="text-xs text-slate-500 font-mono">{deal.city}, {deal.state}</span>
              {deal.domainAgeYears != null && (
                <span className="text-xs text-slate-600 font-mono">· {Math.round(deal.domainAgeYears)}yr tenure</span>
              )}
              {deal.googleRating != null && (
                <span className="flex items-center gap-1 text-xs text-slate-500">
                  <Star size={9} className="text-terminal-amber" />
                  <span className="font-mono">{deal.googleRating.toFixed(1)}</span>
                </span>
              )}
            </div>
          </div>
        </div>
        <ConvictionScoreBadge score={deal.convictionScore} />
      </div>

      <div className="space-y-1 mb-3">
        <SubScorePill label="Transition" value={deal.transitionScore || 0} max={40} color="bg-terminal-amber/60" />
        <SubScorePill label="Quality"    value={deal.qualityScore    || 0} max={35} color="bg-terminal-green/60" />
        <SubScorePill label="Platform"   value={deal.platformScore   || 0} max={25} color="bg-blue-400/60" />
      </div>

      {(deal.thesisBullets || []).length > 0 && (
        <ul className="space-y-1 mb-3">
          {(deal.thesisBullets || []).slice(0, 2).map((bullet, i) => (
            <li key={i} className="flex gap-2 text-xs text-slate-400 leading-snug">
              <span className="text-terminal-green shrink-0 mt-px">▸</span>
              <span>{bullet}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between pt-2.5 border-t border-surface-600/60">
        <div className="flex items-center gap-3">
          {vb && (
            <span className="font-mono text-xs font-semibold text-accent">
              {fmtDollar(vb.mid)} est.
            </span>
          )}
          {vb?.multipleRange && (
            <span className="text-xs text-slate-600 font-mono">{vb.multipleRange}</span>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {deal.recommendedAction && (
            <span className="text-xs text-slate-500 italic truncate max-w-[140px]">{deal.recommendedAction}</span>
          )}
          <span className="text-accent text-sm font-mono group-hover:translate-x-0.5 transition-transform inline-block">→</span>
        </div>
      </div>
    </div>
  )
}

function Top5HeroSection({ onSelect }: { onSelect: (id: string) => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ['top5'],
    queryFn: fetchTop5,
    staleTime: 60_000,
  })
  const top5 = data?.topDeals || []

  return (
    <div className="h-full overflow-y-auto bg-navy-gradient border-l border-surface-600">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-navy-900/90 backdrop-blur-sm px-6 py-4 border-b border-surface-600">
        <div className="flex items-end justify-between">
          <div>
            <div className="terminal-label text-[10px] text-accent mb-1">DECISION ENGINE · TODAY'S FOCUS</div>
            <h2 className="text-lg font-display font-semibold text-slate-100">Top Acquisition Targets</h2>
          </div>
          <p className="text-xs text-slate-600 font-mono pb-0.5">
            Conviction = Transition (40) + Quality (35) + Platform (25)
          </p>
        </div>
      </div>

      <div className="px-6 py-5 space-y-3">
        {isLoading && (
          <div className="flex items-center justify-center h-48 text-slate-600">
            <RefreshCw size={16} className="animate-spin mr-2 text-accent" />
            <span className="font-mono text-sm">Ranking targets...</span>
          </div>
        )}

        {!isLoading && top5.length === 0 && (
          <div className="flex flex-col items-center justify-center h-48 text-slate-600 text-center">
            <Target size={28} className="mb-3 opacity-30" />
            <p className="text-sm font-display">No targets ranked yet</p>
            <p className="text-xs mt-1.5 text-slate-700 font-mono">
              Run the enrichment pipeline to discover HVAC acquisition targets
            </p>
          </div>
        )}

        {top5.map((deal, i) => (
          <Top5Card key={deal.id} deal={deal} rank={i + 1} onSelect={onSelect} />
        ))}

        {top5.length > 0 && (
          <p className="text-center text-xs text-slate-700 font-mono pt-2">
            Click any target to open full tearsheet · Use screener to filter all {top5.length > 4 ? '100+' : ''} targets
          </p>
        )}
      </div>
    </div>
  )
}

export default function DealDesk() {
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<ScreenerFilters>({
    search: "", state: "", minConviction: 0, workflowStatus: "", sortBy: "conviction_score",
  })
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("company"))

  const selectedDeal = useQuery({
    queryKey: ["tearsheet", selectedId],
    queryFn: () => fetchTearsheet(selectedId!),
    enabled: !!selectedId,
    staleTime: 30_000,
  })

  const { data: feedData, isLoading, refetch } = useQuery({
    queryKey: ["dealFeed", filters],
    queryFn: () => fetchDealFeed({
      limit: 100,
      minConviction: filters.minConviction || null,
      state: filters.state || undefined,
      workflowStatus: filters.workflowStatus || undefined,
      search: filters.search || undefined,
      sortBy: filters.sortBy,
      sortOrder: "desc",
    }),
    staleTime: 30_000,
  })

  const deals = feedData?.deals || []
  const total = feedData?.total || 0
  const councilCount = deals.filter(d => d.councilAnalyzed).length

  const workflowMutation = useMutation({
    mutationFn: ({ id, status, notes }: { id: string; status: WorkflowStatus; notes?: string }) =>
      updateWorkflow(id, status, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dealFeed"] })
      queryClient.invalidateQueries({ queryKey: ["tearsheet", selectedId] })
    },
  })

  const handleFilterChange = (partial: Partial<ScreenerFilters>) => setFilters(prev => ({ ...prev, ...partial }))
  const handleSelect = (id: string) => { setSelectedId(id); setSearchParams({ company: id }) }
  const activeDeal = selectedDeal.data || deals.find(d => d.id === selectedId) || null

  return (
    <div className="flex h-full">
      <ScreenerPanel filters={filters} onChange={handleFilterChange} total={total} />
      <div className="w-72 shrink-0 flex flex-col h-full border-r border-surface-600 bg-navy-800">
        <div className="px-4 py-3 border-b border-surface-600 flex items-center justify-between shrink-0">
          <div>
            <div className="terminal-label text-[10px]">DEAL FEED</div>
            <div className="text-xs text-slate-400 font-mono mt-0.5">{`${total} ranked · ${councilCount} council-reviewed`}</div>
          </div>
          <button onClick={() => refetch()} className="btn-ghost p-1.5">
            <RefreshCw size={13} className={isLoading ? "animate-spin text-accent" : ""} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {isLoading && <div className="flex items-center justify-center h-32 text-sm text-slate-600"><RefreshCw size={16} className="animate-spin mr-2" /> Loading...</div>}
          {!isLoading && deals.length === 0 && <div className="flex flex-col items-center justify-center h-32 text-slate-600"><Target size={20} className="mb-2 opacity-30" /><p className="text-xs">No targets match filters</p></div>}
          {deals.map((deal, i) => <DealFeedItem key={deal.id} deal={deal} index={i} selected={deal.id === selectedId} onClick={() => handleSelect(deal.id)} />)}
        </div>
      </div>
      <div className="flex-1 overflow-hidden">
        {!selectedId ? (
          <Top5HeroSection onSelect={handleSelect} />
        ) : (
          <DecisionPane
            deal={activeDeal}
            onWorkflowUpdate={(id, status, notes) => workflowMutation.mutate({ id, status, notes })}
          />
        )}
      </div>
    </div>
  )
}

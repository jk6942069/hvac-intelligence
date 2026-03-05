import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Search, Download, Star, Globe, ChevronUp, ChevronDown, ArrowUpDown, MapPin
} from 'lucide-react'
import { fetchCompanies } from '../api/client'
import { WORKFLOW_LABELS } from '../types'
import type { WorkflowStatus } from '../types'

const scoreColor = (s: number) =>
  s >= 60 ? 'text-terminal-green' : s >= 40 ? 'text-terminal-amber' : 'text-terminal-red'

const scoreBg = (s: number) =>
  s >= 60 ? 'bg-terminal-green/10 text-terminal-green' :
  s >= 40 ? 'bg-terminal-amber/10 text-terminal-amber' :
  'bg-surface-600 text-slate-500'

type SortCol = 'score' | 'name' | 'google_rating' | 'google_review_count' | 'domain_age_years'

export default function Companies() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [state, setState] = useState('')
  const [sortBy, setSortBy] = useState<SortCol>('score')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [minScore, setMinScore] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['companies', page, search, state, sortBy, sortOrder, minScore],
    queryFn: () => fetchCompanies({
      page, limit: 50, sortBy, sortOrder,
      state: state || undefined,
      search: search || undefined,
      minScore,
    }),
    staleTime: 30_000,
  })

  const companies = (data?.companies || []) as any[]
  const total = data?.total || 0
  const pages = data?.pages || 1

  const handleSort = (col: SortCol) => {
    if (sortBy === col) setSortOrder(o => o === 'desc' ? 'asc' : 'desc')
    else { setSortBy(col); setSortOrder('desc') }
    setPage(1)
  }

  function SortIcon({ col }: { col: SortCol }) {
    if (sortBy !== col) return <ArrowUpDown size={11} className="text-slate-600 opacity-50" />
    return sortOrder === 'desc'
      ? <ChevronDown size={11} className="text-accent" />
      : <ChevronUp size={11} className="text-accent" />
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header toolbar */}
      <div className="px-6 py-3 border-b border-surface-600 flex items-center gap-3 shrink-0 bg-navy-800">
        <div className="mr-2">
          <span className="font-display text-base font-semibold text-slate-100">Companies</span>
          <span className="ml-2 font-mono text-xs text-slate-500">{total} targets</span>
        </div>

        <div className="relative w-56">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            placeholder="Search…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            className="w-full pl-7 pr-3 py-1.5 bg-surface-700 border border-surface-500 rounded text-xs text-slate-200 placeholder-slate-600 outline-none focus:border-accent/50 font-mono"
          />
        </div>

        <select
          value={state}
          onChange={e => { setState(e.target.value); setPage(1) }}
          className="bg-surface-700 border border-surface-500 rounded px-2 py-1.5 text-xs text-slate-300 outline-none"
        >
          <option value="">All States</option>
          {['AZ','TX','FL','TN','NC','GA','CA','CO','NV','SC','VA'].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={minScore ?? ''}
          onChange={e => { setMinScore(e.target.value ? Number(e.target.value) : null); setPage(1) }}
          className="bg-surface-700 border border-surface-500 rounded px-2 py-1.5 text-xs text-slate-300 outline-none"
        >
          <option value="">All Scores</option>
          <option value="60">Score ≥ 60</option>
          <option value="40">Score ≥ 40</option>
          <option value="20">Score ≥ 20</option>
        </select>

        <div className="flex-1" />
        <button
          onClick={() => window.open('/api/companies/export/csv', '_blank')}
          className="btn-secondary flex items-center gap-1.5 text-xs py-1.5 px-3"
        >
          <Download size={12} /> Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 z-10 bg-navy-800 border-b border-surface-600">
            <tr>
              <th className="px-4 py-2.5 text-left terminal-label text-[10px] w-10">#</th>
              <th
                className="px-4 py-2.5 text-left terminal-label text-[10px] cursor-pointer hover:text-slate-300 min-w-[200px]"
                onClick={() => handleSort('name')}
              >
                <span className="flex items-center gap-1.5">COMPANY <SortIcon col="name" /></span>
              </th>
              <th className="px-4 py-2.5 text-left terminal-label text-[10px]">LOCATION</th>
              <th
                className="px-4 py-2.5 text-left terminal-label text-[10px] cursor-pointer hover:text-slate-300"
                onClick={() => handleSort('score')}
              >
                <span className="flex items-center gap-1.5">CONVICTION <SortIcon col="score" /></span>
              </th>
              <th
                className="px-4 py-2.5 text-left terminal-label text-[10px] cursor-pointer hover:text-slate-300"
                onClick={() => handleSort('google_rating')}
              >
                <span className="flex items-center gap-1.5">RATING <SortIcon col="google_rating" /></span>
              </th>
              <th
                className="px-4 py-2.5 text-left terminal-label text-[10px] cursor-pointer hover:text-slate-300"
                onClick={() => handleSort('google_review_count')}
              >
                <span className="flex items-center gap-1.5">REVIEWS <SortIcon col="google_review_count" /></span>
              </th>
              <th
                className="px-4 py-2.5 text-left terminal-label text-[10px] cursor-pointer hover:text-slate-300"
                onClick={() => handleSort('domain_age_years')}
              >
                <span className="flex items-center gap-1.5">AGE <SortIcon col="domain_age_years" /></span>
              </th>
              <th className="px-4 py-2.5 text-left terminal-label text-[10px]">WORKFLOW</th>
              <th className="px-4 py-2.5 text-left terminal-label text-[10px]">TOP SIGNALS</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={9} className="text-center py-12 text-sm text-slate-600">Loading…</td>
              </tr>
            )}
            {!isLoading && companies.length === 0 && (
              <tr>
                <td colSpan={9} className="text-center py-12 text-sm text-slate-600">
                  No companies match filters
                </td>
              </tr>
            )}
            {companies.map((c: any, i: number) => {
              const score = c.convictionScore ?? c.score ?? 0
              const wfStatus = (c.workflowStatus || 'not_contacted') as WorkflowStatus
              const topSig = (c.signals || []).find((s: any) => s.severity === 'high')
              return (
                <tr
                  key={c.id}
                  onClick={() => navigate(`/?company=${c.id}`)}
                  className="border-b border-surface-700 hover:bg-surface-800 cursor-pointer transition-colors group"
                >
                  <td className="px-4 py-2.5 font-mono text-[10px] text-slate-600">
                    {((page - 1) * 50 + i + 1).toString().padStart(2, '0')}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="text-sm font-medium text-slate-200 group-hover:text-accent transition-colors truncate max-w-[220px]">
                      {c.name}
                    </div>
                    {c.website && (
                      <div className="flex items-center gap-1 text-slate-600 text-[10px] mt-0.5 font-mono">
                        <Globe size={9} />
                        <span className="truncate max-w-[180px]">{c.domain || c.website}</span>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1 text-xs text-slate-400 font-mono">
                      <MapPin size={10} className="text-slate-600 shrink-0" />
                      {c.city}, {c.state}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded font-mono font-bold text-sm ${scoreBg(score)}`}>
                      {score}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    {c.googleRating != null ? (
                      <span className="flex items-center gap-1 font-mono text-xs text-slate-300">
                        <Star size={10} className="text-terminal-amber" />
                        {c.googleRating.toFixed(1)}
                      </span>
                    ) : <span className="text-slate-600 text-xs">—</span>}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-400">
                    {c.googleReviewCount ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-400">
                    {c.domainAgeYears != null ? `${Math.round(c.domainAgeYears)}y` : '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`badge workflow-${wfStatus} text-[10px]`}>
                      {WORKFLOW_LABELS[wfStatus] || wfStatus}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1 max-w-[200px]">
                      {topSig && (
                        <span className={`badge text-[9px] ${
                          topSig.severity === 'high' ? 'badge-high' :
                          topSig.severity === 'medium' ? 'badge-medium' : 'badge-neutral'
                        }`} title={topSig.description}>
                          {topSig.label.split(' ').slice(0, 2).join(' ')}
                        </span>
                      )}
                      {(c.signals || []).length > 1 && (
                        <span className="badge badge-neutral text-[9px]">+{c.signals.length - 1}</span>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="px-6 py-3 border-t border-surface-600 flex items-center justify-between shrink-0 bg-navy-800">
          <span className="terminal-label text-[10px]">
            Page {page} of {pages} · {total} results
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary text-xs py-1.5 px-3 disabled:opacity-40"
            >
              ← Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(pages, p + 1))}
              disabled={page >= pages}
              className="btn-secondary text-xs py-1.5 px-3 disabled:opacity-40"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

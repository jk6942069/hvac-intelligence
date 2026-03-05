import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  Building2, TrendingUp, FileText, BarChart3, Star, Target,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import { fetchDashboardStats } from '../api/client'
import StatCard from '../components/StatCard'
import ScoreBar from '../components/ScoreBar'
import SignalBadge from '../components/SignalBadge'
import type { Company } from '../types'

const SCORE_COLORS = ['#475569', '#64748b', '#f59e0b', '#10b981', '#3b82f6']

function EmptyState() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col items-center justify-center h-64 text-center">
      <div className="w-14 h-14 rounded-full bg-surface-800 flex items-center justify-center mb-4">
        <Building2 className="w-7 h-7 text-slate-500" />
      </div>
      <p className="text-slate-400 text-sm mb-1">No data yet</p>
      <p className="text-slate-600 text-xs mb-4">Run the pipeline to discover HVAC acquisition targets</p>
      <button onClick={() => navigate('/pipeline')} className="btn-primary">
        Run Pipeline
      </button>
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboardStats,
    refetchInterval: 30_000,
  })

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="h-8 w-48 bg-surface-800 rounded animate-pulse mb-6" />
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="card p-5 h-24 animate-pulse bg-surface-800" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !stats) {
    return (
      <div className="p-8">
        <div className="card p-6 text-center text-slate-400 text-sm">
          Could not connect to backend. Make sure the API server is running on port 8000.
        </div>
      </div>
    )
  }

  const hasData = stats.totalCompanies > 0

  return (
    <div className="p-8 space-y-7">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-slate-100 text-xl font-semibold">Intelligence Dashboard</h1>
          <p className="text-slate-500 text-sm mt-0.5">HVAC acquisition target overview</p>
        </div>
        <button onClick={() => navigate('/pipeline')} className="btn-primary flex items-center gap-2">
          <TrendingUp className="w-4 h-4" />
          Run Pipeline
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 xl:grid-cols-3 gap-4">
        <StatCard label="Total Companies" value={stats.totalCompanies.toLocaleString()} icon={Building2} accent="blue" />
        <StatCard label="Top Candidates" value={stats.topCandidates} icon={Target} accent="green"
          sub="Score ≥ 65 or top 10%" />
        <StatCard label="High Score (≥65)" value={stats.highScoreCompanies} icon={TrendingUp} accent="amber" />
        <StatCard label="Dossiers Generated" value={stats.dossiersGenerated} icon={FileText} accent="purple" />
        <StatCard label="Avg Transition Score" value={`${stats.avgScore}/100`} icon={BarChart3} accent="blue" />
        <StatCard label="Pipeline Runs" value={stats.pipelineRuns} icon={Star} accent="green" />
      </div>

      {/* Charts + Top Targets */}
      {hasData ? (
        <div className="grid grid-cols-5 gap-5">
          {/* Score Distribution */}
          <div className="card p-5 col-span-2">
            <h2 className="text-slate-300 text-sm font-medium mb-4">Score Distribution</h2>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={stats.scoreDistribution} barCategoryGap="25%">
                <XAxis dataKey="range" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6, fontSize: 12 }}
                  labelStyle={{ color: '#94a3b8' }}
                  itemStyle={{ color: '#f1f5f9' }}
                />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {stats.scoreDistribution.map((_, i) => (
                    <Cell key={i} fill={SCORE_COLORS[i] ?? '#3b82f6'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Top States */}
          <div className="card p-5 col-span-1">
            <h2 className="text-slate-300 text-sm font-medium mb-4">Top Markets</h2>
            <div className="space-y-2">
              {stats.topStates.slice(0, 7).map(({ state, count }) => (
                <div key={state} className="flex items-center justify-between">
                  <span className="text-slate-400 text-xs font-mono">{state}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-surface-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full"
                        style={{ width: `${(count / (stats.topStates[0]?.count || 1)) * 100}%` }}
                      />
                    </div>
                    <span className="text-slate-500 text-xs w-6 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Top Targets */}
          <div className="card p-5 col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-slate-300 text-sm font-medium">Top Acquisition Targets</h2>
              <button
                onClick={() => navigate('/companies?status=top_candidate')}
                className="text-accent text-xs hover:text-accent-light transition-colors"
              >
                View all →
              </button>
            </div>
            <div className="space-y-2.5">
              {stats.recentTargets.map((c: Company) => (
                <div
                  key={c.id}
                  onClick={() => navigate(`/companies/${c.id}`)}
                  className="flex items-center gap-3 p-2.5 rounded-md hover:bg-surface-800 cursor-pointer transition-colors"
                >
                  <div className="w-6 h-6 rounded bg-accent/10 flex items-center justify-center flex-shrink-0">
                    <span className="text-accent text-xs font-bold">{c.rank ?? '—'}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-slate-200 text-xs font-medium truncate">{c.name}</div>
                    <div className="text-slate-500 text-xs">{c.city}, {c.state}</div>
                  </div>
                  <ScoreBar score={c.score} size="sm" className="w-24" />
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="card">
          <EmptyState />
        </div>
      )}
    </div>
  )
}

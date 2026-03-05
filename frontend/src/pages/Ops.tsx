import { useState, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Play, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react'
import { fetchPipelineStatus, fetchPipelineHistory, startPipeline, fetchDashboardStats, createPipelineSocket } from '../api/client'

export default function Ops() {
  const [wsMessages, setWsMessages] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [pipelineConfig, setPipelineConfig] = useState({
    states: ['AZ', 'TN'],
    maxCompanies: 100,
    generateDossiersForTop: 10,
  })

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['pipeline-status'],
    queryFn: fetchPipelineStatus,
    refetchInterval: running ? 2000 : 10000,
  })

  const { data: history } = useQuery({
    queryKey: ['pipeline-history'],
    queryFn: fetchPipelineHistory,
    staleTime: 30_000,
  })

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: fetchDashboardStats,
    staleTime: 30_000,
  })

  const runMutation = useMutation({
    mutationFn: () => startPipeline({
      states: pipelineConfig.states,
      maxCompanies: pipelineConfig.maxCompanies,
      generateDossiersForTop: pipelineConfig.generateDossiersForTop,
    }),
    onMutate: () => setRunning(true),
    onSettled: () => refetchStatus(),
  })

  useEffect(() => {
    if (!running) return
    let ws: WebSocket | null = null
    createPipelineSocket((data) => {
      const msg = (data as any).message || JSON.stringify(data)
      setWsMessages(prev => [...prev.slice(-49), msg])
      if ((data as any).status === 'completed' || (data as any).status === 'failed') {
        setRunning(false)
      }
    }).then(socket => {
      ws = socket
    })
    return () => {
      ws?.close()
    }
  }, [running])

  const isRunning = status?.isRunning || running
  return (
    <div className="h-full overflow-y-auto p-6 space-y-6">
      <div>
        <h1 className="text-xl font-display font-semibold text-slate-100">Ops / Pipeline</h1>
        <p className="text-sm text-slate-500 mt-1 font-mono">Discovery pipeline controls and system metrics</p>
      </div>

      <div className="grid grid-cols-6 gap-3">
        {[
          { label: 'TOTAL COMPANIES', value: stats?.totalCompanies || 0 },
          { label: 'HIGH CONVICTION (>=60)', value: stats?.highScoreCompanies || 0 },
          { label: 'TOP CANDIDATES', value: stats?.topCandidates || 0 },
          { label: 'DOSSIERS', value: stats?.dossiersGenerated || 0 },
          { label: 'AVG SCORE', value: `${stats?.avgScore || 0}/100` },
          { label: 'PIPELINE RUNS', value: stats?.pipelineRuns || 0 },
        ].map(({ label, value }) => (
          <div key={label} className="stat-card">
            <div className="terminal-label text-[10px]">{label}</div>
            <div className="font-display text-xl font-bold text-slate-100">{value}</div>
          </div>
        ))}
      </div>

      <div className="glass-card p-5">
        <div className="terminal-label text-[10px] mb-4">DISCOVERY PIPELINE</div>
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="terminal-label text-[10px] mb-1.5 block">TARGET STATES</label>
            <input
              type="text"
              value={pipelineConfig.states.join(', ')}
              onChange={e => setPipelineConfig(p => ({
                ...p,
                states: e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean)
              }))}
              className="w-full bg-surface-700 border border-surface-500 rounded px-3 py-2 text-xs text-slate-300 font-mono outline-none"
              placeholder="AZ, TN, TX"
            />
          </div>
          <div>
            <label className="terminal-label text-[10px] mb-1.5 block">MAX COMPANIES</label>
            <input type="number" value={pipelineConfig.maxCompanies} onChange={e => setPipelineConfig(p => ({ ...p, maxCompanies: Number(e.target.value) }))} className="w-full bg-surface-700 border border-surface-500 rounded px-3 py-2 text-xs text-slate-300 font-mono outline-none" />
          </div>
          <div>
            <label className="terminal-label text-[10px] mb-1.5 block">GEN DOSSIERS (TOP N)</label>
            <input type="number" value={pipelineConfig.generateDossiersForTop} onChange={e => setPipelineConfig(p => ({ ...p, generateDossiersForTop: Number(e.target.value) }))} className="w-full bg-surface-700 border border-surface-500 rounded px-3 py-2 text-xs text-slate-300 font-mono outline-none" />
          </div>
        </div>

        <button onClick={() => runMutation.mutate()} disabled={isRunning} className="btn-primary flex items-center gap-2">
          {isRunning ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
          {isRunning ? 'Pipeline Running...' : 'Run Pipeline'}
        </button>

        {isRunning && status?.lastRun && (
          <div className="mt-3 flex items-center gap-3 text-xs text-slate-400">
            <span className="pulse-dot inline-block w-2 h-2 rounded-full bg-accent" />
            Stage: <span className="font-mono text-accent">{status.lastRun.stage}</span>
            <span className="font-mono">{status.lastRun.processed}/{status.lastRun.total}</span>
          </div>
        )}
      </div>
      {wsMessages.length > 0 && (
        <div className="glass-card p-4">
          <div className="terminal-label text-[10px] mb-3">PIPELINE LOG</div>
          <div className="font-mono text-xs space-y-0.5 text-slate-500 max-h-48 overflow-y-auto">
            {wsMessages.map((msg, i) => (<div key={i} className="text-slate-400">&gt; {msg}</div>))}
          </div>
        </div>
      )}

      <div className="glass-card p-4">
        <div className="terminal-label text-[10px] mb-3">RUN HISTORY</div>
        {(!history || history.length === 0) && <p className="text-sm text-slate-600">No runs yet.</p>}
        <div className="space-y-2">
          {(history || []).slice(0, 10).map(run => (
            <div key={run.id} className="flex items-center gap-3 text-xs py-2 border-b border-surface-700">
              {run.status === 'completed' ? <CheckCircle size={12} className="text-terminal-green" /> :
               run.status === 'failed' ? <XCircle size={12} className="text-terminal-red" /> :
               <Clock size={12} className="text-terminal-amber pulse-dot" />}
              <span className="font-mono text-slate-400">{run.startedAt ? new Date(run.startedAt).toLocaleString() : 'Unknown'}</span>
              <span className={`badge ${run.status === 'completed' ? 'badge-high' : run.status === 'failed' ? 'badge-low' : 'badge-medium'}`}>{run.status}</span>
              <span className="text-slate-500 ml-auto">{run.processed}/{run.total} companies</span>
              {run.error && <span className="text-terminal-red truncate max-w-xs">{run.error}</span>}
            </div>
          ))}
        </div>
      </div>

      {stats?.scoreDistribution && (
        <div className="glass-card p-4">
          <div className="terminal-label text-[10px] mb-3">SCORE DISTRIBUTION</div>
          <div className="space-y-2">
            {stats.scoreDistribution.map(({ range, count }) => (
              <div key={range} className="flex items-center gap-3">
                <span className="font-mono text-xs text-slate-500 w-14">{range}</span>
                <div className="flex-1 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                  <div className="h-full score-bar-fill rounded-full" style={{ width: `${Math.min((count / (stats.totalCompanies || 1)) * 100 * 3, 100)}%` }} />
                </div>
                <span className="font-mono text-xs text-slate-400 w-8 text-right">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
import { useState, useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Square, CheckCircle, XCircle, Clock, ChevronRight, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import {
  fetchPipelineStatus, fetchPipelineHistory, startPipeline, createPipelineSocket,
} from '../api/client'
import type { PipelineRun } from '../types'

const STAGES = [
  { key: 'scout',    label: 'Scout',    desc: 'Discovering HVAC companies via Google Places' },
  { key: 'enrich',   label: 'Enrich',   desc: 'Enriching with domain, SSL & web data' },
  { key: 'signals',  label: 'Signals',  desc: 'Detecting ownership transition signals' },
  { key: 'scoring',  label: 'Score',    desc: 'Calculating acquisition probability scores' },
  { key: 'ranking',  label: 'Rank',     desc: 'Ranking and classifying candidates' },
  { key: 'dossiers', label: 'Dossiers', desc: 'Generating investor intelligence reports' },
]

interface LiveMessage {
  type: string
  stage?: string
  message?: string
  progress?: number
}

function StageStep({ stage, currentStage, done }: { stage: typeof STAGES[0]; currentStage: string; done: boolean }) {
  const isActive = currentStage === stage.key
  const isComplete = done && !isActive
  return (
    <div className={clsx('flex items-start gap-3 py-2', !isActive && !isComplete && 'opacity-40')}>
      <div className="flex-shrink-0 mt-0.5">
        {isComplete ? (
          <CheckCircle className="w-4 h-4 text-emerald-400" />
        ) : isActive ? (
          <Loader2 className="w-4 h-4 text-accent animate-spin" />
        ) : (
          <div className="w-4 h-4 rounded-full border border-surface-600" />
        )}
      </div>
      <div>
        <div className={clsx('text-sm font-medium', isActive ? 'text-slate-100' : 'text-slate-400')}>
          {stage.label}
        </div>
        <div className="text-slate-500 text-xs">{stage.desc}</div>
      </div>
    </div>
  )
}

function RunRow({ run }: { run: PipelineRun }) {
  const duration = run.completedAt && run.startedAt
    ? Math.round((new Date(run.completedAt).getTime() - new Date(run.startedAt).getTime()) / 1000)
    : null

  return (
    <div className="flex items-center gap-4 py-3 border-b border-surface-800 last:border-0">
      <div className="flex-shrink-0">
        {run.status === 'completed' ? (
          <CheckCircle className="w-4 h-4 text-emerald-400" />
        ) : run.status === 'failed' ? (
          <XCircle className="w-4 h-4 text-red-400" />
        ) : (
          <Loader2 className="w-4 h-4 text-accent animate-spin" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-slate-300 text-sm font-mono truncate">{run.id.slice(0, 16)}…</div>
        <div className="text-slate-500 text-xs">
          {run.startedAt ? new Date(run.startedAt).toLocaleString() : '—'}
          {duration ? ` · ${duration}s` : ''}
        </div>
      </div>
      <div className="text-slate-400 text-sm tabular-nums">{run.total ?? 0} companies</div>
      <div className={clsx('text-xs font-medium px-2 py-0.5 rounded',
        run.status === 'completed' ? 'bg-emerald-500/15 text-emerald-400'
          : run.status === 'failed' ? 'bg-red-500/15 text-red-400'
          : 'bg-blue-500/15 text-blue-400'
      )}>
        {run.status}
      </div>
    </div>
  )
}

export default function Pipeline() {
  const qc = useQueryClient()
  const wsRef = useRef<WebSocket | null>(null)
  const [liveMsg, setLiveMsg] = useState<LiveMessage | null>(null)
  const [liveProgress, setLiveProgress] = useState(0)
  const [isStarting, setIsStarting] = useState(false)
  const [maxCompanies, setMaxCompanies] = useState(200)

  const { data: status, refetch: refetchStatus } = useQuery({
    queryKey: ['pipeline-status'],
    queryFn: fetchPipelineStatus,
    refetchInterval: 3000,
  })

  const { data: history } = useQuery({
    queryKey: ['pipeline-history'],
    queryFn: fetchPipelineHistory,
    refetchInterval: 10_000,
  })

  // WebSocket
  useEffect(() => {
    const connect = () => {
      const ws = createPipelineSocket(
        (data) => {
          const msg = data as unknown as LiveMessage
          if (msg.type === 'progress') {
            setLiveMsg(msg)
            setLiveProgress(msg.progress ?? 0)
          }
          if (msg.type === 'complete' || msg.type === 'error') {
            setTimeout(() => {
              refetchStatus()
              qc.invalidateQueries({ queryKey: ['dashboard'] })
              qc.invalidateQueries({ queryKey: ['pipeline-history'] })
            }, 800)
          }
        },
        () => setTimeout(connect, 3000)
      )
      wsRef.current = ws
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const handleStart = async () => {
    setIsStarting(true)
    setLiveProgress(0)
    setLiveMsg(null)
    try {
      await startPipeline({ maxCompanies, generateDossiersForTop: 20 })
      await refetchStatus()
    } catch (e) {
      console.error(e)
    } finally {
      setIsStarting(false)
    }
  }

  const isRunning = status?.isRunning ?? false
  const currentStage = liveMsg?.stage ?? status?.lastRun?.stage ?? ''
  const stageIdx = STAGES.findIndex(s => s.key === currentStage)

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-slate-100 text-xl font-semibold">Pipeline</h1>
        <p className="text-slate-500 text-sm mt-0.5">Run the 7-agent HVAC deal sourcing pipeline</p>
      </div>

      <div className="grid grid-cols-3 gap-5">
        {/* Control Panel */}
        <div className="col-span-1 space-y-4">
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-4">Run Configuration</h2>
            <div className="space-y-4">
              <div>
                <label className="text-slate-400 text-xs block mb-1.5">Max companies to process</label>
                <select
                  value={maxCompanies}
                  onChange={e => setMaxCompanies(Number(e.target.value))}
                  disabled={isRunning}
                  className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent"
                >
                  <option value={50}>50 — Quick test</option>
                  <option value={100}>100 — Small batch</option>
                  <option value={200}>200 — Standard</option>
                  <option value={500}>500 — Large batch</option>
                  <option value={1000}>1,000 — Full run</option>
                </select>
              </div>
              <div className="text-slate-500 text-xs bg-surface-800 rounded-md p-3 leading-relaxed">
                Searches {Math.round(maxCompanies / 8)} US cities · Top 10% get AI dossiers · ~{Math.round(maxCompanies * 0.3 / 60)} min estimated
              </div>
              {!isRunning ? (
                <button
                  onClick={handleStart}
                  disabled={isStarting}
                  className="btn-primary w-full flex items-center justify-center gap-2"
                >
                  {isStarting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  {isStarting ? 'Starting…' : 'Run Pipeline'}
                </button>
              ) : (
                <button disabled className="btn-secondary w-full flex items-center justify-center gap-2 opacity-60">
                  <Square className="w-4 h-4" />
                  Pipeline Running…
                </button>
              )}
            </div>
          </div>

          {/* Agent Pipeline Overview */}
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-3">Agent Pipeline</h2>
            <div className="space-y-0.5">
              {STAGES.map((stage, i) => (
                <StageStep
                  key={stage.key}
                  stage={stage}
                  currentStage={isRunning ? currentStage : ''}
                  done={isRunning && stageIdx > i}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Live Progress */}
        <div className="col-span-2 space-y-4">
          {/* Progress Card */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-slate-300 text-sm font-medium">Live Progress</h2>
              {isRunning && (
                <span className="flex items-center gap-1.5 text-xs text-accent">
                  <span className="w-2 h-2 rounded-full bg-accent pulse-dot" />
                  Running
                </span>
              )}
            </div>

            <div className="mb-3">
              <div className="flex justify-between text-xs text-slate-500 mb-1.5">
                <span>{liveMsg?.message ?? (isRunning ? 'Processing…' : 'Ready')}</span>
                <span>{Math.round(liveProgress * 100)}%</span>
              </div>
              <div className="h-2 bg-surface-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-accent rounded-full transition-all duration-500"
                  style={{ width: `${liveProgress * 100}%` }}
                />
              </div>
            </div>

            {liveMsg?.stage && (
              <div className="flex items-center gap-2 text-xs text-slate-500 mt-2">
                <ChevronRight className="w-3 h-3" />
                Stage: <span className="text-slate-300 font-medium capitalize">{liveMsg.stage}</span>
              </div>
            )}

            {!isRunning && !liveMsg && (
              <div className="flex items-center gap-2 text-slate-600 text-xs mt-2">
                <Clock className="w-3.5 h-3.5" />
                Click "Run Pipeline" to begin deal sourcing
              </div>
            )}
          </div>

          {/* Run History */}
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-3">Run History</h2>
            {history && history.length > 0 ? (
              <div>
                {history.map(run => <RunRow key={run.id} run={run} />)}
              </div>
            ) : (
              <div className="text-slate-600 text-sm text-center py-6">
                No pipeline runs yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Square, CheckCircle, XCircle, Loader2, MapPin } from 'lucide-react'
import clsx from 'clsx'
import {
  fetchPipelineStatus, fetchPipelineHistory, startPipeline, createPipelineSocket,
} from '../api/client'
import type { PipelineRun } from '../types'

const PIPELINE_STEPS = [
  { id: 'scout', label: 'Discovering HVAC Companies', stages: ['scout'] },
  { id: 'analyze', label: 'Analyzing Business Signals', stages: ['enrich', 'content_enrich', 'signals'] },
  { id: 'score', label: 'Ranking Acquisition Targets', stages: ['scoring', 'ranking', 'council', 'dossiers'] },
  { id: 'complete', label: 'Pipeline Complete', stages: ['complete'] },
]

interface LiveMessage {
  type: string
  stage?: string
  message?: string
  progress?: number
  total?: number
}

function getStepStatus(stepIndex: number, currentStage: string, isRunning: boolean): 'complete' | 'active' | 'pending' {
  if (!currentStage || !isRunning) return 'pending'

  // Find which step contains the current stage
  const activeStepIndex = PIPELINE_STEPS.findIndex(s => s.stages.includes(currentStage))

  if (activeStepIndex === -1) {
    // If 'complete' type message came in, all steps are done
    if (currentStage === 'complete') return 'complete'
    return 'pending'
  }

  if (stepIndex < activeStepIndex) return 'complete'
  if (stepIndex === activeStepIndex) return 'active'
  return 'pending'
}

function PipelineStepRow({ step, status }: { step: typeof PIPELINE_STEPS[0]; status: 'complete' | 'active' | 'pending' }) {
  return (
    <div className={clsx('flex items-center gap-3 py-3', status === 'pending' && 'opacity-40')}>
      <div className="flex-shrink-0 w-5 text-center">
        {status === 'complete' ? (
          <span className="text-emerald-400 text-base leading-none">✓</span>
        ) : status === 'active' ? (
          <span className="text-accent text-base leading-none animate-pulse">●</span>
        ) : (
          <span className="text-slate-600 text-base leading-none">○</span>
        )}
      </div>
      <div className={clsx(
        'text-sm',
        status === 'active' ? 'text-slate-100 font-medium' : status === 'complete' ? 'text-emerald-400' : 'text-slate-500'
      )}>
        {step.label}
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
        <div className="text-slate-300 text-sm">
          {run.startedAt ? new Date(run.startedAt).toLocaleString() : '—'}
          {duration ? ` · ${duration}s` : ''}
        </div>
        {run.total != null && run.total > 0 && (
          <div className="text-slate-500 text-xs mt-0.5">{run.total} companies found</div>
        )}
      </div>
      <div className={clsx('text-xs font-medium px-2 py-0.5 rounded',
        run.status === 'completed' ? 'bg-emerald-500/15 text-emerald-400'
          : run.status === 'failed' ? 'bg-red-500/15 text-red-400'
          : 'bg-blue-500/15 text-blue-400'
      )}>
        {run.status === 'completed' ? 'Done' : run.status === 'failed' ? 'Failed' : 'Running'}
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
  const [location, setLocation] = useState('')
  const [maxCompanies, setMaxCompanies] = useState(50)
  const [completionTotal, setCompletionTotal] = useState<number | null>(null)

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
      createPipelineSocket(
        (data) => {
          const msg = data as unknown as LiveMessage
          if (msg.type === 'progress') {
            setLiveMsg(msg)
            setLiveProgress(msg.progress ?? 0)
          }
          if (msg.type === 'complete') {
            if (msg.total != null) setCompletionTotal(msg.total)
            setLiveMsg({ type: 'complete', stage: 'complete' })
            setTimeout(() => {
              refetchStatus()
              qc.invalidateQueries({ queryKey: ['dashboard'] })
              qc.invalidateQueries({ queryKey: ['pipeline-history'] })
            }, 800)
          }
          if (msg.type === 'error') {
            setTimeout(() => {
              refetchStatus()
              qc.invalidateQueries({ queryKey: ['pipeline-history'] })
            }, 800)
          }
        },
        () => setTimeout(connect, 3000)
      ).then(socket => {
        wsRef.current = socket
      })
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const handleStart = async () => {
    setIsStarting(true)
    setLiveProgress(0)
    setLiveMsg(null)
    setCompletionTotal(null)
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
  const isPipelineComplete = currentStage === 'complete' || (!isRunning && status?.lastRun?.status === 'completed')
  const lastRunTotal = completionTotal ?? status?.lastRun?.total ?? null

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <div>
        <h1 className="text-slate-100 text-xl font-semibold">Pipeline</h1>
        <p className="text-slate-500 text-sm mt-0.5">Discover and rank HVAC acquisition targets</p>
      </div>

      <div className="grid grid-cols-5 gap-5">
        {/* Control Panel */}
        <div className="col-span-2 space-y-4">
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-4">Run Pipeline</h2>
            <div className="space-y-4">
              {/* Location input */}
              <div>
                <label className="text-slate-400 text-xs block mb-1.5 flex items-center gap-1.5">
                  <MapPin className="w-3 h-3" />
                  City, State (optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Phoenix, AZ"
                  value={location}
                  onChange={e => setLocation(e.target.value)}
                  disabled={isRunning}
                  className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent placeholder-slate-600 disabled:opacity-50"
                />
                <p className="text-slate-600 text-xs mt-1">Leave blank to search across all markets</p>
              </div>

              {/* Max companies slider */}
              <div>
                <div className="flex justify-between mb-1.5">
                  <label className="text-slate-400 text-xs">Max Companies</label>
                  <span className="text-accent font-mono text-xs font-semibold">{maxCompanies}</span>
                </div>
                <input
                  type="range"
                  min={10}
                  max={100}
                  step={5}
                  value={maxCompanies}
                  onChange={e => setMaxCompanies(Number(e.target.value))}
                  disabled={isRunning}
                  className="w-full accent-accent disabled:opacity-50"
                />
                <div className="flex justify-between text-[10px] text-slate-600 font-mono mt-1">
                  <span>10</span>
                  <span>50</span>
                  <span>100</span>
                </div>
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

          {/* Run History */}
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-3">Recent Runs</h2>
            {history && history.length > 0 ? (
              <div>
                {history.slice(0, 5).map(run => <RunRow key={run.id} run={run} />)}
              </div>
            ) : (
              <div className="text-slate-600 text-sm text-center py-4">
                No pipeline runs yet
              </div>
            )}
          </div>
        </div>

        {/* Progress Steps */}
        <div className="col-span-3">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-slate-300 text-sm font-medium">Progress</h2>
              {isRunning && (
                <span className="flex items-center gap-1.5 text-xs text-accent">
                  <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                  Running
                </span>
              )}
            </div>

            {/* Step list */}
            <div className="space-y-0 divide-y divide-surface-800">
              {PIPELINE_STEPS.map((step, i) => {
                const stepStatus = isRunning
                  ? getStepStatus(i, currentStage, isRunning)
                  : isPipelineComplete && !isRunning
                    ? 'complete'
                    : 'pending'
                return (
                  <PipelineStepRow key={step.id} step={step} status={stepStatus} />
                )
              })}
            </div>

            {/* Progress bar */}
            {isRunning && (
              <div className="mt-5 pt-4 border-t border-surface-800">
                <div className="flex justify-between text-xs text-slate-500 mb-1.5">
                  <span>{liveMsg?.message ?? 'Processing…'}</span>
                  <span className="font-mono">{Math.round(liveProgress * 100)}%</span>
                </div>
                <div className="h-1.5 bg-surface-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent rounded-full transition-all duration-500"
                    style={{ width: `${liveProgress * 100}%` }}
                  />
                </div>
              </div>
            )}

            {/* Completion message */}
            {isPipelineComplete && !isRunning && lastRunTotal != null && (
              <div className="mt-5 pt-4 border-t border-surface-800">
                <div className="flex items-center gap-2 text-sm text-emerald-400">
                  <CheckCircle className="w-4 h-4" />
                  Pipeline complete — {lastRunTotal} companies added to Deal Desk.
                </div>
              </div>
            )}

            {/* Idle state */}
            {!isRunning && !isPipelineComplete && (
              <div className="mt-5 pt-4 border-t border-surface-800">
                <p className="text-slate-600 text-xs text-center">
                  Configure your run and click "Run Pipeline" to begin
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

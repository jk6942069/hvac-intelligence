import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft, Globe, Phone, MapPin, Star, Shield, ShieldOff,
  Facebook, Instagram, FileText, CheckCircle, Clock, Loader2,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import clsx from 'clsx'
import { fetchCompany, submitFeedback, generateDossier } from '../api/client'
import ScoreBar from '../components/ScoreBar'
import SignalBadge from '../components/SignalBadge'
import MemoExport from '../components/MemoExport'

const FEEDBACK_OPTIONS = [
  { value: 'responded', label: 'Owner Responded', cls: 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10' },
  { value: 'uninterested', label: 'Not Interested', cls: 'border-slate-600 text-slate-400' },
  { value: 'already_selling', label: 'Already Selling', cls: 'border-amber-500/40 text-amber-400 bg-amber-500/10' },
]

function ScoreBreakdownBar({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-400">{label}</span>
        <span className="text-slate-300 tabular-nums">{value}/{max}</span>
      </div>
      <div className="h-1.5 bg-surface-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-accent rounded-full"
          style={{ width: `${(value / max) * 100}%` }}
        />
      </div>
    </div>
  )
}

export default function CompanyDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [feedbackNote, setFeedbackNote] = useState('')
  const [selectedOutcome, setSelectedOutcome] = useState('')

  const { data: company, isLoading } = useQuery({
    queryKey: ['company', id],
    queryFn: () => fetchCompany(id!),
    enabled: !!id,
  })

  const feedbackMut = useMutation({
    mutationFn: ({ outcome, notes }: { outcome: string; notes: string }) =>
      submitFeedback(id!, outcome, notes),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['company', id] })
    },
  })

  const dossierMut = useMutation({
    mutationFn: () => generateDossier(id!),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ['company', id] }), 3000)
    },
  })

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="h-6 w-32 bg-surface-800 rounded animate-pulse mb-6" />
        <div className="card p-6 h-64 animate-pulse bg-surface-800" />
      </div>
    )
  }

  if (!company) return (
    <div className="p-8 text-slate-400">Company not found.</div>
  )

  const sb = company.scoreBreakdown
  const hasDossier = !!company.dossier

  return (
    <div className="p-8 space-y-5">
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 text-sm transition-colors"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Companies
      </button>

      {/* Header Card */}
      <div className="card p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-1">
              {company.rank && (
                <span className="text-xs font-mono text-slate-500">#{company.rank}</span>
              )}
              <h1 className="text-slate-100 text-xl font-semibold">{company.name}</h1>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-sm text-slate-400 mb-4">
              {company.address && (
                <div className="flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5" />
                  {company.address}
                </div>
              )}
              {company.phone && (
                <div className="flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5" />
                  {company.phone}
                </div>
              )}
              {company.website && (
                <a
                  href={company.website}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-accent hover:text-accent-light transition-colors"
                  onClick={e => e.stopPropagation()}
                >
                  <Globe className="w-3.5 h-3.5" />
                  {company.domain || company.website}
                </a>
              )}
            </div>
            {/* Signals */}
            <div className="flex flex-wrap gap-2">
              {company.signals.map(s => (
                <SignalBadge key={s.type} signal={s} size="md" />
              ))}
            </div>
          </div>

          {/* Score */}
          <div className="flex-shrink-0 text-center">
            <div className="text-4xl font-bold tabular-nums" style={{
              color: company.score >= 75 ? '#60a5fa' : company.score >= 60 ? '#34d399' : company.score >= 40 ? '#fbbf24' : '#f87171'
            }}>
              {company.score}
            </div>
            <div className="text-slate-500 text-xs mt-0.5">/ 100</div>
            <div className="text-slate-400 text-xs mt-1 capitalize">
              {company.status?.replace(/_/g, ' ')}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-5">
        {/* Left column */}
        <div className="space-y-4">
          {/* Score Breakdown */}
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-4">Score Breakdown</h2>
            <div className="space-y-3">
              <ScoreBreakdownBar label="Operating Age" value={sb?.operating_age ?? 0} max={25} />
              <ScoreBreakdownBar label="Digital Health" value={sb?.digital_health ?? 0} max={30} />
              <ScoreBreakdownBar label="Review Signals" value={sb?.review_signals ?? 0} max={25} />
              <ScoreBreakdownBar label="Lifecycle Signals" value={sb?.lifecycle_signals ?? 0} max={20} />
            </div>
          </div>

          {/* Digital Profile */}
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-4">Digital Profile</h2>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">Domain Age</span>
                <span className="text-slate-300">{company.domainAgeYears ? `${company.domainAgeYears} years` : '—'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">SSL</span>
                {company.sslValid
                  ? <span className="flex items-center gap-1 text-emerald-400 text-xs"><Shield className="w-3.5 h-3.5" /> Valid</span>
                  : <span className="flex items-center gap-1 text-red-400 text-xs"><ShieldOff className="w-3.5 h-3.5" /> None</span>
                }
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Website</span>
                <span className={company.websiteActive ? 'text-emerald-400' : 'text-red-400'}>
                  {company.websiteActive == null ? '—' : company.websiteActive ? 'Active' : 'Down'}
                </span>
              </div>
              {company.websiteLoadTimeMs && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Load Time</span>
                  <span className={clsx('text-sm', company.websiteLoadTimeMs > 4000 ? 'text-amber-400' : 'text-slate-300')}>
                    {(company.websiteLoadTimeMs / 1000).toFixed(1)}s
                  </span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-slate-500">Tech Stack</span>
                <span className="text-slate-300 text-right max-w-32 truncate">
                  {company.techStack?.join(', ') || '—'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-500">Social</span>
                <div className="flex items-center gap-2">
                  <Facebook className={clsx('w-3.5 h-3.5', company.hasFacebook ? 'text-blue-400' : 'text-slate-700')} />
                  <Instagram className={clsx('w-3.5 h-3.5', company.hasInstagram ? 'text-pink-400' : 'text-slate-700')} />
                </div>
              </div>
            </div>
          </div>

          {/* Google Data */}
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-4">Google Profile</h2>
            <div className="space-y-3 text-sm">
              {company.googleRating != null && (
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Rating</span>
                  <div className="flex items-center gap-1.5">
                    <Star className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-slate-300">{company.googleRating}</span>
                    <span className="text-slate-500">({company.googleReviewCount} reviews)</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Feedback */}
          <div className="card p-5">
            <h2 className="text-slate-300 text-sm font-medium mb-4">Feedback</h2>
            {company.feedback ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-400" />
                  <span className="text-slate-300 text-sm capitalize">{company.feedback.outcome.replace(/_/g,' ')}</span>
                </div>
                {company.feedback.notes && (
                  <p className="text-slate-500 text-xs">{company.feedback.notes}</p>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-col gap-2">
                  {FEEDBACK_OPTIONS.map(opt => (
                    <button
                      key={opt.value}
                      onClick={() => setSelectedOutcome(opt.value)}
                      className={clsx(
                        'text-left px-3 py-2 rounded-md border text-xs font-medium transition-colors',
                        selectedOutcome === opt.value ? opt.cls : 'border-surface-700 text-slate-500 hover:text-slate-300'
                      )}
                    >
                      {opt.label}
                    </button>
                  ))}
                </div>
                {selectedOutcome && (
                  <>
                    <textarea
                      placeholder="Notes (optional)…"
                      value={feedbackNote}
                      onChange={e => setFeedbackNote(e.target.value)}
                      rows={2}
                      className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-xs rounded-md px-3 py-2 focus:outline-none focus:border-accent resize-none"
                    />
                    <button
                      onClick={() => feedbackMut.mutate({ outcome: selectedOutcome, notes: feedbackNote })}
                      disabled={feedbackMut.isPending}
                      className="btn-primary w-full text-xs"
                    >
                      {feedbackMut.isPending ? 'Saving…' : 'Save Feedback'}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Dossier */}
        <div className="col-span-2">
          <div className="card p-5 h-full">
            <div className="flex items-center justify-between mb-5">
              <h2 className="text-slate-300 text-sm font-medium flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Acquisition Dossier
              </h2>
              {!hasDossier && (
                <button
                  onClick={() => dossierMut.mutate()}
                  disabled={dossierMut.isPending}
                  className="btn-primary flex items-center gap-2 text-xs"
                >
                  {dossierMut.isPending
                    ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating…</>
                    : <><FileText className="w-3.5 h-3.5" /> Generate Dossier</>
                  }
                </button>
              )}
            </div>

            {hasDossier ? (
              <div className="dossier-content prose prose-invert max-w-none">
                {company.dossier?.content && (
                  <div className="flex items-center justify-between mb-4">
                    <div className="terminal-label text-[10px]">INVESTMENT MEMO</div>
                    <MemoExport
                      memoContent={company.dossier.content}
                      companyName={company?.name || 'company'}
                      memoId={company.dossier?.id}
                    />
                  </div>
                )}
                <ReactMarkdown>{company.dossier!.content}</ReactMarkdown>
                <div className="mt-6 pt-4 border-t border-surface-700 flex items-center gap-2 text-slate-600 text-xs">
                  <Clock className="w-3.5 h-3.5" />
                  Generated {company.dossier!.generatedAt
                    ? new Date(company.dossier!.generatedAt).toLocaleString() : '—'}
                  · {company.dossier!.modelUsed}
                </div>
              </div>
            ) : dossierMut.isPending ? (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <Loader2 className="w-8 h-8 text-accent animate-spin mb-3" />
                <p className="text-slate-400 text-sm">Generating investor dossier…</p>
                <p className="text-slate-600 text-xs mt-1">Using AI to analyze signals and write report</p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-64 text-center">
                <FileText className="w-10 h-10 text-slate-700 mb-3" />
                <p className="text-slate-400 text-sm">No dossier generated yet</p>
                <p className="text-slate-600 text-xs mt-1">Click "Generate Dossier" to create an investor-ready report</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

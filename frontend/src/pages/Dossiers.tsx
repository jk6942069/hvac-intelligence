import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { FileText, Star, ChevronRight, Clock } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { fetchDossiers } from '../api/client'
import ScoreBar from '../components/ScoreBar'
import type { DossierItem } from '../types'

export default function Dossiers() {
  const navigate = useNavigate()
  const [selected, setSelected] = useState<DossierItem | null>(null)
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['dossiers', page],
    queryFn: () => fetchDossiers(page, 50),
  })

  return (
    <div className="p-8 space-y-5">
      <div>
        <h1 className="text-slate-100 text-xl font-semibold">Acquisition Dossiers</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Investor-ready intelligence reports — {data?.total ?? 0} generated
        </p>
      </div>

      <div className="grid grid-cols-5 gap-5 h-[calc(100vh-180px)]">
        {/* List */}
        <div className="col-span-2 card overflow-y-auto">
          {isLoading ? (
            <div className="space-y-px">
              {[...Array(8)].map((_, i) => (
                <div key={i} className="p-4 border-b border-surface-800">
                  <div className="h-4 bg-surface-800 rounded animate-pulse mb-2" />
                  <div className="h-3 bg-surface-800 rounded animate-pulse w-2/3" />
                </div>
              ))}
            </div>
          ) : (data?.dossiers ?? []).length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-center">
              <FileText className="w-8 h-8 text-slate-700 mb-2" />
              <p className="text-slate-500 text-sm">No dossiers yet</p>
              <p className="text-slate-600 text-xs mt-1">Run the pipeline to generate reports</p>
            </div>
          ) : (
            <div>
              {(data?.dossiers ?? []).map((d: DossierItem) => (
                <div
                  key={d.id}
                  onClick={() => setSelected(d)}
                  className={`p-4 border-b border-surface-800 cursor-pointer transition-colors ${
                    selected?.id === d.id
                      ? 'bg-accent/10 border-l-2 border-l-accent'
                      : 'hover:bg-surface-800'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-slate-200 text-sm font-medium truncate flex-1">{d.companyName}</div>
                    <ChevronRight className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
                  </div>
                  <div className="text-slate-500 text-xs mb-2">{d.companyCity}, {d.companyState}</div>
                  <div className="flex items-center gap-3">
                    <ScoreBar score={d.companyScore} size="sm" className="w-24" />
                    {d.companyRank && (
                      <span className="text-slate-600 text-xs">Rank #{d.companyRank}</span>
                    )}
                  </div>
                  {d.generatedAt && (
                    <div className="flex items-center gap-1 text-slate-600 text-xs mt-1.5">
                      <Clock className="w-3 h-3" />
                      {new Date(d.generatedAt).toLocaleDateString()}
                    </div>
                  )}
                </div>
              ))}
              {data && data.pages > 1 && (
                <div className="flex justify-between items-center p-3 border-t border-surface-800">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="btn-secondary px-3 py-1 text-xs disabled:opacity-40"
                  >← Prev</button>
                  <span className="text-slate-500 text-xs">{page}/{data.pages}</span>
                  <button
                    onClick={() => setPage(p => Math.min(data.pages, p + 1))}
                    disabled={page >= data.pages}
                    className="btn-secondary px-3 py-1 text-xs disabled:opacity-40"
                  >Next →</button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Viewer */}
        <div className="col-span-3 card p-6 overflow-y-auto">
          {selected ? (
            <>
              <div className="flex items-start justify-between mb-5">
                <div>
                  <h2 className="text-slate-100 text-base font-semibold">{selected.companyName}</h2>
                  <div className="text-slate-500 text-sm mt-0.5">
                    {selected.companyCity}, {selected.companyState}
                    {selected.companyRank && ` · Rank #${selected.companyRank}`}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <ScoreBar score={selected.companyScore} size="md" className="w-32" />
                  <button
                    onClick={() => navigate(`/companies/${selected.companyId}`)}
                    className="btn-secondary flex items-center gap-1.5 text-xs"
                  >
                    View Profile
                  </button>
                </div>
              </div>
              <div className="dossier-content">
                <ReactMarkdown>{selected.content}</ReactMarkdown>
              </div>
              <div className="mt-6 pt-4 border-t border-surface-700 text-slate-600 text-xs flex items-center gap-2">
                <Clock className="w-3.5 h-3.5" />
                Generated {selected.generatedAt
                  ? new Date(selected.generatedAt).toLocaleString() : '—'}
                · {selected.modelUsed}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <FileText className="w-12 h-12 text-slate-700 mb-4" />
              <p className="text-slate-400 text-sm">Select a dossier to read</p>
              <p className="text-slate-600 text-xs mt-1">
                Investor-ready acquisition intelligence reports
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

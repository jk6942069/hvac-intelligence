import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, LayoutDashboard, Building2, Terminal, Settings, X } from 'lucide-react'
import { fetchDealFeed } from '../api/client'
import type { Deal } from '../types'

interface CommandPaletteProps {}

export default function CommandPalette({}: CommandPaletteProps) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Deal[]>([])
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault()
        setOpen(o => !o)
        setQuery('')
        setResults([])
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50)
  }, [open])

  useEffect(() => {
    if (!query.trim()) { setResults([]); return }
    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const res = await fetchDealFeed({ search: query, limit: 6 })
        setResults(res.deals)
      } catch {}
      setLoading(false)
    }, 200)
    return () => clearTimeout(timer)
  }, [query])

  const navItems = [
    { label: 'Deal Desk', path: '/', icon: LayoutDashboard },
    { label: 'Companies', path: '/companies', icon: Building2 },
    { label: 'Ops / Pipeline', path: '/ops', icon: Terminal },
    { label: 'Settings', path: '/settings', icon: Settings },
  ]

  if (!open) return null

  return (
    <div className="cmd-overlay" onClick={() => setOpen(false)}>
      <div
        className="w-full max-w-lg mx-4 glass-card overflow-hidden"
        onClick={e => e.stopPropagation()}
        style={{ boxShadow: '0 0 0 1px #1A2E4A, 0 20px 60px rgba(0,0,0,0.6), 0 0 40px rgba(0,212,255,0.08)' }}
      >
        {/* Input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-surface-600">
          <Search size={16} className="text-slate-500 shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="Search companies, navigate pages..."
            className="flex-1 bg-transparent text-slate-100 text-sm outline-none placeholder-slate-600 font-sans"
          />
          <button onClick={() => setOpen(false)}>
            <X size={14} className="text-slate-600 hover:text-slate-400" />
          </button>
        </div>

        {/* Results */}
        <div className="max-h-80 overflow-y-auto">
          {!query && (
            <div className="py-2">
              <div className="px-4 py-1.5 terminal-label text-[10px]">NAVIGATION</div>
              {navItems.map(item => (
                <button
                  key={item.path}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-surface-700 transition-colors text-left"
                  onClick={() => { navigate(item.path); setOpen(false) }}
                >
                  <item.icon size={14} className="text-slate-500" />
                  <span className="text-sm text-slate-300">{item.label}</span>
                </button>
              ))}
            </div>
          )}

          {query && (
            <div className="py-2">
              <div className="px-4 py-1.5 terminal-label text-[10px]">COMPANIES</div>
              {loading && (
                <div className="px-4 py-3 text-sm text-slate-500">Searching...</div>
              )}
              {!loading && results.length === 0 && (
                <div className="px-4 py-3 text-sm text-slate-500">No results for "{query}"</div>
              )}
              {results.map(deal => (
                <button
                  key={deal.id}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-surface-700 transition-colors text-left"
                  onClick={() => { navigate(`/?company=${deal.id}`); setOpen(false) }}
                >
                  <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                    deal.convictionScore >= 60 ? 'bg-terminal-green' :
                    deal.convictionScore >= 40 ? 'bg-terminal-amber' : 'bg-terminal-red'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-slate-200 truncate">{deal.name}</div>
                    <div className="text-xs text-slate-500">{deal.city}, {deal.state}</div>
                  </div>
                  <span className={`font-mono text-xs font-medium ${
                    deal.convictionScore >= 60 ? 'text-terminal-green' :
                    deal.convictionScore >= 40 ? 'text-terminal-amber' : 'text-slate-500'
                  }`}>{deal.convictionScore}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

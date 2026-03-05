import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, Save } from 'lucide-react'
import { fetchConfig, updateConfig } from '../api/client'

export default function Settings() {
  const qc = useQueryClient()

  // Account
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')

  // Deal Export
  const [exportFormat, setExportFormat] = useState<'pdf' | 'markdown'>('pdf')
  const [memoHeader, setMemoHeader] = useState('')

  // Report Format
  const [currency, setCurrency] = useState<'USD' | 'GBP' | 'EUR' | 'CAD'>('USD')
  const [valuationLow, setValuationLow] = useState(3.5)
  const [valuationHigh, setValuationHigh] = useState(5.5)
  const [avgTicket, setAvgTicket] = useState(385)
  const [ebitdaMargin, setEbitdaMargin] = useState(20)
  const [jobsPerReview, setJobsPerReview] = useState(8)

  // API Keys
  const [firecrawlKey, setFirecrawlKey] = useState('')
  const [openrouterKey, setOpenrouterKey] = useState('')
  const [saved, setSaved] = useState(false)

  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: fetchConfig,
  })

  const mutation = useMutation({
    mutationFn: updateConfig,
    onSuccess: () => {
      setSaved(true)
      qc.invalidateQueries({ queryKey: ['config'] })
      setTimeout(() => setSaved(false), 2500)
    },
  })

  const handleSaveKeys = () => {
    const payload: Record<string, string> = {}
    if (firecrawlKey) payload.firecrawlApiKey = firecrawlKey
    if (openrouterKey) payload.openrouterApiKey = openrouterKey
    mutation.mutate(payload)
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-5 max-w-2xl">
      <div>
        <h1 className="font-display text-lg font-semibold text-slate-100">Settings</h1>
        <p className="text-slate-500 text-xs mt-0.5 font-mono">Platform preferences and integrations</p>
      </div>

      {/* Account Settings */}
      <div className="glass-card p-5 space-y-4">
        <h2 className="text-slate-300 text-sm font-medium">Account Settings</h2>
        <div className="space-y-3">
          <div>
            <label className="text-slate-400 text-xs block mb-1.5">Display Name</label>
            <input
              type="text"
              placeholder="Your name"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent placeholder-slate-600"
            />
          </div>
          <div>
            <label className="text-slate-400 text-xs block mb-1.5">Email</label>
            <input
              type="email"
              placeholder="you@firm.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent placeholder-slate-600"
            />
          </div>
        </div>
      </div>

      {/* Team Members */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-slate-300 text-sm font-medium">Team Members</h2>
          <span className="text-xs bg-surface-700 text-slate-500 px-2 py-0.5 rounded font-mono">Coming soon</span>
        </div>
        <p className="text-slate-600 text-xs mt-2">
          Multi-user workspaces with role-based access will be available in a future update.
        </p>
      </div>

      {/* Deal Export Preferences */}
      <div className="glass-card p-5 space-y-4">
        <h2 className="text-slate-300 text-sm font-medium">Deal Export Preferences</h2>

        <div>
          <label className="text-slate-400 text-xs block mb-2">Default Export Format</label>
          <div className="flex gap-3">
            {(['pdf', 'markdown'] as const).map(fmt => (
              <label key={fmt} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="exportFormat"
                  value={fmt}
                  checked={exportFormat === fmt}
                  onChange={() => setExportFormat(fmt)}
                  className="accent-accent"
                />
                <span className="text-sm text-slate-300 capitalize">{fmt === 'pdf' ? 'PDF' : 'Markdown'}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="text-slate-400 text-xs block mb-1.5">Memo Header</label>
          <input
            type="text"
            placeholder="e.g. Acme Capital Partners"
            value={memoHeader}
            onChange={e => setMemoHeader(e.target.value)}
            className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent placeholder-slate-600"
          />
          <p className="text-slate-600 text-xs mt-1">Company or firm name shown in exported memos</p>
        </div>
      </div>

      {/* Report Format Preferences */}
      <div className="glass-card p-5 space-y-4">
        <h2 className="text-slate-300 text-sm font-medium">Report Format Preferences</h2>

        <div>
          <label className="text-slate-400 text-xs block mb-1.5">Currency</label>
          <select
            value={currency}
            onChange={e => setCurrency(e.target.value as typeof currency)}
            className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent"
          >
            <option value="USD">USD — US Dollar</option>
            <option value="GBP">GBP — British Pound</option>
            <option value="EUR">EUR — Euro</option>
            <option value="CAD">CAD — Canadian Dollar</option>
          </select>
        </div>

        <div>
          <label className="text-slate-400 text-xs block mb-1.5">Valuation Multiple Range</label>
          <div className="flex items-center gap-3">
            <input
              type="number"
              step={0.5}
              min={1}
              max={20}
              value={valuationLow}
              onChange={e => setValuationLow(Number(e.target.value))}
              className="w-24 bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent"
            />
            <span className="text-slate-500 text-sm">×</span>
            <span className="text-slate-500 text-xs">to</span>
            <input
              type="number"
              step={0.5}
              min={1}
              max={20}
              value={valuationHigh}
              onChange={e => setValuationHigh(Number(e.target.value))}
              className="w-24 bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent"
            />
            <span className="text-slate-500 text-sm">×</span>
          </div>
          <p className="text-slate-600 text-xs mt-1">EBITDA multiple range used in valuation estimates</p>
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="text-slate-400 text-xs block mb-1.5">Avg HVAC Ticket Size</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">$</span>
              <input
                type="number"
                min={100}
                max={5000}
                step={5}
                value={avgTicket}
                onChange={e => setAvgTicket(Number(e.target.value))}
                className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md pl-7 pr-3 py-2 focus:outline-none focus:border-accent"
              />
            </div>
          </div>

          <div>
            <label className="text-slate-400 text-xs block mb-1.5">EBITDA Margin</label>
            <div className="relative">
              <input
                type="number"
                min={5}
                max={50}
                step={1}
                value={ebitdaMargin}
                onChange={e => setEbitdaMargin(Number(e.target.value))}
                className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 pr-8 py-2 focus:outline-none focus:border-accent"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">%</span>
            </div>
          </div>

          <div>
            <label className="text-slate-400 text-xs block mb-1.5">Jobs per Review</label>
            <div className="relative">
              <input
                type="number"
                min={1}
                max={50}
                step={1}
                value={jobsPerReview}
                onChange={e => setJobsPerReview(Number(e.target.value))}
                className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 pr-8 py-2 focus:outline-none focus:border-accent"
              />
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">×</span>
            </div>
          </div>
        </div>
      </div>

      {/* Notifications */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-slate-300 text-sm font-medium">Notifications</h2>
          <span className="text-xs bg-surface-700 text-slate-500 px-2 py-0.5 rounded font-mono">Coming soon</span>
        </div>
        <p className="text-slate-600 text-xs mt-2">
          Email and webhook notifications for pipeline completion and new high-conviction targets.
        </p>
      </div>

      {/* Advanced Integrations */}
      <div className="mt-2">
        <div className="flex items-center gap-3 mb-3">
          <div className="flex-1 h-px bg-surface-700" />
          <span className="text-slate-600 text-[10px] font-mono uppercase tracking-widest shrink-0">Advanced Integrations</span>
          <div className="flex-1 h-px bg-surface-700" />
        </div>

        <div className="glass-card p-5 space-y-4 border-surface-700/50">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-slate-500 text-xs font-medium font-mono">Firecrawl API Key</label>
              {config?.hasFirecrawlKey
                ? <span className="text-emerald-400/70 text-xs flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Configured</span>
                : <span className="text-slate-600 text-xs">Not set</span>
              }
            </div>
            <input
              type="password"
              placeholder={config?.hasFirecrawlKey ? "Update key (leave blank to keep)" : "fc-…"}
              value={firecrawlKey}
              onChange={e => setFirecrawlKey(e.target.value)}
              className="w-full bg-surface-800 border border-surface-700 text-slate-400 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent/50 font-mono placeholder-slate-700"
            />
            <p className="text-slate-700 text-xs mt-1">Optional — enables real-time web discovery</p>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-slate-500 text-xs font-medium font-mono">OpenRouter API Key</label>
              {config?.hasOpenrouterKey
                ? <span className="text-emerald-400/70 text-xs flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Configured</span>
                : <span className="text-slate-600 text-xs">Not set</span>
              }
            </div>
            <input
              type="password"
              placeholder={config?.hasOpenrouterKey ? "Update key (leave blank to keep)" : "sk-or-…"}
              value={openrouterKey}
              onChange={e => setOpenrouterKey(e.target.value)}
              className="w-full bg-surface-800 border border-surface-700 text-slate-400 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent/50 font-mono placeholder-slate-700"
            />
            <p className="text-slate-700 text-xs mt-1">Optional — enables LLM Council analysis</p>
          </div>

          <div className="flex items-center gap-3 pt-1">
            <button
              onClick={handleSaveKeys}
              disabled={mutation.isPending || (!firecrawlKey && !openrouterKey)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-surface-700 hover:bg-surface-600 text-slate-400 border border-surface-600 rounded transition-colors disabled:opacity-40"
            >
              <Save className="w-3.5 h-3.5" />
              {mutation.isPending ? 'Saving…' : 'Save Keys'}
            </button>
            {saved && (
              <span className="text-emerald-400/80 text-xs flex items-center gap-1">
                <CheckCircle className="w-3.5 h-3.5" /> Saved
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

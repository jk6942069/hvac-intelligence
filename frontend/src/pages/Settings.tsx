import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Settings as SettingsIcon, Key, CheckCircle, AlertCircle, ToggleLeft, ToggleRight } from 'lucide-react'
import clsx from 'clsx'
import { fetchConfig, updateConfig } from '../api/client'

export default function Settings() {
  const qc = useQueryClient()
  const [googleKey, setGoogleKey] = useState('')
  const [anthropicKey, setAnthropicKey] = useState('')
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
      setTimeout(() => setSaved(false), 2000)
    },
  })

  const mockMutation = useMutation({
    mutationFn: (val: boolean) => updateConfig({ useMockData: val }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config'] }),
  })

  const handleSaveKeys = () => {
    const payload: Record<string, string> = {}
    if (googleKey) payload.googlePlacesApiKey = googleKey
    if (anthropicKey) payload.anthropicApiKey = anthropicKey
    mutation.mutate(payload)
  }

  return (
    <div className="h-full overflow-y-auto p-6 space-y-5 max-w-2xl">
      <div>
        <h1 className="font-display text-lg font-semibold text-slate-100">Settings</h1>
        <p className="text-slate-500 text-xs mt-0.5 font-mono">Configure API keys and pipeline options</p>
      </div>

      {/* Mode Toggle */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-slate-300 text-sm font-medium flex items-center gap-2">
              <SettingsIcon className="w-4 h-4" />
              Demo Mode
            </h2>
            <p className="text-slate-500 text-xs mt-1">
              Use synthetic data — no API keys required. Turn off to use real Google Places & Anthropic APIs.
            </p>
          </div>
          <button
            onClick={() => mockMutation.mutate(!config?.useMockData)}
            className="flex-shrink-0 ml-4"
          >
            {config?.useMockData
              ? <ToggleRight className="w-8 h-8 text-accent" />
              : <ToggleLeft className="w-8 h-8 text-slate-600" />
            }
          </button>
        </div>
        <div className={clsx(
          'mt-3 flex items-center gap-2 text-xs px-3 py-2 rounded-md',
          config?.useMockData
            ? 'bg-amber-500/10 text-amber-400'
            : 'bg-emerald-500/10 text-emerald-400'
        )}>
          {config?.useMockData
            ? <><AlertCircle className="w-3.5 h-3.5" /> Demo mode ON — using synthetic HVAC company data</>
            : <><CheckCircle className="w-3.5 h-3.5" /> Live mode — using real APIs</>
          }
        </div>
      </div>

      {/* API Keys */}
      <div className="glass-card p-5 space-y-5">
        <h2 className="text-slate-300 text-sm font-medium flex items-center gap-2">
          <Key className="w-4 h-4" />
          API Keys
        </h2>

        <div className="space-y-4">
          {/* Google */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-slate-400 text-xs font-medium">Google Places API Key</label>
              {config?.hasGoogleKey
                ? <span className="text-emerald-400 text-xs flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Configured</span>
                : <span className="text-slate-600 text-xs">Not set</span>
              }
            </div>
            <input
              type="password"
              placeholder={config?.hasGoogleKey ? "Update key (leave blank to keep current)" : "AIza…"}
              value={googleKey}
              onChange={e => setGoogleKey(e.target.value)}
              className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent font-mono"
            />
            <p className="text-slate-600 text-xs mt-1">
              Required for real HVAC company discovery via Google Maps Platform
            </p>
          </div>

          {/* Anthropic */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-slate-400 text-xs font-medium">Anthropic API Key</label>
              {config?.hasAnthropicKey
                ? <span className="text-emerald-400 text-xs flex items-center gap-1"><CheckCircle className="w-3 h-3" /> Configured</span>
                : <span className="text-slate-600 text-xs">Not set</span>
              }
            </div>
            <input
              type="password"
              placeholder={config?.hasAnthropicKey ? "Update key (leave blank to keep current)" : "sk-ant-…"}
              value={anthropicKey}
              onChange={e => setAnthropicKey(e.target.value)}
              className="w-full bg-surface-800 border border-surface-700 text-slate-200 text-sm rounded-md px-3 py-2 focus:outline-none focus:border-accent font-mono"
            />
            <p className="text-slate-600 text-xs mt-1">
              Required for AI-powered dossier generation (Claude claude-sonnet-4-6)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSaveKeys}
            disabled={mutation.isPending || (!googleKey && !anthropicKey)}
            className="btn-primary disabled:opacity-50"
          >
            {mutation.isPending ? 'Saving…' : 'Save API Keys'}
          </button>
          {saved && (
            <span className="text-emerald-400 text-sm flex items-center gap-1">
              <CheckCircle className="w-4 h-4" /> Saved
            </span>
          )}
        </div>
      </div>

      {/* Info */}
      <div className="glass-card p-5">
        <h2 className="text-slate-300 text-sm font-medium mb-3">How to get API Keys</h2>
        <div className="space-y-3 text-sm text-slate-500">
          <div>
            <div className="text-slate-300 font-medium mb-0.5">Google Places API</div>
            <ol className="list-decimal list-inside space-y-0.5 text-xs">
              <li>Go to console.cloud.google.com</li>
              <li>Create a project → Enable "Places API"</li>
              <li>Create credentials → API Key</li>
              <li>Enable billing (required for Places API)</li>
            </ol>
          </div>
          <div>
            <div className="text-slate-300 font-medium mb-0.5">Anthropic API</div>
            <ol className="list-decimal list-inside space-y-0.5 text-xs">
              <li>Go to console.anthropic.com</li>
              <li>Create account → Go to API Keys</li>
              <li>Create a new API key</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  )
}

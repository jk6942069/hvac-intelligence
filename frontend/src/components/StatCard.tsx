import clsx from 'clsx'
import type { LucideIcon } from 'lucide-react'

interface StatCardProps {
  label: string
  value: string | number
  icon: LucideIcon
  sub?: string
  accent?: 'blue' | 'green' | 'amber' | 'red' | 'purple'
}

const ACCENT_CLASSES = {
  blue:   { bg: 'bg-blue-500/10',   icon: 'text-blue-400',   border: 'border-blue-500/20' },
  green:  { bg: 'bg-emerald-500/10', icon: 'text-emerald-400', border: 'border-emerald-500/20' },
  amber:  { bg: 'bg-amber-500/10',  icon: 'text-amber-400',  border: 'border-amber-500/20' },
  red:    { bg: 'bg-red-500/10',    icon: 'text-red-400',    border: 'border-red-500/20' },
  purple: { bg: 'bg-violet-500/10', icon: 'text-violet-400', border: 'border-violet-500/20' },
}

export default function StatCard({ label, value, icon: Icon, sub, accent = 'blue' }: StatCardProps) {
  const cls = ACCENT_CLASSES[accent]
  return (
    <div className={clsx('card p-5 flex items-start gap-4', cls.border)}>
      <div className={clsx('p-2.5 rounded-lg flex-shrink-0', cls.bg)}>
        <Icon className={clsx('w-5 h-5', cls.icon)} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-1">{label}</div>
        <div className="text-slate-100 text-2xl font-semibold tabular-nums">{value}</div>
        {sub && <div className="text-slate-500 text-xs mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

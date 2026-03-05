import clsx from 'clsx'
import type { Signal } from '../types'

interface SignalBadgeProps {
  signal: Signal
  size?: 'sm' | 'md'
}

const SEVERITY_CLS = {
  high:   'bg-red-500/15 text-red-400 border-red-500/25',
  medium: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
  low:    'bg-blue-500/15 text-blue-400 border-blue-500/25',
}

const DOTS = {
  high:   'bg-red-400',
  medium: 'bg-amber-400',
  low:    'bg-blue-400',
}

export default function SignalBadge({ signal, size = 'sm' }: SignalBadgeProps) {
  return (
    <span
      title={signal.description}
      className={clsx(
        'inline-flex items-center gap-1.5 border rounded font-medium',
        SEVERITY_CLS[signal.severity],
        size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1'
      )}
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full flex-shrink-0', DOTS[signal.severity])} />
      {signal.label}
    </span>
  )
}

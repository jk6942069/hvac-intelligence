import clsx from 'clsx'

interface ScoreBarProps {
  score: number
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  className?: string
}

function getScoreColor(score: number): string {
  if (score >= 75) return 'text-blue-400'
  if (score >= 60) return 'text-emerald-400'
  if (score >= 40) return 'text-amber-400'
  return 'text-red-400'
}

function getBarColor(score: number): string {
  if (score >= 75) return 'bg-blue-500'
  if (score >= 60) return 'bg-emerald-500'
  if (score >= 40) return 'bg-amber-500'
  return 'bg-red-500'
}

const SIZE_HEIGHTS = { sm: 'h-1.5', md: 'h-2', lg: 'h-2.5' }
const SIZE_TEXT = { sm: 'text-xs', md: 'text-sm', lg: 'text-base' }

export default function ScoreBar({
  score,
  size = 'sm',
  showLabel = true,
  className,
}: ScoreBarProps) {
  const pct = Math.min(100, Math.max(0, score))
  return (
    <div className={clsx('flex items-center gap-2', className)}>
      {showLabel && (
        <span className={clsx('font-semibold tabular-nums w-8 text-right flex-shrink-0', getScoreColor(score), SIZE_TEXT[size])}>
          {score}
        </span>
      )}
      <div className={clsx('flex-1 bg-surface-700 rounded-full overflow-hidden', SIZE_HEIGHTS[size])}>
        <div
          className={clsx('h-full rounded-full transition-all duration-300', getBarColor(score))}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

import type { TrendData, TrendPoint, InsightsRegion } from '../../types'
import { formatSalary } from './currencyUtils'
import { EmptyState } from '../shared/EmptyState'

// ── SVG line/area chart ───────────────────────────────────────────────────────

interface MiniChartProps {
  points: TrendPoint[]
  /** How to extract the x-axis label from a point */
  getLabel: (p: TrendPoint) => string
  /** How to format the y-axis tick / tooltip text */
  formatY: (v: number) => string
  color: string       // Tailwind-compatible hex or CSS color for stroke
  fillColor: string   // lighter fill for area
  title: string
  yUnit?: string
}

function MiniChart({ points, getLabel, formatY, color, fillColor, title, yUnit }: MiniChartProps) {
  if (points.length === 0) {
    return (
      <EmptyState
        title={`No data for "${title}"`}
        description="Not enough historical data points to show a trend."
      />
    )
  }

  const W = 480
  const H = 160
  const PAD = { top: 16, right: 12, bottom: 36, left: 56 }
  const chartW = W - PAD.left - PAD.right
  const chartH = H - PAD.top - PAD.bottom

  const values = points.map((p) => p.value)
  const minV = Math.min(...values)
  const maxV = Math.max(...values)
  const span = maxV - minV || 1

  const toX = (i: number) => PAD.left + (i / Math.max(points.length - 1, 1)) * chartW
  const toY = (v: number) => PAD.top + chartH - ((v - minV) / span) * chartH

  // Build SVG path data
  const lineD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(p.value).toFixed(1)}`)
    .join(' ')

  const areaD =
    `M${toX(0).toFixed(1)},${(PAD.top + chartH).toFixed(1)} ` +
    points.map((p, i) => `L${toX(i).toFixed(1)},${toY(p.value).toFixed(1)}`).join(' ') +
    ` L${toX(points.length - 1).toFixed(1)},${(PAD.top + chartH).toFixed(1)} Z`

  // Y-axis ticks (3 evenly spaced)
  const yTicks = [minV, minV + span / 2, maxV]

  // X-axis labels: show first, last, and one or two in between — avoid crowding
  const xLabelIndices = getXLabelIndices(points.length)

  return (
    <figure className="w-full" aria-label={title}>
      <figcaption className="sr-only">{title} trend chart</figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label={`${title}: line chart from ${getLabel(points[0])} to ${getLabel(points[points.length - 1])}`}
        preserveAspectRatio="xMidYMid meet"
      >
        {/* Area fill */}
        <path d={areaD} fill={fillColor} opacity={0.35} />

        {/* Horizontal grid lines */}
        {yTicks.map((tick, i) => (
          <g key={i}>
            <line
              x1={PAD.left}
              y1={toY(tick).toFixed(1)}
              x2={PAD.left + chartW}
              y2={toY(tick).toFixed(1)}
              stroke="#e2e8f0"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 6}
              y={parseFloat(toY(tick).toFixed(1)) + 4}
              textAnchor="end"
              fontSize={10}
              fill="#94a3b8"
            >
              {formatY(tick)}{yUnit}
            </text>
          </g>
        ))}

        {/* Line */}
        <path d={lineD} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

        {/* Data points */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={toX(i).toFixed(1)}
            cy={toY(p.value).toFixed(1)}
            r={3}
            fill={color}
            aria-label={`${getLabel(p)}: ${formatY(p.value)}${yUnit ?? ''}`}
          />
        ))}

        {/* X-axis labels */}
        {xLabelIndices.map((i) => (
          <text
            key={i}
            x={toX(i).toFixed(1)}
            y={H - 8}
            textAnchor="middle"
            fontSize={10}
            fill="#94a3b8"
          >
            {getLabel(points[i])}
          </text>
        ))}
      </svg>
    </figure>
  )
}

/** Choose a sparse set of x-axis label indices (≤5) that avoid crowding. */
function getXLabelIndices(n: number): number[] {
  if (n <= 1) return [0]
  if (n <= 5) return Array.from({ length: n }, (_, i) => i)
  const step = Math.floor((n - 1) / 4)
  const indices = [0]
  let cur = step
  while (cur < n - step) {
    indices.push(cur)
    cur += step
  }
  indices.push(n - 1)
  return [...new Set(indices)]
}

// ── Main component ────────────────────────────────────────────────────────────

interface HiringTrendsProps {
  trends: TrendData
  region: InsightsRegion
}

export function HiringTrends({ trends, region }: HiringTrendsProps) {
  const hasSalaryHistory = trends.salary_history.length > 0
  const hasUnemployment = trends.unemployment.length > 0
  const hasEmployment = trends.employment.length > 0

  if (!hasSalaryHistory && !hasUnemployment && !hasEmployment) {
    return (
      <EmptyState
        title="No trend data"
        description="Historical trend data is unavailable for this region right now."
        icon={
          <svg className="h-7 w-7" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18 9 11.25l4.306 4.306a11.95 11.95 0 0 1 5.814-5.518l2.74-1.22m0 0-5.94-2.281m5.94 2.28-2.28 5.941" />
          </svg>
        }
      />
    )
  }

  return (
    <div className="flex flex-col gap-6">
      {hasSalaryHistory && (
        <section aria-labelledby="salary-trend-heading" className="rounded-xl border border-slate-200 bg-white p-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.04)]">
          <h4 id="salary-trend-heading" className="mb-3 text-[13px] font-semibold text-slate-700">
            Average Salary Trend
          </h4>
          <MiniChart
            points={trends.salary_history}
            getLabel={(p) => p.period?.slice(0, 7) ?? ''}
            formatY={(v) => formatSalary(v, region)}
            color="#6366f1"
            fillColor="#6366f1"
            title="Average salary over time"
          />
        </section>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {hasUnemployment && (
          <section aria-labelledby="unemployment-trend-heading" className="rounded-xl border border-slate-200 bg-white p-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.04)]">
            <h4 id="unemployment-trend-heading" className="mb-3 text-[13px] font-semibold text-slate-700">
              Unemployment Rate
            </h4>
            <MiniChart
              points={trends.unemployment}
              getLabel={(p) => String(p.year ?? '')}
              formatY={(v) => v.toFixed(1)}
              yUnit="%"
              color="#f59e0b"
              fillColor="#f59e0b"
              title="Unemployment rate over years"
            />
          </section>
        )}

        {hasEmployment && (
          <section aria-labelledby="employment-trend-heading" className="rounded-xl border border-slate-200 bg-white p-4 shadow-[0_1px_3px_0_rgb(0_0_0_/_0.04)]">
            <h4 id="employment-trend-heading" className="mb-3 text-[13px] font-semibold text-slate-700">
              Employment Rate
            </h4>
            <MiniChart
              points={trends.employment}
              getLabel={(p) => String(p.year ?? '')}
              formatY={(v) => v.toFixed(1)}
              yUnit="%"
              color="#10b981"
              fillColor="#10b981"
              title="Employment rate over years"
            />
          </section>
        )}
      </div>
    </div>
  )
}

import { useEffect, useId, useRef, useState } from 'react'

export type ChartPoint = { x: number; y: number | null; lower?: number; upper?: number }
export type ChartSeries = { label: string; color: string; dashed?: boolean; points: ChartPoint[] }

export function AnalyticsChart({ title, unit, series, xLabel, maximum }: {
  title: string; unit: string; series: ChartSeries[]; xLabel: (value: number) => string; maximum?: number
}) {
  const id = useId(), [cursor, setCursor] = useState<number | null>(null)
  const surface = useRef<HTMLDivElement>(null), [chartWidth, setChartWidth] = useState(920)
  useEffect(() => {
    if (!surface.current || typeof ResizeObserver === 'undefined') return
    const resize = () => {
      const width = surface.current?.querySelector('svg')?.getBoundingClientRect().width ?? surface.current?.clientWidth
      if (width) setChartWidth(Math.max(320, Math.round(width)))
    }
    const observer = new ResizeObserver(resize)
    observer.observe(surface.current); resize()
    return () => observer.disconnect()
  }, [])
  const xs = [...new Set(series.flatMap(s => s.points.map(p => p.x)))].sort((a, b) => a - b)
  const numbers = series.flatMap(s => s.points.flatMap(p => p.y === null ? [] : [p.y, p.upper ?? p.y]))
  if (!xs.length || !numbers.length) return <div className="analytics-empty" ref={surface}>Belum ada sampel untuk grafik ini.</div>
  const minX = xs[0] - (xs.length === 1 ? 60000 : 0), maxX = xs.at(-1)! + (xs.length === 1 ? 60000 : 0), span = maxX - minX
  const top = maximum ?? Math.max(1, Math.max(...numbers) * 1.12)
  const plotWidth = chartWidth - 94
  const px = (x: number) => 66 + (x - minX) / span * plotWidth
  const py = (y: number) => 246 - Math.min(top, Math.max(0, y)) / top * 220
  const active = Math.min(cursor ?? xs.length - 1, xs.length - 1), at = xs[active]
  const format = (n: number) => new Intl.NumberFormat('id-ID', { maximumFractionDigits: top < 10 ? 2 : 1, notation: top > 99999 ? 'compact' : 'standard' }).format(n)
  const paths = (points: ChartPoint[]) => {
    let open = false
    return points.map(p => { if (p.y === null) { open = false; return '' }; const command = open ? 'L' : 'M'; open = true; return `${command}${px(p.x)},${py(p.y)}` }).join(' ')
  }
  const observed = series.map(s => ({ ...s, point: s.points.find(p => p.x === at) }))
  return <div className="analytics-chart" ref={surface}>
    <div className="chart-legend">{series.map(s => <span key={s.label}><i style={{ borderColor: s.color, borderTopStyle: s.dashed ? 'dashed' : 'solid' }} />{s.label}</span>)}<small>{unit}</small></div>
    <svg viewBox={`0 0 ${chartWidth} 290`} role="img" aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`}
      onPointerMove={e => { const rect = e.currentTarget.getBoundingClientRect(); const x = (e.clientX - rect.left) / rect.width * chartWidth; const value = minX + (x - 66) / plotWidth * span; setCursor(xs.reduce((best, v, i) => Math.abs(v - value) < Math.abs(xs[best] - value) ? i : best, 0)) }}>
      <title id={`${id}-title`}>{title}</title><desc id={`${id}-description`}>Grafik {series.map(s => s.label).join(' dan ')}. Periksa setiap titik dengan penggeser atau tabel data di bawah grafik.</desc>
      {[0, 1, 2, 3, 4].map(i => { const v = top * i / 4; return <g key={i}><line x1="66" x2={chartWidth - 28} y1={py(v)} y2={py(v)} stroke="#e4ebf1" /><text x="54" y={py(v) + 4} textAnchor="end">{format(v)}</text></g> })}
      {[0, 1, 2, 3, 4].map(i => { const x = minX + span * i / 4; return <text key={i} x={px(x)} y="273" textAnchor="middle">{xLabel(x)}</text> })}
      {series.map(s => { const band = s.points.filter(p => p.y !== null && p.lower !== undefined && p.upper !== undefined); return <g key={s.label}>
        {band.length > 1 && <path d={`${band.map((p, i) => `${i ? 'L' : 'M'}${px(p.x)},${py(p.upper!)}`).join(' ')} ${[...band].reverse().map(p => `L${px(p.x)},${py(p.lower!)}`).join(' ')} Z`} fill={s.color} opacity=".10" />}
        <path d={paths(s.points)} fill="none" stroke={s.color} strokeWidth="2.8" strokeDasharray={s.dashed ? '7 5' : undefined} strokeLinecap="round" strokeLinejoin="round" />
        {s.points.filter(p => p.y !== null && (s.points.length === 1 || p.x === at)).map(p => <circle key={p.x} cx={px(p.x)} cy={py(p.y!)} r="4" fill={s.color} stroke="white" strokeWidth="2" />)}
      </g> })}
      <line x1={px(at)} x2={px(at)} y1="26" y2="246" stroke="#9aabbb" strokeDasharray="3 4" />
    </svg>
    <div className="chart-readout"><strong>{xLabel(at)}</strong>{observed.map(s => <span key={s.label} style={{ color: s.color }}>{s.label}: <b>{s.point?.y == null ? '—' : `${format(s.point.y)} ${unit}`}</b></span>)}</div>
    {xs.length > 1 && <input className="chart-scrubber" type="range" min="0" max={xs.length - 1} value={active} onChange={e => setCursor(Number(e.target.value))} aria-label={`Periksa titik ${title}`} aria-valuetext={xLabel(at)} />}
    <details className="chart-data"><summary>Lihat tabel data grafik</summary><div className="table-scroll"><table><thead><tr><th>Waktu</th>{series.map(s => <th key={s.label}>{s.label} ({unit})</th>)}</tr></thead><tbody>{xs.map(x => <tr key={x}><td>{xLabel(x)}</td>{series.map(s => { const p = s.points.find(p => p.x === x); return <td key={s.label}>{p?.y == null ? '—' : format(p.y)}</td> })}</tr>)}</tbody></table></div></details>
  </div>
}

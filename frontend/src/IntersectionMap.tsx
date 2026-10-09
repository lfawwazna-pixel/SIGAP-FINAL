import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { directions, directionNames, signalNames, type Direction } from './traffic'
import type { AtcsStatus } from './types/AtcsStatus'
import type { TrafficView } from './types/TrafficView'
import { JunctionRoad } from './JunctionRoad'
import { VehicleLayer } from './VehicleLayer'
import { schematicVehicleLayout } from './schematicVehicleLayout'
import geometry from './geometry/map-geometry.json'

interface Props { selected: Direction; onSelect: (direction: Direction) => void; signals: AtcsStatus['signals']; routes: boolean; vehicles?: TrafficView['vehicles']; markerId?: string; vehicleRunId?: string; schematic?: boolean }
export function IntersectionMap({ selected, onSelect, signals, routes, vehicles = [], markerId = 'route-arrow', vehicleRunId, schematic = false }: Props) {
  const layout = useMemo(() => schematic ? schematicVehicleLayout(vehicles) : null, [schematic, vehicles])
  const runKey = `${vehicleRunId || markerId}:${schematic ? 'video' : 'simulation'}`
  const [extent, setExtent] = useState({ runKey, start: geometry.start })
  const neededStart = layout?.roadStart ?? geometry.start
  // Grow within a run instead of changing the bounds with every video frame.
  const start = runKey === extent.runKey ? Math.min(extent.start, neededStart) : neededStart
  if (extent.runKey !== runKey || extent.start !== start) setExtent({ runKey, start })
  const end = 2 * geometry.center - start
  const span = end - start + 220
  const svg = useRef<SVGSVGElement>(null)
  const previousStart = useRef(geometry.start)
  useLayoutEffect(() => {
    if (previousStart.current === start) return
    const node = svg.current
    const canvas = node?.closest<HTMLElement>('.map-canvas')
    const width = node?.getBoundingClientRect().width ?? 0
    if (canvas && width > 0) {
      // Preserve the operator's view while extending the pannable road canvas.
      const shift = (previousStart.current - start) * width / span
      canvas.scrollLeft += shift
      canvas.scrollTop += shift
      previousStart.current = start
    }
  })
  const labels: Record<Direction, [number, number]> = { U: [400, start-22], T: [end+22, 400], S: [400, end+22], B: [start-22, 400] }
  const countLabels: Record<Direction, [number, number]> = { U: [610, start+45], T: [end-45, 610], S: [190, end-45], B: [start+45, 190] }
  return <svg ref={svg} className="intersection-map" viewBox={`${start-110} ${start-110} ${span} ${span}`} style={span > 1820 ? { width: `${span/1820*100}%`, maxWidth: 'none' } : undefined} role="group" aria-label="Peta interaktif persimpangan empat arah">
    <title>Skema simpang Ibrahim Adjie–Soekarno Hatta</title>
    <desc>{schematic ? 'Satu ikon per kendaraan dalam zona, dengan jenis sesuai klasifikasi YOLO. Motor berjejer hingga tiga per baris dalam lajurnya; bus dan truk sepanjang dua mobil. Ruas memanjang untuk menampung antrean. Susunan bukan posisi atau lintasan persis di video. ' : 'Kendaraan simulasi berpindah lajur bertahap di bagian hulu. '}Tiga lajur masuk dan tiga lajur keluar per pendekat. Kiri untuk ruas pintas, tengah untuk lurus, kanan untuk belok kanan. Lurus dan kanan mengikuti lampu. Pilih pendekat untuk melihat rute.</desc>
    <defs><marker id={markerId} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9" fill="none" stroke="#1763a6" strokeWidth="2" /></marker></defs>
    <JunctionRoad selected={selected} markerId={markerId} roadStart={start} />
    {routes && <g transform={`rotate(${directions.indexOf(selected) * 90} ${geometry.center} ${geometry.center})`} className="selected-routes" aria-label={`Rute lurus dan kanan dari ${directionNames[selected]}, mengikuti lampu`}>
      <path d={`M${geometry.lane_centers.middle} ${geometry.stop_line+8} V${end-60}`} markerEnd={`url(#${markerId})`} />
      <path d={`M${geometry.lane_centers.inner} ${geometry.stop_line+8} C${geometry.lane_centers.inner} ${geometry.center} ${geometry.center} ${geometry.lane_centers.inner} ${geometry.stop_line} ${geometry.lane_centers.inner} H${start+60}`} markerEnd={`url(#${markerId})`} />
    </g>}
    <VehicleLayer key={runKey} vehicles={layout?.vehicles ?? vehicles} schematic={schematic} />
    {directions.map((code, i) => {
      const signal = signals?.[code] ?? 'unknown'
      return <g key={`signal-${code}`} transform={`rotate(${i * 90} 400 400)`} role="img" aria-label={`Lampu ${directionNames[code]}: ${signalNames[signal]}`} data-signal={signal}>
        <rect className="signal-housing" x="497" y="215" width="18" height="45" rx="5" />
        {(['red', 'yellow', 'green'] as const).map((light, index) => <circle key={light} cx="506" cy={224 + index * 14} r="5" className={signal === light ? `bulb bulb--${light}` : 'bulb bulb--off'} />)}
        {signal === 'unknown' && <text className="unknown-signal" x="506" y="279" textAnchor="middle">?</text>}
      </g>
    })}
    {directions.map(code => {
      const [x, y] = labels[code]
      return <g key={`label-${code}`} className={`map-selector${selected === code ? ' is-selected' : ''}`} transform={`translate(${x} ${y})`}
        role="button" tabIndex={0} aria-pressed={selected === code} aria-label={`Pilih pendekat ${directionNames[code]}`}
        onClick={() => onSelect(code)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(code) } }}>
        <rect x="-68" y="-22" width="136" height="44" rx="6" /><text y="5" textAnchor="middle"><tspan className="direction-code">{code}</tspan><tspan dx="10">{directionNames[code]}</tspan></text>
      </g>
    })}
    {schematic && directions.map(code => <g key={`count-${code}`} className="map-count" transform={`translate(${countLabels[code].join(' ')})`}>
      <rect x="-68" y="-20" width="136" height="40" rx="6" /><text y="6" textAnchor="middle">{vehicles.filter(vehicle => vehicle.origin === code).length} terlacak</text>
    </g>)}
    <g className="map-annotation" transform={`translate(${start+40} ${start+70})`}><text className="map-kicker">{schematic ? 'KENDARAAN DARI VIDEO' : 'GEOMETRI SIMULASI'}</text><text y="22">3 lajur / pendekat</text><text y="44">{schematic ? 'Motor: hingga 3 per baris' : 'Pindah lajur sebelum percabangan'}</text></g>
    <g className="map-annotation" transform={`translate(700 ${end-130})`}><text>Skema tanpa skala.</text><text y="21">Bukan ukuran lapangan.</text></g>
  </svg>
}

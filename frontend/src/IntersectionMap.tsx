import { directions, directionNames, signalNames, type Direction } from './traffic'
import type { AtcsStatus } from './types/AtcsStatus'
import type { TrafficView } from './types/TrafficView'
import mapGeometry from './geometry/map-geometry.json'
import { VehicleLayer } from './VehicleLayer'

interface Props { selected: Direction; onSelect: (direction: Direction) => void; signals: AtcsStatus['signals']; routes: boolean; vehicles?: TrafficView['vehicles']; markerId?: string; vehicleRunId?: string }
const slip = mapGeometry.slip
const slipPath = `M${slip.start.join(' ')} C${slip.control1.join(' ')} ${slip.control2.join(' ')} ${slip.end.join(' ')}`

function LaneArrow({ x, y, turn, sign = false }: { x: number; y: number; turn?: 'left' | 'right'; sign?: boolean }) {
  return <g transform={`translate(${x} ${y})`} className={sign ? 'lane-sign' : 'lane-arrow'}>
    {sign && <circle r="17" />}
    <g fill="none" stroke="white" strokeWidth={sign ? 2 : 3} strokeLinecap="round" strokeLinejoin="round">
      <path d="M0 -11 V11 M-5 6 L0 11 L5 6" />
      {turn && <path transform={turn === 'right' ? 'scale(-1 1)' : undefined} d="M0 -5 Q0 2 7 2 H12 M8 -2 L12 2 L8 6" />}
    </g>
  </g>
}

export function IntersectionMap({ selected, onSelect, signals, routes, vehicles = [], markerId = 'route-arrow', vehicleRunId }: Props) {
  const labels: Record<Direction, [number, number]> = { U: [400, -218], T: [1018, 400], S: [400, 1018], B: [-218, 400] }
  return <svg className="intersection-map" viewBox="-300 -300 1400 1400" role="group" aria-label="Peta interaktif persimpangan empat arah">
    <title>Skema simpang Ibrahim Adjie–Soekarno Hatta</title>
    <desc>Dua lajur masuk dan dua lajur keluar per pendekat. Empat ruas pintas belok kiri terpisah oleh pulau jalan. Lurus dan kanan mengikuti lampu; belok kiri melalui ruas pintas wajib memberi jalan saat bergabung. Pilih Utara, Timur, Selatan, atau Barat untuk melihat rute.</desc>
    <defs><marker id={markerId} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9" fill="none" stroke="#1763a6" strokeWidth="2" /></marker></defs>
    <path className="road" d={mapGeometry.road_outline} />
    {directions.map((code, i) => <g key={`slip-${code}`} transform={`rotate(${i * 90} 400 400)`}>
      <path className="island" data-island={code} d={mapGeometry.island} />
    </g>)}
    {directions.map((code, i) => <g key={`arm-${code}`} transform={`rotate(${i * 90} 400 400)`}>
      {selected === code && <path className="approach-highlight" d="M410 -180 H485 V294 H410 Z" />}
      <path className="lane-divider" d="M350 -180 V298 M450 -180 V298" />
      <rect className="median" x="396" y="-180" width="8" height="471" rx="4" />
      <path className="stop-line" d="M410 297 H486" />
      <g transform="rotate(180 350 169)"><LaneArrow x={330} y={169} /><LaneArrow x={370} y={169} /></g>
      <LaneArrow x={430} y={246} turn="right" /><LaneArrow x={470} y={267} />
      <g role="img" aria-label={`Rambu ${directionNames[code]} lajur dalam: lurus atau kanan`}><LaneArrow x={530} y={20} turn="right" sign /></g>
      <g role="img" aria-label={`Rambu ${directionNames[code]} lajur luar: lurus atau kiri lewat ruas pintas`}><LaneArrow x={574} y={20} turn="left" sign /></g>
      <path className="slip-route" data-slip-road={code} d={slipPath} markerEnd={`url(#${markerId})`} />
      <g className="yield-sign" role="img" aria-label={`Beri jalan pada penggabungan ruas pintas ${directionNames[code]}`}><path d={mapGeometry.yield_sign} /></g>
    </g>)}
    {routes && <g transform={`rotate(${directions.indexOf(selected) * 90} 400 400)`} className="selected-routes" aria-label={`Rute lurus dan kanan dari ${directionNames[selected]}, mengikuti lampu`}>
      <path d="M470 305 V940" markerEnd={`url(#${markerId})`} /><path d="M430 305 V940" markerEnd={`url(#${markerId})`} />
      <path d="M430 305 V338 Q430 430 329 430 H-140" markerEnd={`url(#${markerId})`} />
    </g>}
    {directions.map((code, i) => {
      const signal = signals?.[code] ?? 'unknown'
      return <g key={`signal-${code}`} transform={`rotate(${i * 90} 400 400)`} role="img" aria-label={`Lampu ${directionNames[code]}: ${signalNames[signal]}`} data-signal={signal}>
        <rect className="signal-housing" x="498" y="260" width="18" height="45" rx="5" />
        {(['red', 'yellow', 'green'] as const).map((light, index) => <circle key={light} cx="507" cy={269 + index * 14} r="5" className={signal === light ? `bulb bulb--${light}` : 'bulb bulb--off'} />)}
        {signal === 'unknown' && <text className="unknown-signal" x="507" y="323" textAnchor="middle">?</text>}
      </g>
    })}
    <VehicleLayer key={vehicleRunId || markerId} vehicles={vehicles} />
    {directions.map(code => {
      const [x, y] = labels[code]
      return <g key={`label-${code}`} className={`map-selector${selected === code ? ' is-selected' : ''}`} transform={`translate(${x} ${y})`}
        role="button" tabIndex={0} aria-pressed={selected === code} aria-label={`Pilih pendekat ${directionNames[code]}`}
        onClick={() => onSelect(code)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(code) } }}>
        <rect x="-68" y="-22" width="136" height="44" rx="6" /><text y="5" textAnchor="middle"><tspan className="direction-code">{code}</tspan><tspan dx="10">{directionNames[code]}</tspan></text>
      </g>
    })}
    <g className="map-annotation" transform="translate(-180 -140)"><text className="map-kicker">GEOMETRI SIMULASI</text><text y="22">4 pendekat / 4 ruas pintas</text></g>
    <g className="map-annotation" transform="translate(650 900)"><text>Skema tanpa skala.</text><text y="21">Bukan ukuran lapangan.</text></g>
  </svg>
}

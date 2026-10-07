import { directions, directionNames, signalNames, type Direction } from './traffic'
import type { AtcsStatus } from './types/AtcsStatus'
import type { TrafficView } from './types/TrafficView'
import { JunctionRoad } from './JunctionRoad'
import { VehicleLayer } from './VehicleLayer'
import geometry from './geometry/map-geometry.json'

interface Props { selected: Direction; onSelect: (direction: Direction) => void; signals: AtcsStatus['signals']; routes: boolean; vehicles?: TrafficView['vehicles']; markerId?: string; vehicleRunId?: string; schematic?: boolean }
export function IntersectionMap({ selected, onSelect, signals, routes, vehicles = [], markerId = 'route-arrow', vehicleRunId, schematic = false }: Props) {
  const labels: Record<Direction, [number, number]> = { U: [400, -422], T: [1222, 400], S: [400, 1222], B: [-422, 400] }
  const countLabels: Record<Direction, [number, number]> = { U: [610, -355], T: [1155, 610], S: [190, 1155], B: [-355, 190] }
  return <svg className="intersection-map" viewBox="-510 -510 1820 1820" role="group" aria-label="Peta interaktif persimpangan empat arah">
    <title>Skema simpang Ibrahim Adjie–Soekarno Hatta</title>
    <desc>{schematic ? 'Satu ikon per kendaraan terlacak, disusun per lajur pada pendekat kameranya. Slot bukan posisi atau lintasan persis di video. ' : 'Kendaraan simulasi berpindah lajur bertahap di bagian hulu. '}Tiga lajur masuk dan tiga lajur keluar per pendekat. Kiri untuk ruas pintas, tengah untuk lurus, kanan untuk belok kanan. Lurus dan kanan mengikuti lampu. Pilih pendekat untuk melihat rute.</desc>
    <defs><marker id={markerId} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9" fill="none" stroke="#1763a6" strokeWidth="2" /></marker></defs>
    <JunctionRoad selected={selected} markerId={markerId} />
    {routes && <g transform={`rotate(${directions.indexOf(selected) * 90} ${geometry.center} ${geometry.center})`} className="selected-routes" aria-label={`Rute lurus dan kanan dari ${directionNames[selected]}, mengikuti lampu`}>
      <path d={`M${geometry.lane_centers.middle} ${geometry.stop_line+8} V${geometry.end-60}`} markerEnd={`url(#${markerId})`} />
      <path d={`M${geometry.lane_centers.inner} ${geometry.stop_line+8} C${geometry.lane_centers.inner} ${geometry.center} ${geometry.center} ${geometry.lane_centers.inner} ${geometry.stop_line} ${geometry.lane_centers.inner} H${geometry.start+60}`} markerEnd={`url(#${markerId})`} />
    </g>}
    <VehicleLayer key={`${vehicleRunId || markerId}:${schematic ? 'video' : 'simulation'}`} vehicles={vehicles} schematic={schematic} />
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
    <g className="map-annotation" transform="translate(-360 -330)"><text className="map-kicker">{schematic ? 'KENDARAAN DARI VIDEO' : 'GEOMETRI SIMULASI'}</text><text y="22">3 lajur / pendekat</text><text y="44">{schematic ? 'Ikon disusun per lajur' : 'Pindah lajur sebelum percabangan'}</text></g>
    <g className="map-annotation" transform="translate(700 1070)"><text>Skema tanpa skala.</text><text y="21">Bukan ukuran lapangan.</text></g>
  </svg>
}

import { directions, directionNames, type Direction } from './traffic'
import geometry from './geometry/map-geometry.json'

const { slip, lane_centers: lanes, start, stop_line: stop } = geometry
export const slipPath = `M${slip.start.join(' ')} C${slip.control1.join(' ')} ${slip.control2.join(' ')} ${slip.end.join(' ')}`

function LaneArrow({ x, y, turn, sign = false }: { x: number; y: number; turn?: 'left' | 'right'; sign?: boolean }) {
  return <g transform={`translate(${x} ${y})`} className={sign ? 'lane-sign' : 'lane-arrow'}>
    {sign && <circle r="17" />}
    <g fill="none" stroke="white" strokeWidth={sign ? 2 : 3} strokeLinecap="round" strokeLinejoin="round">
      {turn ? <path transform={turn === 'right' ? 'scale(-1 1)' : undefined} d="M0 -11 V-3 Q0 3 7 3 H12 M8 -1 L12 3 L8 7" /> : <path d="M0 -11 V11 M-5 6 L0 11 L5 6" />}
    </g>
  </g>
}

/** One road drawing for the operator map and the public login illustration. */
export function JunctionRoad({ selected, markerId, signs = true }: { selected: Direction; markerId: string; signs?: boolean }) {
  const dividers = [
    ...geometry.outgoing_centers.slice(1).map((x, i) => `M${(x+geometry.outgoing_centers[i])/2} ${start+20} V${stop}`),
    `M${(lanes.inner+lanes.middle)/2} ${start+20} V${geometry.lane_change.end}`,
    `M${(lanes.middle+lanes.outer)/2} ${start+20} V${geometry.lane_change.end}`,
  ].join(' ')
  return <>
    <path className="road" d={geometry.road_outline} />
    {directions.map((code, i) => <g key={code} transform={`rotate(${i*90} ${geometry.center} ${geometry.center})`}>
      <path className="island" data-island={code} d={geometry.island} />
      {selected === code && <path className="approach-highlight" d="M410 -380 H528 V98 H488 V253 H410 Z" />}
      <path className="lane-divider" d={dividers} />
      <path className="lane-guide" d={`M450 ${geometry.lane_change.end} V${stop} M490 ${geometry.lane_change.end} V${slip.start[1]}`} />
      <rect className="median" x={geometry.center-4} y={start+20} width="8" height={stop-start-27} rx="4" />
      <path className="stop-line" d={`M410 ${stop} H488`} />
      {geometry.outgoing_centers.map(x => <g key={x} transform={`rotate(180 ${x} 190)`}><LaneArrow x={x} y={190} /></g>)}
      <LaneArrow x={lanes.inner} y={218} turn="right" /><LaneArrow x={lanes.middle} y={218} /><LaneArrow x={lanes.outer} y={65} turn="left" />
      {signs && <>
        <g data-incoming-lane="inner" role="img" aria-label={`Rambu ${directionNames[code]} lajur kanan: belok kanan`}><LaneArrow x={565} y={-260} turn="right" sign /></g>
        <g data-incoming-lane="middle" role="img" aria-label={`Rambu ${directionNames[code]} lajur tengah: lurus`}><LaneArrow x={609} y={-260} sign /></g>
        <g data-incoming-lane="outer" role="img" aria-label={`Rambu ${directionNames[code]} lajur kiri: ruas pintas kiri`}><LaneArrow x={653} y={-260} turn="left" sign /></g>
      </>}
      <path className="slip-route" data-slip-road={code} d={slipPath} markerEnd={`url(#${markerId})`} />
      <g className="yield-sign" role={signs ? 'img' : undefined} aria-label={signs ? `Beri jalan pada penggabungan ruas pintas ${directionNames[code]}` : undefined}><path d={geometry.yield_sign} /></g>
    </g>)}
  </>
}

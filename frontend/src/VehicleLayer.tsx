import { useLayoutEffect, useRef } from 'react'
import { directionNames } from './traffic'
import type { TrafficView } from './types/TrafficView'

interface Pose { x: number; y: number; heading: number }
const poseOf = ({ x, y, heading }: Pose): Pose => ({ x, y, heading })
export function interpolatePose(from: Pose, to: Pose, progress: number): Pose {
  const turn = (((to.heading - from.heading) % 360 + 540) % 360) - 180
  return { x: from.x + (to.x-from.x)*progress, y: from.y + (to.y-from.y)*progress, heading: from.heading+turn*progress }
}
const transform = (pose: Pose) => `translate(${pose.x} ${pose.y})`
const laneOrder = ['outer', 'middle', 'inner']
const laneNames = { outer: 'kiri', middle: 'tengah', inner: 'kanan' }
const stopReasons = { following: 'mengikuti antrean', yielding: 'memberi jalan', signal: 'menunggu lampu', exit_blocked: 'keluaran penuh', conflict: 'menunggu area konflik', safety_gap: 'menjaga jarak aman', stationary: 'kendaraan diam' }

function vehicleTitle(vehicle: TrafficView['vehicles'][number], schematic: boolean) {
  const kind = vehicle.kind === 'ambulance' ? 'Ambulans' : vehicle.kind === 'fire_engine' ? 'Pemadam' : schematic ? 'Kendaraan' : 'Mobil'
  const parts = [`${kind}${schematic ? ' terlacak' : ` #${vehicle.id}`}`, `dari ${directionNames[vehicle.origin]}`, `lajur ${laneNames[vehicle.lane]}`]
  if (vehicle.changing_to) parts.push(`berpindah ke ${laneNames[vehicle.changing_to]}`)
  if (vehicle.stopped) parts.push(vehicle.stop_reason ? stopReasons[vehicle.stop_reason] : 'berhenti')
  if (schematic && vehicle.served) parts.push('sudah melewati garis henti di video')
  return parts.join(' · ')
}

/** Fit complete glyphs (including their stroke) into the shared lane slots. */
export function schematicVehicleScales(vehicles: TrafficView['vehicles']) {
  const lanes = new Map<string, TrafficView['vehicles']>()
  for (const vehicle of vehicles) {
    const key = `${vehicle.origin}:${vehicle.lane}`
    const group = lanes.get(key) ?? []
    group.push(vehicle)
    lanes.set(key, group)
  }
  const scales = new Map<number, number>()
  for (const group of lanes.values()) {
    const vertical = group[0].origin === 'U' || group[0].origin === 'S'
    const ordered = [...group].sort((a, b) => vertical ? a.y-b.y : a.x-b.x)
    let gap = Infinity
    for (let i = 1; i < ordered.length; i++) {
      gap = Math.min(gap, Math.hypot(ordered[i].x-ordered[i-1].x, ordered[i].y-ordered[i-1].y))
    }
    const scale = Math.min(1, gap/36)
    for (const vehicle of group) scales.set(vehicle.id, scale)
  }
  return scales
}

/** Interpolate only SVG user coordinates. Browser zoom changes the common SVG
 * viewport, never a separate CSS-pixel translation or compositor transition. */
export function VehicleLayer({ vehicles, schematic = false }: { vehicles: TrafficView['vehicles']; schematic?: boolean }) {
  const nodes = useRef(new Map<number, SVGGElement>())
  const drawn = useRef(new Map<number, Pose>())
  const scales = schematic ? schematicVehicleScales(vehicles) : null
  useLayoutEffect(() => {
    let frame = 0
    const start = performance.now()
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    const movements = vehicles.map(vehicle => {
      const to = poseOf(vehicle)
      const previous = drawn.current.get(vehicle.id) || to
      // Fresh arrivals, reconnections and large jumps snap to the verified sample.
      // CCTV slots show presence, not a guessed trajectory through the junction.
      // Snap their layout atomically: arrivals and lane changes cannot cross a
      // neighbouring body during the animation. Synthetic routes still animate.
      const from = schematic || reduceMotion || document.hidden || Math.hypot(to.x-previous.x, to.y-previous.y) > 100 ? to : previous
      return { id: vehicle.id, from, to }
    })
    drawn.current = new Map(movements.map(item => [item.id, item.from]))
    const moving = movements.some(({ from, to }) => from.x !== to.x || from.y !== to.y || from.heading !== to.heading)
    const draw = (at: number) => {
      const progress = moving ? Math.min(1, Math.max(0, (at-start)/230)) : 1
      for (const { id, from, to } of movements) {
        const pose = interpolatePose(from, to, progress)
        const node = nodes.current.get(id)
        node?.setAttribute('transform', transform(pose))
        node?.firstElementChild?.setAttribute('transform', `rotate(${pose.heading})`)
        drawn.current.set(id, pose)
      }
      if (progress < 1) frame = requestAnimationFrame(draw)
    }
    draw(start)
    return () => cancelAnimationFrame(frame)
  }, [vehicles, schematic])

  return <g className="vehicle-layer" aria-label={`${vehicles.length} kendaraan pada peta`}>
    {vehicles.map(vehicle => <g key={vehicle.id} className="vehicle-position" transform={transform(vehicle)}
      ref={node => { if (node) nodes.current.set(vehicle.id, node); else nodes.current.delete(vehicle.id) }}>
      <g transform={`rotate(${vehicle.heading})`} className={`map-vehicle map-vehicle--${vehicle.kind}`} data-vehicle-id={vehicle.id} data-origin={vehicle.origin} data-lane={vehicle.lane} data-changing-to={vehicle.changing_to ?? undefined} data-stop-reason={vehicle.stop_reason ?? undefined}>
        <title>{vehicleTitle(vehicle, schematic)}</title>
        <g className="vehicle-body" transform={`scale(${scales?.get(vehicle.id) ?? 1})`} data-scale={scales?.get(vehicle.id) ?? 1}>
        <rect x="-13" y="-9" width="26" height="18" rx="4" /><path className="vehicle-window" d="M5 -6 H9 V6 H5Z" />
        {vehicle.kind === 'ambulance' && <path className="ambulance-cross" d="M-7 0 H1 M-3 -4 V4" />}
        {vehicle.kind === 'fire_engine' && <path className="fire-ladder" d="M-9 -4 H2 V4 H-9Z M-5 -4 V4 M-1 -4 V4" />}
        {vehicle.changing_to && <path className="vehicle-indicator" d={laneOrder.indexOf(vehicle.changing_to) < laneOrder.indexOf(vehicle.lane) ? 'M5 -10 H11' : 'M5 10 H11'} />}
        </g>
      </g>{vehicle.kind !== 'car' && !schematic && <text className="evp-number" x="0" y="-17" textAnchor="middle">#{vehicle.id}</text>}
    </g>)}
  </g>
}

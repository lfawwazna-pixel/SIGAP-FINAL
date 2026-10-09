import { vehicleDimensions, vehicleKindNames, type VehicleKind } from './vehicleAppearance'
export { vehicleKindNames } from './vehicleAppearance'
const kinds: VehicleKind[] = ['motorcycle', 'car', 'bus', 'truck', 'ambulance', 'fire_engine']

/** Body proportions match the lane packing dimensions; front faces +x. */
export function VehicleGlyph({ kind }: { kind: VehicleKind }) {
  const { length, width } = vehicleDimensions[kind]
  const front = length / 2
  return <g className={`vehicle-glyph vehicle-glyph--${kind}`}>
    {kind === 'motorcycle' ? <>
      <path className="motorcycle-wheel" d="M-9.5 0 H-6 M6 0 H9.5" />
      <rect x="-7" y="-3.5" width="14" height="7" rx="3" />
      <path className="motorcycle-handlebar" d="M5 -4.25 V4.25" />
      <circle className="motorcycle-rider" cx="-1" cy="0" r="3" />
    </> : kind === 'truck' ? <>
      <rect className="truck-cargo" x="-26" y="-10" width="39" height="20" rx="1" />
      <rect className="truck-cab" x="13" y="-9" width="13" height="18" rx="2" />
      <path className="vehicle-window" d="M20 -6 H23 V6 H20Z" />
      <path className="cargo-lines" d="M-20 -7 V7 M-12 -7 V7 M-4 -7 V7 M4 -7 V7" />
    </> : <>
      <rect x={-front} y={-width/2} width={length} height={width} rx={kind === 'bus' || kind === 'fire_engine' ? 2 : 4} />
      <path className="vehicle-window" d={`M${front-8} -6 H${front-4} V6 H${front-8}Z`} />
      {kind === 'car' && <path className="vehicle-window" d="M-10 -5 H-7 V5 H-10Z" />}
      {kind === 'bus' && <>
        <path className="bus-windows" d="M-21 -7 H-15 M-11 -7 H-5 M-1 -7 H5 M9 -7 H15 M-21 7 H-15 M-11 7 H-5 M-1 7 H5 M9 7 H15" />
        <rect className="bus-roof" x="-13" y="-3" width="22" height="6" rx="1" />
      </>}
      {kind === 'ambulance' && <path className="ambulance-cross" d="M-7 0 H1 M-3 -4 V4" />}
      {kind === 'fire_engine' && <path className="fire-ladder" d="M-9 -4 H2 V4 H-9Z M-5 -4 V4 M-1 -4 V4" />}
      {(kind === 'ambulance' || kind === 'fire_engine') && <path className="emergency-lightbar" d={`M${front-10} -6 V6`} />}
    </>}
  </g>
}

export function VehicleLegend({ label = 'Kelas dari YOLO' }: { label?: string }) {
  return <div className="vehicle-kind-legend" aria-label="Jenis kendaraan pada peta">
    <span className="vehicle-kind-label">{label}</span>
    {kinds.map(kind => {
      const length = vehicleDimensions[kind].length + 10
      return <span key={kind}><svg viewBox={`${-length/2} -14 ${length} 28`} style={{ width: length }} aria-hidden="true" focusable="false"><VehicleGlyph kind={kind} /></svg>{vehicleKindNames[kind]}</span>
    })}
  </div>
}

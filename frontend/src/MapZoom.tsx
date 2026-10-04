export const mapZoomLevels = Array.from({ length: 16 }, (_, index) => (50 + index * 10) / 100)

export function MapZoom({ value, onChange, label }: { value: number; onChange: (value: number) => void; label: string }) {
  return <label>Zoom<select aria-label={label} value={value} onChange={event => onChange(Number(event.target.value))}>
    {mapZoomLevels.map(level => <option key={level} value={level}>{Math.round(level * 100)}%</option>)}
  </select></label>
}

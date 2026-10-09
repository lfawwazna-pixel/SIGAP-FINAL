import { useState } from 'react'
import { IntersectionMap } from './IntersectionMap'
import { VehicleLegend } from './VehicleGlyph'
import { Readiness } from './Readiness'
import { coherentStatus, directions, directionNames, eventNames, localTime, modeNames, phaseNames, signalNames, supportedGeometry, type Direction } from './traffic'
import { useJournal, useMonitor, useReadiness, type Connection } from './useMonitor'
import type { SessionView } from './types/SessionView'
import { SimulationWorkspace, TrafficMetrics } from './SimulationWorkspace'
import { useTraffic } from './useTraffic'
import { useControl } from './useControl'
import { ControlPanel } from './ControlPanel'
import { MapZoom } from './MapZoom'
import { SigapLogo } from './SigapLogo'
import { AdaptivePanel, useAdaptive } from './AdaptivePanel'
import { VideoPanel } from './VideoPanel'
import { ModelQualityPanel } from './ModelQualityPanel'
import { EmergencyPanel } from './EmergencyPanel'
import { freshVideoObservation, videoMapVehicles, useVideoMapData } from './videoMap'

const connectionLabels: Record<Connection, string> = {
  loading: 'Menghubungkan', live: 'Terhubung ke ATCS', unavailable: 'Status tidak tersedia', stale: 'Data tidak mutakhir', paused: 'Pemantauan dijeda',
}

export function Monitor({ session, onLogout, signingOut, logoutError }: {
  session: SessionView; onLogout: () => void; signingOut: boolean; logoutError: string | null
}) {
  const [revision, setRevision] = useState(0)
  const [workspace, setWorkspace] = useState<'atcs' | 'sigap' | 'simulation'>('atcs')
  const [zoom, setZoom] = useState(1)
  const [selected, setSelected] = useState<Direction>('U')
  const [routes, setRoutes] = useState(true)
  const [eventFilter, setEventFilter] = useState<'all' | 'phase' | 'incident'>('all')
  const [historyVisible, setHistoryVisible] = useState(true)
  const { snapshot, checking } = useReadiness(revision)
  const config = snapshot.configuration.state === 'ready' && supportedGeometry(snapshot.configuration.data) ? snapshot.configuration.data : null
  const monitor = useMonitor(config?.intersection_id, revision)
  const { journal, state: journalState } = useJournal(config?.intersection_id, monitor.runId, revision)
  const data = monitor.status.state === 'ready' ? monitor.status.data : null
  const verified = monitor.connection === 'live' && data && config && coherentStatus(data, config.intersection_id) ? data : null
  const connection = config ? monitor.connection : snapshot.configuration.state === 'loading' ? 'loading' : 'unavailable'
  const approach = config?.approaches.find(a => a.code === selected)
  const mayControl = session.operator.permissions.includes('control:operate')
  const adaptive = useAdaptive(Boolean(config))
  const control = useControl(config?.intersection_id, session.csrf_token, mayControl, adaptive.data?.enabled === true)
  const videoData = useVideoMapData(adaptive.data, config?.intersection_id)
  const videoSource = control.status?.source === 'cctv' || Boolean(videoData)
    || adaptive.data?.source === 'recording' || adaptive.data?.source === 'cctv'
  // Only the verified phase controller changes the ATCS map's source. Keep
  // tracking through release clearance; fixed_time confirms release completion.
  const videoControl = Boolean(videoSource && verified
    && (verified.controller === 'SIGAP' || verified.mode === 'fallback'))
  const videoMap = videoControl || (workspace === 'sigap' && adaptive.data?.source !== 'synthetic')
  // Fetch synthetic poses only while they are actually displayed. The independent
  // ATCS status feed keeps checking the real controller in every workspace.
  const needsTraffic = workspace !== 'simulation' && !videoMap
    && (workspace === 'atcs' || control.status?.source === 'integration_test')
  const traffic = useTraffic('atcs_synthetic', config?.intersection_id, needsTraffic, session.csrf_token)
  const trafficFrame = verified && traffic.data?.run_id === verified.run_id ? traffic.data : null
  // Lamps and vehicles share one server snapshot whenever the traffic feed is available.
  const live = verified && trafficFrame && verified.controller === 'ATCS' ? { ...verified, signals: trafficFrame.signals, phase: trafficFrame.phase,
    active_approach: trafficFrame.active_approach, remaining_seconds: trafficFrame.remaining_seconds,
    conflict_area: { ...verified.conflict_area!, state: trafficFrame.conflict } } : verified
  const signals = live?.signals ?? null
  const vehicles = videoMap ? videoMapVehicles(videoData, config?.intersection_id)
    : (workspace === 'atcs' || control.status?.source === 'integration_test') && live && traffic.data?.run_id === live.run_id ? traffic.data.vehicles : []
  const selectedSignal = signals?.[selected] ?? 'unknown'
  const filtered = [...journal.events].reverse().filter(event => eventFilter === 'all'
    || (eventFilter === 'phase' ? event.event_type === 'phase_changed' : ['fault', 'recovered', 'clearance_held', 'service_stopped', 'control_changed'].includes(event.event_type)))
  const visibleEvents = filtered.slice(0, 20)
  const phaseText = live?.phase ? phaseNames[live.phase] : 'Belum diketahui'

  return <>
    <a className="skip-link" href="#content">Lewati ke isi</a>
    <header className="app-header">
      <a className="brand" href="#content" aria-label="SIGAP — monitor persimpangan"><SigapLogo /></a>
      <span className="header-context">Ruang kendali persimpangan</span>
      <nav aria-label="Navigasi monitor"><a href="/analytics">Analitik &amp; dampak</a><a href="/history">Riwayat lengkap</a><a href="#services" onClick={() => { const details = document.querySelector<HTMLDetailsElement>('#services'); if (details) details.open = true }}>Layanan</a></nav>
      <span className="environment-tag">Prototipe lokal</span>
      <details className="operator-menu">
        <summary><span className="operator-avatar" aria-hidden="true">{session.operator.display_name.slice(0, 1).toUpperCase()}</span><span>{session.operator.display_name}<small>Operator pemantauan</small></span><span aria-hidden="true">⌄</span></summary>
        <div className="operator-popover"><strong>{session.operator.username}</strong><p>Akses pemantauan simpang</p><p>Sesi sampai {localTime(session.expires_at)} WIB</p><button onClick={onLogout} disabled={signingOut}>{signingOut ? 'Mengakhiri sesi…' : 'Keluar dari SIGAP'}</button></div>
      </details>
    </header>
    <main id="content">
      {logoutError && <p className="connection-note" role="alert">{logoutError}</p>}
      <div className="page-heading">
        <div><p className="eyebrow">PEMANTAUAN / KIRCON, BANDUNG</p><h1>Monitor persimpangan</h1>
          <p className="site-name">{config?.name ?? (snapshot.configuration.state === 'loading' ? 'Memuat identitas persimpangan…' : 'Identitas persimpangan tidak tersedia')}</p></div>
        <div className="connection-tools">
          <span className={`connection connection--${connection}`} role="status"><span aria-hidden="true" />{connectionLabels[connection]}</span>
          <button className="refresh-button" onClick={() => setRevision(value => value + 1)} disabled={checking}><span aria-hidden="true">↻</span> {checking ? 'Memeriksa…' : 'Periksa ulang'}</button>
        </div>
      </div>
      <div className="workspace-switch" role="group" aria-label="Mode ruang kerja">
        <button aria-pressed={workspace === 'atcs'} onClick={() => setWorkspace('atcs')}><strong>ATCS</strong><span>Fase bersama · peta kendaraan</span></button>
        <button aria-pressed={workspace === 'sigap'} onClick={() => setWorkspace('sigap')}><strong>SIGAP</strong><span>Adaptif, sumber &amp; kendali</span></button>
        <button aria-pressed={workspace === 'simulation'} onClick={() => setWorkspace('simulation')}><strong>Simulasi</strong><span>Percobaan arus &amp; EVP</span></button>
      </div>
      <div className="background-atcs" role="status"><span className="signal-dot" /><strong>{live?.mode === 'fallback' ? 'Transisi aman · kembali ke ATCS' : live?.controller === 'SIGAP' ? 'SIGAP mengambil alih kendali · ATCS mengikuti fase adaptif' : control.status?.state === 'activating' ? 'SIGAP menunggu transisi aman' : control.status?.state === 'returning_atcs' ? 'Fallback · kembali ke ATCS' : 'ATCS mengendalikan · waktu tetap'}</strong> · {live?.phase ? `${phaseNames[live.phase]} ${live.active_approach ?? ''} · ${live.remaining_seconds != null ? `${Math.ceil(live.remaining_seconds)} dtk` : 'menunggu konflik'}` : 'status belum terverifikasi'}</div>
      {control.status?.fallback_code && <p className="connection-note" role="status"><strong>{control.status.state === 'returning_atcs' ? 'Transisi ke ATCS.' : 'Catatan pengendali.'}</strong> {control.status.reason}</p>}
      {workspace === 'sigap' && <><ControlPanel control={control} mayControl={mayControl} allowSynthetic={adaptive.data?.source === 'synthetic' && adaptive.data.enabled} autoResume={adaptive.data?.auto_resume} /><AdaptivePanel feed={adaptive} csrf={session.csrf_token} mayControl={mayControl} /></>}
      {workspace !== 'simulation' && live?.controller === 'SIGAP' && live.mode === 'adaptive'
        && control.status?.atcs_run_id === live.run_id
        && <EmergencyPanel emergency={adaptive.data?.emergency} control={control.status} />}
      <VideoPanel workspace={workspace} csrf={session.csrf_token} mayControl={mayControl} />
      <SimulationWorkspace intersection={config?.intersection_id} csrf={session.csrf_token} active={workspace === 'simulation'} />
      <div hidden={workspace === 'simulation'}>
      <div className="simulation-strip"><span className="simulation-mark" aria-hidden="true">{videoMap ? 'V' : 'A'}</span><span><strong>{live?.mode ? `${live.controller} · ${modeNames[live.mode]}` : 'Pengendali ATCS'}</strong> · {videoMap ? 'Satu ikon per kendaraan dalam zona, sesuai pendekat kamera. Ikon disusun per lajur; posisi dan geraknya tidak sama persis dengan video.' : 'Kendaraan ilustrasi acak bergerak mengikuti lampu ATCS.'} Belum terhubung ke lampu lapangan.</span><span className="read-only">{videoMap ? (videoControl ? 'Tracking aktif' : 'Pratinjau tracking') : '1× · Terus berjalan'}</span></div>
      {connection !== 'live' && <div className={`connection-note${connection === 'loading' ? ' is-loading' : ''}`}>
        <strong>{connectionLabels[connection]}.</strong> {connection === 'loading' ? 'Menunggu kondisi pengendali.'
          : connection === 'paused' ? 'Data lampu akan diperiksa kembali saat halaman aktif.'
          : !config ? 'Konfigurasi simpang belum tersedia atau tidak cocok dengan geometri peta.'
          : data?.reason ?? 'Lampu dan sisa waktu disembunyikan sampai data baru terverifikasi. Kegagalan koneksi belum membuktikan proses ATCS berhenti.'}
      </div>}
      <div className="operator-workspace">
        <section className="map-panel" aria-labelledby="map-title">
          <div className="section-toolbar"><div><h2 id="map-title">Situasi simpang</h2><p>Pilih pendekat untuk memeriksa arah pergerakan.</p></div>
            <div className="map-tools"><MapZoom label="Zoom peta ATCS" value={zoom} onChange={setZoom} /><button className="route-toggle" aria-pressed={routes} onClick={() => setRoutes(value => !value)}><span aria-hidden="true">{routes ? '✓' : '+'}</span> Rute terpilih</button></div></div>
          <div className="map-canvas traffic-map-scroll">
            {config ? <div style={{ width: `${zoom*100}%` }}><IntersectionMap selected={selected} onSelect={setSelected} signals={signals} routes={routes} vehicles={vehicles} vehicleRunId={live?.run_id ?? undefined} schematic={videoMap} /></div>
              : <div className="map-empty"><span aria-hidden="true">＋</span><h3>{snapshot.configuration.state === 'loading' ? 'Menyiapkan peta simpang' : 'Peta belum dapat ditampilkan'}</h3><p>Geometri dan arah dibaca dari konfigurasi simpang.</p></div>}
          </div>
          <div className="map-legend"><span><i className="legend-route" />Ruas pintas kiri</span><span><i className="legend-dashed" />Rute pendekat terpilih</span><span><i className="legend-yield" />Beri jalan saat bergabung</span></div>
          {videoMap && <VehicleLegend />}
          <p className="map-rule">Ruas pintas kiri melewati sisi luar pulau jalan. <strong>Arus lurus dan kanan tetap mengikuti lampu.</strong></p>
          {videoMap ? <><p className="map-rule" role="status">{vehicles.length} kendaraan dalam zona ditampilkan di peta. Jumlah per pendekat mengikuti tracking dalam zona tersimpan. Motor disusun hingga tiga per baris; bus dan truk sepanjang dua mobil. Ruas memanjang bila diperlukan; geser peta atau gunakan zoom untuk memeriksa. Kebutuhan lampu hanya menghitung area terkalibrasi.</p>{videoData?.measurements ? <div className="table-scroll"><table className="event-table video-map-table" aria-label="Jumlah kendaraan video dan peta"><thead><tr><th>Pendekat</th><th>Dalam zona / di peta</th><th>Untuk lampu</th><th>Antrean</th><th>Tunggu terlama</th></tr></thead><tbody>{directions.map(d => { const v = videoData.measurements!.approaches[d]; const usable = v.usable && freshVideoObservation(v.observed_at); return <tr key={d}><th>{directionNames[d]}</th><td>{vehicles.filter(vehicle => vehicle.origin === d).length}</td><td>{usable ? v.controlled_count : '—'}</td><td>{usable ? v.queue_count : '—'}</td><td>{usable ? `${v.oldest_wait_seconds.toFixed(1)} dtk` : '—'}</td></tr> })}</tbody></table></div> : <p className="map-rule">Menunggu hasil tracking mutakhir. Video dan kalibrasi dapat diperiksa di panel CCTV.</p>}</> : live && traffic.data?.run_id === live.run_id ? <TrafficMetrics data={traffic.data} /> : <p className="map-rule">Posisi kendaraan belum tersedia atau tidak mutakhir.</p>}
        </section>
        <aside className="operations-panel" aria-label="Panel operasional">
          <div className="controller-heading"><span className="eyebrow">PENGENDALI AKTIF</span><div><strong>{live?.controller ?? '—'}</strong><span>{live?.mode ? modeNames[live.mode] : 'Belum terverifikasi'}</span></div></div>
          <section className="phase-block" aria-labelledby="phase-title">
            <div className="phase-heading"><h2 id="phase-title">Fase saat ini</h2><span className={`phase-tag phase-tag--${live?.phase ?? 'unknown'}`}>{phaseText}</span></div>
            <p className="active-approach">{live?.active_approach ? `Dari ${directionNames[live.active_approach]}` : live?.phase === 'all_red' ? 'Jeda aman antarfase' : 'Menunggu status ATCS'}</p>
            <div className="countdown" aria-label="Sisa waktu fase"><strong data-testid="countdown">{live?.remaining_seconds != null ? Math.ceil(live.remaining_seconds).toString().padStart(2, '0') : '—'}</strong><span>detik<br />tersisa</span></div>
            <p className="phase-description">{live?.clearance_state === 'waiting_conflict' ? 'Menunggu area konflik bebas. Durasi semua merah diperpanjang.' : live?.clearance_state === 'waiting_command' ? 'Semua merah: menunggu keputusan SIGAP. ATCS memantau batas waktu.' : live?.phase === 'all_red' ? 'Seluruh pendekat berhenti selama clearance minimum.' : live?.reason ?? 'Waktu hanya ditampilkan saat data pengendali tersedia.'}</p>
            <div className="phase-sequence" aria-label={live?.controller === 'SIGAP' ? 'Pendekat kendali adaptif' : 'Urutan pendekat waktu tetap'}>{(config?.fixed_time.sequence ?? directions).map(code => <div key={code} className={live?.active_approach === code ? 'is-active' : ''}><span>{code}</span><small>{live?.controller === 'SIGAP' ? 'Adaptif' : config ? `${config.fixed_time.green_seconds[code]} dtk` : '—'}</small></div>)}</div>
            <p className="cycle-note">{live?.controller === 'SIGAP' ? 'Durasi mengikuti keputusan SIGAP; sisa waktu dibaca dari pengendali ATCS.' : config ? `Siklus nominal ${config.fixed_time.nominal_cycle_seconds} detik · kuning ${config.fixed_time.yellow_seconds} detik` : 'Baseline belum tersedia'}</p>
          </section>
          <section className="approach-panel" aria-labelledby="approach-title">
            <div className="phase-heading"><h2 id="approach-title">Pendekat</h2><span className="small-muted">Klik untuk detail</span></div>
            <div className="approach-tabs" role="group" aria-label="Pilih arah pendekat">{directions.map(code => <button key={code} aria-label={`Detail ${directionNames[code]}`} aria-pressed={selected === code} className={selected === code ? 'is-selected' : ''} onClick={() => setSelected(code)}><span>{code}</span><i className={`signal-dot signal-dot--${signals?.[code] ?? 'unknown'}`} /><span className="sr-only">{signalNames[signals?.[code] ?? 'unknown']}</span></button>)}</div>
            <div className="selected-approach"><h3>{directionNames[selected]}</h3><span className={`signal-label signal-label--${selectedSignal}`}>{signalNames[selectedSignal]}</span></div>
            <p className="approach-road">{approach?.road ?? 'Identitas jalan belum tersedia'}</p>
            <dl className="lane-details"><div><dt>Lajur kiri</dt><dd>{approach ? `Ruas pintas ke ${directionNames[approach.outer.left]}` : '—'}</dd></div><div><dt>Lajur tengah</dt><dd>{approach ? `Lurus ke ${directionNames[approach.middle.straight]}` : '—'}</dd></div><div><dt>Lajur kanan</dt><dd>{approach ? `Belok kanan ke ${directionNames[approach.inner.right]}` : '—'}</dd></div></dl>
            <p className="small-muted">Mobil memilih lajur di bagian hulu. Menjelang percabangan, ikuti arah lajur; ruas pintas kiri melewati antrean lampu.</p>
            <p className="yield-note"><span aria-hidden="true">▽</span> Kiri lewat ruas pintas; beri jalan saat bergabung.</p>
          </section>
          <div className="telemetry-details"><div><span>Area konflik</span><strong>{live?.conflict_area?.source === 'assumed_clear' ? 'Diasumsikan kosong' : live?.conflict_area ? ({ clear: 'Kosong', occupied: 'Terisi', unknown: 'Tidak diketahui' }[live.conflict_area.state]) : 'Belum diketahui'}</strong></div><div><span>Pembaruan terakhir</span><time>{monitor.receivedAt ? `${localTime(monitor.receivedAt)} WIB${live ? '' : ' · terakhir diterima'}` : '—'}</time></div></div>
        </aside>
      </div>
      <section className="history-panel" id="history" aria-labelledby="history-title">
        <div className="section-toolbar"><div><h2 id="history-title">Riwayat kejadian</h2><p>20 kejadian terakhir · sesi ATCS saat ini</p></div><label className="history-filter">Tampilkan<select value={eventFilter} onChange={event => { setEventFilter(event.target.value as typeof eventFilter) }}><option value="all">Semua kejadian</option><option value="phase">Pergantian fase</option><option value="incident">Gangguan &amp; penahanan</option></select></label></div>
        {journalState === 'unavailable' && <p className="history-note" role="status">Pembaruan riwayat terputus. Baris yang tersimpan merupakan kejadian sebelumnya.</p>}
        <div className="history-actions"><button aria-expanded={historyVisible} onClick={() => setHistoryVisible(v => !v)}>{historyVisible ? 'Sembunyikan kejadian' : 'Tampilkan kejadian'}</button><a href="/history">Buka arsip riwayat lengkap</a></div>
        <div hidden={!historyVisible}>
        {visibleEvents.length ? <div className="table-scroll"><table className="event-table"><thead><tr><th scope="col">Waktu (WIB)</th><th scope="col">Kejadian</th><th scope="col">Fase / arah</th><th scope="col">Keterangan pengendali</th></tr></thead><tbody>{visibleEvents.map(event => <tr key={event.event_id}><td><time dateTime={event.occurred_at}>{localTime(event.occurred_at)}</time></td><th scope="row">{eventNames[event.event_type]}</th><td><span className={`event-phase event-phase--${event.phase}`}>{phaseNames[event.phase]}{event.active_approach ? ` · ${event.active_approach}` : ''}</span></td><td>{event.reason}</td></tr>)}</tbody></table></div>
          : <p className="empty-history">{!monitor.runId ? 'Riwayat akan muncul setelah sesi ATCS terverifikasi.' : journalState === 'loading' ? 'Memuat riwayat sesi…' : journalState === 'unavailable' ? 'Riwayat belum dapat diperbarui.' : 'Belum ada kejadian untuk pilihan ini.'}</p>}
        </div>
      </section>
      </div>
      {workspace !== 'simulation' && <ModelQualityPanel active={Boolean(config)} />}
      <Readiness snapshot={snapshot} />
      <footer><span><strong>SIGAP</strong> — Sistem Pengaturan Fase Lampu Adaptif Berbasis CCTV dan Deteksi Kendaraan YOLO.</span><span>Video bersama · YOLO26s + ByteTrack</span></footer>
    </main>
  </>
}

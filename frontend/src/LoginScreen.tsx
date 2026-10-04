import { useEffect, useRef, useState, type FormEvent } from 'react'
import { directions, directionNames, type Direction } from './traffic'
import { SigapLogo } from './SigapLogo'

const destinations: Record<Direction, { road: string; opposite: string; left: string }> = {
  U: { road: 'Jl. Ibrahim Adjie', opposite: 'Selatan', left: 'Timur' },
  T: { road: 'Jl. Soekarno Hatta', opposite: 'Barat', left: 'Selatan' },
  S: { road: 'Jl. Ibrahim Adjie', opposite: 'Utara', left: 'Barat' },
  B: { road: 'Jl. Soekarno Hatta', opposite: 'Timur', left: 'Utara' },
}

function JunctionIllustration({ direction, busy }: { direction: Direction; busy: boolean }) {
  return <svg className={`login-junction${busy ? ' is-verifying' : ''}`} viewBox="0 0 640 510" role="img" aria-label={`Ilustrasi rute dari ${directionNames[direction]}; bukan kondisi lampu aktual`}>
    <defs><marker id="login-route-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path d="M1 1 L9 5 L1 9" fill="none" stroke="#9dcdf0" strokeWidth="2" /></marker></defs>
    <path className="login-road" d="M260 36 H380 V195 H600 V315 H380 V474 H260 V315 H40 V195 H260Z" />
    {directions.map((code, i) => <g key={code} transform={`rotate(${i * 90} 320 255)`}>
      <path className="login-slip-edge" d="M360 103 C360 165 410 215 472 215" />
      <path className="login-slip-road" d="M360 103 C360 165 410 215 472 215" />
      <path className="login-island" d="M387 167 Q400 185 423 187 H387Z" />
      <path className="login-lane" d="M290 51 V184 M350 51 V184" />
      <path className="login-median" d="M320 51 V181" />
      <path className="login-stop" d="M325 187 H374" />
      <path className="login-lane-arrow" d="M335 129 V151 M330 145 L335 151 L340 145 M280 133 V111 M275 117 L280 111 L285 117" />
    </g>)}
    <g className="login-selected-route" transform={`rotate(${directions.indexOf(direction) * 90} 320 255)`}>
      <path d="M360 70 V441" markerEnd="url(#login-route-arrow)" />
      <path d="M360 103 C360 165 410 215 472 215 H555" markerEnd="url(#login-route-arrow)" />
      <circle cx="360" cy="76" r="5" />
    </g>
    <g className="login-map-labels"><text x="320" y="22" textAnchor="middle">U</text><text x="618" y="261" textAnchor="middle">T</text><text x="320" y="499" textAnchor="middle">S</text><text x="22" y="261" textAnchor="middle">B</text></g>
    <g className="login-map-caption"><text x="48" y="70">KIRCON</text><text x="48" y="91">BANDUNG</text><text x="458" y="438">SKEMA SIMPANG</text><text x="458" y="457">ILUSTRASI</text></g>
  </svg>
}

export function LoginScreen({ screen, busy, message, onSubmit, onRetry }: {
  screen: 'checking' | 'guest' | 'unavailable'; busy: boolean; message: string
  onSubmit: (username: string, password: string) => Promise<void>; onRetry: () => void
}) {
  const [direction, setDirection] = useState<Direction>('U')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [visible, setVisible] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const [localError, setLocalError] = useState('')
  const feedback = useRef<HTMLDivElement>(null)
  const displayedMessage = localError || message
  useEffect(() => { if (displayedMessage) feedback.current?.focus() }, [displayedMessage])
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    if (username.trim().length < 3 || !password) { setLocalError('Isi nama pengguna dan kata sandi terlebih dahulu.'); return }
    setLocalError('')
    const submitted = password
    setPassword(''); setVisible(false); setCapsLock(false)
    await onSubmit(username.trim(), submitted)
  }
  const selected = destinations[direction]

  return <div className="login-shell">
    <a className="skip-link" href="#login-content">Lewati ke formulir masuk</a>
    <section className="login-world" aria-label="SIGAP dan ilustrasi simpang">
      <div className="login-brand"><span className="login-brand-symbol"><SigapLogo /></span><span className="login-brand-caption">RUANG KENDALI<br />PERSIMPANGAN</span></div>
      <div className="login-world-heading"><p className="login-kicker">IBRAHIM ADJIE × SOEKARNO HATTA</p><h2>Kenali arah.<br /><span>Pantau pergerakan.</span></h2></div>
      <JunctionIllustration direction={direction} busy={busy || screen === 'checking'} />
      <div className="login-explorer">
        <div className="login-explorer-label"><span>JELAJAHI PENDEKAT</span><span aria-hidden="true">↗</span></div>
        <div className="login-directions" role="group" aria-label="Jelajahi ilustrasi pendekat">{directions.map(code => <button key={code} type="button" aria-pressed={direction === code} onClick={() => setDirection(code)}><span>{code}</span>{directionNames[code]}</button>)}</div>
        <div className="login-route-detail" aria-live="polite"><strong>{selected.road}</strong><span>Dari {directionNames[direction]} · lurus ke {selected.opposite}, ruas pintas kiri ke {selected.left}.</span></div>
      </div>
      <div className="login-world-footer"><span>SIMPANG KIRCON / BANDUNG</span><span>SIMULASI LOKAL</span></div>
    </section>
    <main className="login-access" id="login-content">
      <div className="login-access-top"><span>AKSES OPERATOR</span><span className="login-access-marker"><svg width="14" height="16" viewBox="0 0 14 16" fill="none" aria-hidden="true"><path d="M2 7V5a5 5 0 0 1 10 0v2M1 7h12v8H1zM7 10v2" stroke="currentColor" strokeWidth="1.4" /></svg>SIGAP</span></div>
      <div className="login-form-area">
        <span className="login-form-overline">MONITOR PERSIMPANGAN</span>
        <h1>{screen === 'unavailable' ? 'Koneksi belum siap.' : screen === 'checking' ? 'Memeriksa sesi.' : 'Masuk ke SIGAP.'}</h1>
        <p className="login-intro">{screen === 'guest' ? 'Gunakan akun operator untuk membuka monitor dan riwayat persimpangan.' : screen === 'checking' ? 'Memastikan aksesmu sebelum membuka ruang kendali.' : 'Akses ke ruang kendali menunggu sesi yang terverifikasi.'}</p>
        {displayedMessage && <div ref={feedback} tabIndex={-1} className={`login-feedback${displayedMessage.startsWith('Kamu sudah keluar') ? ' is-notice' : ''}`} role={displayedMessage.startsWith('Kamu sudah keluar') ? 'status' : 'alert'}>{displayedMessage}</div>}
        {screen === 'guest' && <form onSubmit={event => void submit(event)} className="login-form" aria-label="Masuk operator">
          <div className="login-field"><label htmlFor="username">Nama pengguna</label><input id="username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} required minLength={3} maxLength={80} placeholder="Nama pengguna operator" value={username} disabled={busy} onChange={event => setUsername(event.target.value)} /></div>
          <div className="login-field"><label htmlFor="password">Kata sandi</label><div className="login-password"><input id="password" name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" required maxLength={128} placeholder="Masukkan kata sandi" value={password} disabled={busy} onChange={event => setPassword(event.target.value)} onKeyUp={event => setCapsLock(event.getModifierState('CapsLock'))} onBlur={() => setCapsLock(false)} />
            <button type="button" className="password-toggle" aria-label={visible ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'} aria-pressed={visible} aria-controls="password" disabled={busy} onClick={() => setVisible(value => !value)}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" stroke="currentColor" strokeWidth="1.5" /><circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5" />{visible && <path d="M4 3L21 21" stroke="currentColor" strokeWidth="1.5" />}</svg></button></div>
            {capsLock && <p className="caps-lock" role="status">Caps Lock aktif.</p>}
          </div>
          <button className="login-submit" type="submit" disabled={busy}>{busy ? <><span className="auth-spinner" aria-hidden="true" />Memverifikasi akses…</> : <>Masuk ke ruang kendali<span aria-hidden="true">→</span></>}</button>
          <p className="login-account-help">Akun dikelola oleh pengelola SIGAP. Hubungi pengelola jika aksesmu perlu diperbarui.</p>
        </form>}
        {screen === 'checking' && <div className="login-checking" role="status"><span className="auth-spinner" aria-hidden="true" />Memeriksa akses operator…</div>}
        {screen === 'unavailable' && <button type="button" className="login-submit" onClick={onRetry}>Periksa koneksi lagi<span aria-hidden="true">↻</span></button>}
        <div className="login-access-note"><span aria-hidden="true">↳</span><p>Setelah masuk, kamu dapat melihat fase lampu, detail pendekat, dan riwayat ATCS.</p></div>
      </div>
      <div className="login-access-footer"><span>Sistem Pengaturan Fase Lampu Adaptif<br />Berbasis CCTV dan Deteksi Kendaraan YOLO.</span><span>AKSES LOKAL<br /><strong>SIGAP / 2D</strong></span></div>
    </main>
  </div>
}

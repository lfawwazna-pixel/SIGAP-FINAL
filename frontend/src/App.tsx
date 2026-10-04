import { useCallback, useEffect, useRef, useState } from 'react'
import { LoginScreen } from './LoginScreen'
import { Monitor } from './Monitor'
import { login, logout, restoreSession, type AuthResult } from './authApi'
import { nextAuthGeneration } from './authEvents'
import type { SessionView } from './types/SessionView'

export function App() {
  const [session, setSession] = useState<SessionView | null>(null)
  const [screen, setScreen] = useState<'checking' | 'guest' | 'authenticated' | 'unavailable'>('checking')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [logoutError, setLogoutError] = useState<string | null>(null)
  const active = useRef<AbortController | null>(null)
  const lock = useRef(false)
  const begin = useCallback(() => { active.current?.abort(); const abort = new AbortController(); active.current = abort; return abort }, [])
  const apply = useCallback((result: AuthResult) => {
    if (result.kind === 'authenticated') { setSession(result.session); setScreen('authenticated'); setMessage('') }
    else { nextAuthGeneration(); setSession(null); setScreen(result.kind === 'guest' ? 'guest' : 'unavailable'); setMessage(result.message) }
  }, [])
  const check = useCallback(async (hide = false) => {
    if (lock.current) return
    const abort = begin()
    if (hide) { nextAuthGeneration(); setScreen('checking') }
    const result = await restoreSession(abort.signal)
    if (!abort.signal.aborted) apply(result)
  }, [apply, begin])
  useEffect(() => {
    if (screen === 'checking') return
    const path = screen === 'authenticated' ? '/monitor' : '/login'
    if (window.location.pathname !== path) window.history.replaceState(null, '', path)
  }, [screen])
  useEffect(() => {
    void check(true)
    function rejected() {
      if (lock.current) return
      active.current?.abort(); nextAuthGeneration()
      setSession(null); setScreen('guest'); setMessage('Sesi telah berakhir atau akses dicabut. Silakan masuk kembali.')
    }
    window.addEventListener('sigap:session-rejected', rejected)
    const navigate = () => void check(true)
    window.addEventListener('popstate', navigate)
    return () => {
      active.current?.abort()
      window.removeEventListener('sigap:session-rejected', rejected)
      window.removeEventListener('popstate', navigate)
    }
  }, [check])
  useEffect(() => {
    if (screen !== 'authenticated' || !session) return
    // Monitoring polls do not extend the session; recheck expiry with the server.
    const timer = setTimeout(() => void check(), Math.min(session.remaining_seconds * 1000, 60000))
    function visible() { if (!document.hidden) void check(true) }
    document.addEventListener('visibilitychange', visible)
    window.addEventListener('pageshow', visible)
    return () => { clearTimeout(timer); document.removeEventListener('visibilitychange', visible); window.removeEventListener('pageshow', visible) }
  }, [screen, session, check])
  async function signIn(username: string, password: string) {
    if (lock.current) return
    lock.current = true
    const abort = begin()
    setBusy(true); setMessage('')
    const result = await login(username, password, abort.signal)
    if (!abort.signal.aborted) {
      nextAuthGeneration()
      if (result.kind === 'authenticated') apply(result)
      else { setScreen('guest'); setMessage(result.message) }
      setBusy(false)
    }
    lock.current = false
  }
  async function signOut() {
    if (lock.current || !session) return
    lock.current = true
    const abort = begin()
    setBusy(true); setLogoutError(null)
    const failure = await logout(session.csrf_token, abort.signal)
    if (!abort.signal.aborted) {
      if (failure) setLogoutError(failure)
      else { nextAuthGeneration(); setSession(null); setScreen('guest'); setMessage('Kamu sudah keluar. Sesi telah diakhiri.') }
      setBusy(false)
    }
    lock.current = false
  }
  if (screen === 'authenticated' && session) return <Monitor session={session} onLogout={() => void signOut()} signingOut={busy} logoutError={logoutError} />
  return <LoginScreen screen={screen === 'authenticated' ? 'checking' : screen} busy={busy} message={message} onSubmit={signIn} onRetry={() => void check(true)} />
}

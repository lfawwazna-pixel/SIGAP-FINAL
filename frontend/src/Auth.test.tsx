import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { restoreSession } from './authApi'
import { authGeneration, rejectSession } from './authEvents'
import { readStatus } from './api'
import { respond, sessionFixture } from './testFixtures'

vi.mock('./Monitor', () => ({ Monitor: ({ onLogout, logoutError }: { onLogout: () => void; logoutError: string | null }) => <div><h1>Monitor terlindungi</h1><button onClick={onLogout}>Keluar dari SIGAP</button>{logoutError && <p role="alert">{logoutError}</p>}</div> }))
const flush = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms) }) }
const enter = () => {
  fireEvent.change(screen.getByLabelText('Nama pengguna'), { target: { value: 'operator.test' } })
  fireEvent.change(screen.getByLabelText('Kata sandi'), { target: { value: 'test password' } })
  fireEvent.submit(screen.getByRole('form', { name: 'Masuk operator' }))
}
let authenticated = false
let requested: string[]
beforeEach(() => {
  vi.useFakeTimers()
  window.history.replaceState(null, '', '/')
  authenticated = false; requested = []
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    requested.push(url)
    if (url.endsWith('/auth/session')) return respond(authenticated ? sessionFixture() : {}, authenticated ? 200 : 401)
    if (url.endsWith('/auth/login')) { authenticated = true; return respond(sessionFixture()) }
    if (url.endsWith('/auth/logout')) { authenticated = false; return Promise.resolve(new Response(null, { status: 204 })) }
    return respond({}, 401)
  }))
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('operator authentication', () => {
  it('keeps the authenticated page mounted for navigation within a page', async () => {
    authenticated = true
    render(<App />); await flush()
    const reads = [...requested]
    window.history.pushState(null, '', '/monitor#history')
    window.dispatchEvent(new PopStateEvent('popstate')); await flush()
    expect(requested).toEqual(reads)
    expect(screen.getByText('Monitor terlindungi')).toBeTruthy()
  })
  it('shows only the login after anonymous session check, with no protected API reads', async () => {
    window.history.replaceState(null, '', '/monitor')
    render(<App />)
    expect(screen.queryByText('Monitor terlindungi')).toBeNull()
    await flush()
    expect(screen.getByRole('heading', { name: 'Masuk ke SIGAP.' })).toBeTruthy()
    expect(requested).toEqual(['/api/auth/session'])
    expect(window.location.pathname).toBe('/login')
    expect((screen.getByLabelText('Nama pengguna') as HTMLInputElement).value).toBe('')
    expect((screen.getByLabelText('Kata sandi') as HTMLInputElement).value).toBe('')
  })
  it('restores a verified session on page reload without presenting a login form', async () => {
    authenticated = true
    render(<App />)
    await flush()
    expect(screen.getByText('Monitor terlindungi')).toBeTruthy()
    expect(screen.queryByRole('form')).toBeNull()
  })
  it('allows password visibility and explores the diagram without network requests', async () => {
    render(<App />); await flush()
    fireEvent.click(screen.getByRole('button', { name: 'Tampilkan kata sandi' }))
    expect((screen.getByLabelText('Kata sandi') as HTMLInputElement).type).toBe('text')
    fireEvent.click(screen.getByRole('button', { name: 'Sembunyikan kata sandi' }))
    expect((screen.getByLabelText('Kata sandi') as HTMLInputElement).type).toBe('password')
    fireEvent.click(screen.getByRole('button', { name: 'T Timur' }))
    expect(screen.getByRole('img', { name: /Ilustrasi rute dari Timur/ })).toBeTruthy()
    expect(requested).toEqual(['/api/auth/session'])
  })
  it('submits credentials once, clears password input, and enters only after verification', async () => {
    const store = vi.spyOn(window.Storage.prototype, 'setItem')
    render(<App />); await flush()
    enter()
    expect((screen.getByLabelText('Kata sandi') as HTMLInputElement).value).toBe('')
    await flush()
    expect(screen.getByText('Monitor terlindungi')).toBeTruthy()
    const call = vi.mocked(fetch).mock.calls.find(([url]) => String(url).endsWith('/auth/login'))!
    expect(window.location.pathname).toBe('/monitor')
    expect(call[1]?.credentials).toBe('same-origin')
    expect(call[1]?.headers).toEqual({ 'Content-Type': 'application/json', 'X-SIGAP-Request': '1' })
    expect(store).not.toHaveBeenCalled()
  })
  it('keeps the login visible with a generic error on incorrect credentials', async () => {
    render(<App />); await flush()
    vi.mocked(fetch).mockImplementationOnce(() => respond({}, 401))
    enter(); await flush()
    expect(screen.getByRole('alert').textContent).toContain('Nama pengguna atau kata sandi salah')
    expect(screen.queryByText('Monitor terlindungi')).toBeNull()
  })
  it('handles throttling, network errors and invalid contracts without granting access', async () => {
    render(<App />); await flush()
    vi.mocked(fetch).mockImplementationOnce(() => respond({}, 429))
    enter(); await flush()
    expect(screen.getByRole('alert').textContent).toContain('dibatasi sementara')
    vi.mocked(fetch).mockRejectedValueOnce(new Error('network'))
    enter(); await flush()
    expect(screen.getByRole('alert').textContent).toContain('Koneksi terputus')
    vi.mocked(fetch).mockImplementationOnce(() => respond({ operator: { username: 'spoofed' } }))
    enter(); await flush()
    expect(screen.queryByText('Monitor terlindungi')).toBeNull()
  })
  it('returns to login when a protected API reports expired or revoked access', async () => {
    authenticated = true
    render(<App />); await flush()
    await act(async () => { await readStatus(new AbortController().signal) })
    expect(screen.queryByText('Monitor terlindungi')).toBeNull()
    expect(screen.getByRole('alert').textContent).toContain('Sesi telah berakhir')
  })
  it('ignores unauthorized responses from the previous login generation', async () => {
    render(<App />); await flush()
    const previous = authGeneration()
    enter(); await flush()
    act(() => rejectSession(previous))
    expect(screen.getByText('Monitor terlindungi')).toBeTruthy()
  })
  it('checks absolute expiration with the server and closes the authenticated view', async () => {
    authenticated = true
    vi.mocked(fetch).mockImplementationOnce(() => respond({ ...sessionFixture(), remaining_seconds: 1 }))
    render(<App />); await flush()
    authenticated = false
    await flush(1000)
    expect(screen.queryByText('Monitor terlindungi')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Masuk ke SIGAP.' })).toBeTruthy()
  })
  it('logs out using CSRF, hides the dashboard, and cannot restore the revoked session', async () => {
    authenticated = true
    const { unmount } = render(<App />); await flush()
    fireEvent.click(screen.getByRole('button', { name: 'Keluar dari SIGAP' })); await flush()
    expect(screen.queryByText('Monitor terlindungi')).toBeNull()
    expect(screen.getByText('Kamu sudah keluar. Sesi telah diakhiri.')).toBeTruthy()
    expect(window.location.pathname).toBe('/login')
    const call = vi.mocked(fetch).mock.calls.find(([url]) => String(url).endsWith('/auth/logout'))!
    expect(call[1]?.headers).toEqual({ 'X-SIGAP-Request': '1', 'X-CSRF-Token': sessionFixture().csrf_token })
    unmount(); render(<App />); await flush()
    expect(screen.queryByText('Monitor terlindungi')).toBeNull()
  })
  it('does not claim logout succeeded when the server cannot confirm revocation', async () => {
    authenticated = true
    render(<App />); await flush()
    vi.mocked(fetch).mockRejectedValueOnce(new Error('network'))
    fireEvent.click(screen.getByRole('button', { name: 'Keluar dari SIGAP' })); await flush()
    expect(screen.getByRole('alert').textContent).toContain('belum terkonfirmasi')
    expect(screen.getByText('Monitor terlindungi')).toBeTruthy()
  })
  it('rechecks access on browser navigation instead of restoring a logged-out monitor', async () => {
    render(<App />); await flush()
    window.history.pushState(null, '', '/monitor')
    act(() => window.dispatchEvent(new PopStateEvent('popstate')))
    await flush()
    expect(screen.queryByText('Monitor terlindungi')).toBeNull()
    expect(window.location.pathname).toBe('/login')
  })
  it('requires a valid contract and recovers an unavailable session service through retry', async () => {
    vi.mocked(fetch).mockImplementationOnce(() => respond({}, 200))
    expect((await restoreSession(new AbortController().signal)).kind).toBe('error')
    vi.mocked(fetch).mockRejectedValueOnce(new Error('offline'))
    render(<App />); await flush()
    expect(screen.getByRole('heading', { name: 'Koneksi belum siap.' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Periksa koneksi lagi' })); await flush()
    expect(screen.getByRole('heading', { name: 'Masuk ke SIGAP.' })).toBeTruthy()
  })
})

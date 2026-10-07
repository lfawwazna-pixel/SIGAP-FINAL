import {act,cleanup,fireEvent,render,screen} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import {HistoryPage} from './HistoryPage'
import {config,eventFixture,respond,sessionFixture,timestamp} from './testFixtures'

afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()})
it('reads durable older pages and applies the selected event filter',async()=>{
  vi.stubGlobal('fetch',vi.fn((url:string)=>{
    const q=new URL(url,'http://localhost').searchParams
    return respond({intersection_id:config.intersection_id,generated_at:timestamp,filter:q.get('event_filter'),events:[eventFixture({reason:q.has('before')?'Kejadian lama':'Kejadian terbaru'})],next_before:q.has('before')?null:31,has_more:!q.has('before')})
  }))
  render(<HistoryPage session={sessionFixture()} onLogout={()=>undefined}/>);await act(async()=>{})
  expect(screen.getByText('Kejadian terbaru')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'Kejadian lebih lama'}));await act(async()=>{})
  expect(screen.getByText('Kejadian lama')).toBeTruthy()
  expect(vi.mocked(fetch).mock.calls.at(-1)![0]).toContain('before=31')
  fireEvent.change(screen.getByRole('combobox',{name:'Tampilkan'}),{target:{value:'phase'}});await act(async()=>{})
  expect(vi.mocked(fetch).mock.calls.at(-1)![0]).toContain('event_filter=phase')
  expect(vi.mocked(fetch).mock.calls.at(-1)![0]).not.toContain('before=')
})
it('does not show unverified history on an invalid response',async()=>{
  vi.stubGlobal('fetch',vi.fn(()=>respond({events:[{reason:'Unverified'}]})))
  render(<HistoryPage session={sessionFixture()} onLogout={()=>undefined}/>);await act(async()=>{})
  expect(screen.queryByRole('table')).toBeNull()
  expect(screen.getByRole('alert').textContent).toMatch(/belum dapat dimuat/)
})

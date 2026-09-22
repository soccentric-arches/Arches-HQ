import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import AlarmsPanel from '../AlarmsPanel.vue'
import { useAuthStore } from '@/stores/auth'
import type { DeviceAlarm, DeviceAlarmListResponse } from '@/lib/types'

// Mock the api module so the panel never hits the network. vi.hoisted runs
// before vi.mock's hoisted factory, so the `api` handle is defined when the
// factory executes and is also accessible to the test bodies below. The
// vi.fn type parameters satisfy oxlint's require-mock-type-parameters rule
// and keep the mock signature aligned with the real api client.
const { api } = vi.hoisted(() => ({
  api: {
    alarms: {
      listForDevice: vi.fn<(deviceId: string) => Promise<DeviceAlarmListResponse>>(),
      clear: vi.fn<(deviceId: string, alarmId: string) => Promise<DeviceAlarm>>(),
    },
  },
}))

vi.mock('@/lib/api', () => ({ api, ApiError: class ApiError extends Error {} }))

const DEVICE_ID = '11111111-1111-1111-1111-111111111111'
const ALARM_ID = '22222222-2222-2222-2222-222222222222'

function deviceAlarmResponse(state: DeviceAlarm['state'] = 'active'): DeviceAlarmListResponse {
  return {
    items: [
      {
        id: ALARM_ID,
        device_id: DEVICE_ID,
        domain: 1,
        module: 4,
        alarm_type: 1,
        alarm_index: 7,
        severity: 'major',
        alarm_code: 0x10410007,
        state,
        triggered_at: '2026-07-30T12:00:00Z',
        resolved_at: null,
        // C-06 transport fields, as the gateway now stores them.
        owner: 'arches-client',
        count: 3,
        acknowledged: false,
        needs_snapshot: false,
        first_seen_at: '2026-07-30T11:00:00Z',
        last_seen_at: '2026-07-30T12:00:00Z',
        correlated: [0x10410008],
        // C-07: catalog rendering fields joined at the API.
        catalog: {
          name: 'hw_device_fail',
          probable_cause: 'hardware-malfunction',
          specific_problem: 'device-failure',
          description: 'Hardware device failure detected by the Hardware daemon.',
          escalation: 'none',
          auto_clear: 'manual',
          hq_reportable: true,
        },
      },
    ],
    page: { total: 1, limit: 100, offset: 0 },
  }
}

// Mount the panel with an operator session so the Clear button is visible.
// A single pinia instance is both set active and provided to the app, so the
// auth store mutated here is the same one the component reads in setup.
async function mountAsOperator() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = { id: '1', email: 'op@example.com', role: 'operator', created_at: '' }

  const wrapper = mount(AlarmsPanel, {
    props: { deviceId: DEVICE_ID },
    global: { plugins: [pinia] },
  })
  await flushPromises()
  return wrapper
}

function findButton(wrapper: Awaited<ReturnType<typeof mountAsOperator>>, text: string) {
  const btn = wrapper.findAll('button').find((b) => b.text().includes(text))
  expect(btn, `expected a ${text} button`).toBeDefined()
  return btn!
}

describe('AlarmsPanel', () => {
  beforeEach(() => {
    api.alarms.listForDevice.mockReset()
    api.alarms.clear.mockReset()
    api.alarms.listForDevice.mockResolvedValue(deviceAlarmResponse())
    api.alarms.clear.mockResolvedValue({
      id: ALARM_ID,
      device_id: DEVICE_ID,
      domain: 1,
      module: 4,
      alarm_type: 1,
      alarm_index: 7,
      severity: 'major',
      alarm_code: 0x10410007,
      state: 'resolved',
      triggered_at: '2026-07-30T12:00:00Z',
      resolved_at: '2026-07-30T12:01:00Z',
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the hex alarm_code with its catalog name and description', async () => {
    const wrapper = await mountAsOperator()

    const html = wrapper.html()
    // The catalog's worked example: hardware / Hardware daemon / equipment /
    // alarm 7 (Arches-Instrumentation REQ.md section 8). Since C-07 the panel
    // renders the catalog's symbolic name and description beside the packed
    // hex code instead of four bare numeric columns.
    expect(html).toContain('0x10410007')
    expect(wrapper.text()).toContain('hw_device_fail')
    expect(wrapper.text()).toContain('Hardware device failure detected by the Hardware daemon.')
    expect(html).toContain('Alarm')
    expect(html).toContain('Severity')
    expect(wrapper.text()).toContain('active')
  })

  it('renders the owning application and correlated alarm codes', async () => {
    const wrapper = await mountAsOperator()

    const text = wrapper.text()
    expect(text).toContain('owner: arches-client')
    expect(text).toContain('correlated: 0x10410008')
  })

  it('renders severity as a named X.733 level, not a bare number', async () => {
    // Regression guard for Task.md C-03/C-05: severity used to be the low byte
    // of the alarm index rendered as an integer.
    const wrapper = await mountAsOperator()

    expect(wrapper.text()).toContain('major')
    expect(wrapper.text()).not.toContain('sub_section')
  })

  it('shows a Clear button for an active alarm (operator) and wires it to api.alarms.clear, then re-loads', async () => {
    const wrapper = await mountAsOperator()

    const clearBtn = findButton(wrapper, 'Clear')
    await clearBtn.trigger('click')
    await flushPromises()

    expect(api.alarms.clear).toHaveBeenCalledWith(DEVICE_ID, ALARM_ID)
    // clear() resolves -> load() re-fires the list call.
    expect(api.alarms.listForDevice).toHaveBeenCalledTimes(2)
  })

  it('hides Clear for resolved alarms', async () => {
    api.alarms.listForDevice.mockResolvedValue(deviceAlarmResponse('resolved'))
    const wrapper = await mountAsOperator()

    expect(wrapper.findAll('button').some((b) => b.text().includes('Clear'))).toBe(false)
  })
})
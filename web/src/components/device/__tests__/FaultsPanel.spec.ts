import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import FaultsPanel from '../FaultsPanel.vue'
import type { FaultListResponse } from '@/lib/types'

// Mock the api module so the panel never hits the network.
const { api } = vi.hoisted(() => ({
  api: {
    faults: { list: vi.fn<(deviceId: string) => Promise<FaultListResponse>>() },
  },
}))

vi.mock('@/lib/api', () => ({ api, ApiError: class ApiError extends Error {} }))

const DEVICE_ID = '11111111-1111-1111-1111-111111111111'

describe('FaultsPanel', () => {
  it('renders fault code, severity and message', async () => {
    api.faults.list.mockResolvedValue({
      items: [
        {
          id: 'f1',
          device_id: DEVICE_ID,
          code: 'PSU-0x12',
          severity: 'critical',
          message: 'Power supply undervoltage',
          raised_at: '2026-07-30T12:00:00Z',
          cleared_at: null,
        },
      ],
      page: { total: 1, limit: 100, offset: 0 },
    })

    const wrapper = mount(FaultsPanel, { props: { deviceId: DEVICE_ID } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('PSU-0x12')
    expect(text).toContain('critical')
    expect(text).toContain('Power supply undervoltage')
  })

  it('shows an empty state when no faults are reported', async () => {
    api.faults.list.mockResolvedValue({
      items: [],
      page: { total: 0, limit: 100, offset: 0 },
    })

    const wrapper = mount(FaultsPanel, { props: { deviceId: DEVICE_ID } })
    await flushPromises()

    expect(wrapper.text()).toContain('No faults reported in the last 24 hours.')
  })
})
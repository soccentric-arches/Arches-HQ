import { describe, expect, it } from 'vitest'
import { cn } from '../utils'

describe('cn', () => {
  it('merges class strings and drops falsy values', () => {
    expect(cn('a', false && 'b', 'c')).toBe('a c')
  })

  it('lets a later tailwind class win over an earlier conflicting one', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4')
  })
})

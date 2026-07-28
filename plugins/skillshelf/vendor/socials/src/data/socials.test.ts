import { describe, expect, it } from 'vitest'
import { socialLinks } from './socials'

describe('social link configuration', () => {
  it('uses unique ids and secure external URLs', () => {
    const ids = socialLinks.map((link) => link.id)
    expect(new Set(ids).size).toBe(ids.length)
    for (const link of socialLinks) expect(new URL(link.href).protocol).toBe('https:')
  })

  it('includes every requested public destination', () => {
    expect(socialLinks.map((link) => link.id)).toEqual(expect.arrayContaining([
      'x', 'linkedin', 'facebook', 'easyequities', 'website',
    ]))
  })
})

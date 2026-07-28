export type SocialId = 'github' | 'linkedin' | 'x' | 'facebook' | 'instagram' | 'easyequities' | 'website'

export interface SocialLink {
  id: SocialId
  label: string
  handle: string
  href: string
  description: string
  signal: string
  featured?: boolean
}

export const socialLinks: SocialLink[] = [
  {
    id: 'github',
    label: 'GitHub',
    handle: '@berendsshalai',
    href: 'https://github.com/berendsshalai',
    description: 'Source code, system architecture and public build evidence.',
    signal: 'Builds and repositories',
    featured: true,
  },
  {
    id: 'linkedin',
    label: 'LinkedIn',
    handle: 'Sha-Lai Berends',
    href: 'https://www.linkedin.com/in/sha-lai-berends',
    description: 'Professional context, certifications and the story behind the work.',
    signal: 'Professional profile',
    featured: true,
  },
  {
    id: 'x',
    label: 'X',
    handle: '@berendsshalai',
    href: 'https://x.com/berendsshalai',
    description: 'Short-form notes on technology, learning and active experiments.',
    signal: 'Ideas in progress',
  },
  {
    id: 'facebook',
    label: 'Facebook',
    handle: 'Sha-Lai Berends',
    href: 'https://www.facebook.com/p/Sha-Lai-Berends-61591546301365/',
    description: 'Community updates and a more personal view of the work in motion.',
    signal: 'Community profile',
  },
  {
    id: 'instagram',
    label: 'Instagram',
    handle: '@berendsshalai',
    href: 'https://www.instagram.com/berendsshalai',
    description: 'Visual notes, project moments and creative work beyond the interface.',
    signal: 'Visual journal',
  },
  {
    id: 'easyequities',
    label: 'EasyEquities',
    handle: 'Investor profile',
    href: 'https://bit.ly/3sA5312',
    description: 'A public entry point into long-term investing and financial learning.',
    signal: 'Financial learning',
  },
  {
    id: 'website',
    label: 'Portfolio website',
    handle: 'Sha-Lai Berends',
    href: 'https://sha-lai-be-2a6c6108-shalaiberends.wix-site-host.com',
    description: 'The live interactive case study for recruitment automation and creative engineering.',
    signal: 'Featured case study',
    featured: true,
  },
]

export const profile = {
  name: 'Sha-Lai Berends',
  role: 'AI Workflow and Automation Specialist',
  location: 'South Africa',
  github: 'https://github.com/berendsshalai',
  portfolio: 'https://sha-lai-be-2a6c6108-shalaiberends.wix-site-host.com',
}

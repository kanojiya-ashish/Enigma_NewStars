import type { SVGProps } from 'react'

export type IconName =
  | 'grid' | 'box' | 'plus' | 'brain' | 'users' | 'truck' | 'route' | 'activity' | 'shield'
  | 'bell' | 'logout' | 'search' | 'check' | 'x' | 'clock' | 'location' | 'file' | 'upload'
  | 'arrow' | 'refresh' | 'chevron' | 'eye' | 'send' | 'layers' | 'clipboard' | 'package' | 'settings'
  | 'camera' | 'navigation' | 'circle' | 'menu' | 'close' | 'info' | 'warning'

const paths: Record<IconName, string> = {
  grid: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  box: 'M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z M12 12l9-4.5 M12 12 3 7.5 M12 12v9',
  plus: 'M12 5v14 M5 12h14',
  brain: 'M9 4a3 3 0 0 0-3 3v1a3 3 0 0 0-2 5 3 3 0 0 0 3 4h2 M15 4a3 3 0 0 1 3 3v1a3 3 0 0 1 2 5 3 3 0 0 1-3 4h-2 M9 4v17 M15 4v17 M9 9h6 M9 15h6',
  users: 'M16 20v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2 M9.5 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M20.5 20v-2a4 4 0 0 0-3-3.87 M16.5 2.13a4 4 0 0 1 0 7.74',
  truck: 'M3 6h11v10H3z M14 10h4l3 3v3h-7z M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M18 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  route: 'M5 19c3 0 3-8 6-8s3 8 6 8 M19 5c-3 0-3 8-6 8s-3-8-6-8 M5 5h.01 M19 19h.01',
  activity: 'M3 12h4l2-6 4 12 2-6h6',
  shield: 'M12 3l8 4v5c0 4.5-3.2 8.4-8 9-4.8-.6-8-4.5-8-9V7z M9 12l2 2 4-4',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4',
  logout: 'M10 17l5-5-5-5 M15 12H3 M21 19V5a2 2 0 0 0-2-2h-5',
  search: 'M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16z M21 21l-4.35-4.35',
  check: 'M5 12l4 4L19 6',
  x: 'M6 6l12 12 M18 6 6 18',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 2',
  location: 'M12 21s7-5.2 7-11a7 7 0 1 0-14 0c0 5.8 7 11 7 11z M12 12a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4z',
  file: 'M6 3h8l4 4v14H6z M14 3v5h5 M9 13h6 M9 17h6',
  upload: 'M12 16V4 M7 9l5-5 5 5 M5 20h14',
  arrow: 'M5 12h13 M13 6l6 6-6 6',
  refresh: 'M20 11a8 8 0 0 0-14.5-4L3 9 M3 4v5h5 M4 13a8 8 0 0 0 14.5 4L21 15 M21 20v-5h-5',
  chevron: 'M8 10l4 4 4-4',
  eye: 'M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  send: 'M22 2 11 13 M22 2l-7 20-4-9-9-4z',
  layers: 'M12 3 21 8l-9 5-9-5z M3 12l9 5 9-5 M3 16l9 5 9-5',
  clipboard: 'M9 5h6v3H9z M6 5h12v16H6z M9 13h6 M9 17h6',
  package: 'M4 7h16v13H4z M4 7l8-4 8 4 M12 3v17',
  settings: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.9 1.9-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-2.7v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1-1.9-1.9.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H4v-2.7h.2a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.9-1.9.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6V3h2.7v.2a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.9 1.9-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2V12h-.2a1.7 1.7 0 0 0-1.7 1z',
  camera: 'M4 7h3l2-2h6l2 2h3v11H4z M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  navigation: 'M4 4l16 8-16 8 4-8z',
  circle: 'M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16z',
  menu: 'M4 7h16 M4 12h16 M4 17h16',
  close: 'M6 6l12 12 M18 6 6 18',
  info: 'M12 8h.01 M11 12h1v5h1 M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
  warning: 'M12 3l10 18H2z M12 9v4 M12 17h.01'
}

export function Icon({ name, size = 20, strokeWidth = 1.9, ...props }: { name: IconName; size?: number; strokeWidth?: number } & Omit<SVGProps<SVGSVGElement>, 'name'>) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d={paths[name]} />
    </svg>
  )
}

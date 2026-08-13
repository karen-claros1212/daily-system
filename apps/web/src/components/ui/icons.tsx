'use client';

/**
 * Iconos SVG inline (stroke 1.75, round, 24 viewBox) — MEMO doble: el catálogo
 * es estático y cada uso es un módulo de stack, así que el coste de
 * multiplicación es marginal y el contrato (dimensión heredable) se mantiene.
 */

export interface IconProps {
  className?: string;
  size?: number;
  'aria-hidden'?: boolean | 'true' | 'false';
}

const BASE = {
  xmlns: 'http://www.w3.org/2000/svg',
  fill: 'none',
  viewBox: '0 0 24 24',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
};

export function IconDashboard(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="4.5" rx="1.5" />
      <rect x="13.5" y="10.5" width="7.5" height="10.5" rx="1.5" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" />
    </svg>
  );
}

export function IconRoute(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <circle cx="5" cy="19" r="1.75" />
      <circle cx="19" cy="5" r="1.75" />
      <path d="M6.2 18.4C10 16 16 14.5 18 7.5" />
      <path d="M14 3.5L18.2 3.6 18 7.6" />
    </svg>
  );
}

export function IconCaja(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M4 8h16v11a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V8Z" />
      <path d="M3 5a1 1 0 0 1 1-1h16a1 1 0 0 1 1 1v3H3V5Z" />
      <path d="M9.5 13h5" />
    </svg>
  );
}

export function IconReportes(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M4 20V10" />
      <path d="M10 20V4" />
      <path d="M16 20v-7" />
      <path d="M2 20h20" />
    </svg>
  );
}

export function IconLogout(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5" />
      <path d="M21 12H9" />
    </svg>
  );
}

export function IconMenu(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </svg>
  );
}

export function IconChevronLeft(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

export function IconChevronDown(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export function IconAlert(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4" />
      <path d="M12 17h.01" />
    </svg>
  );
}

export function IconInfo(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <circle cx="12" cy="12" r="9.25" />
      <path d="M12 11v5" />
      <path d="M12 8h.01" />
    </svg>
  );
}

export function IconCheck(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M20 6L9 17l-5-5" />
    </svg>
  );
}

export function IconInbox(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M3 13h6a3 3 0 0 0 6 0h6" />
      <path d="M20 13H17.5L15.2 5.6a2 2 0 0 0-1.9-1.4H10.7a2 2 0 0 0-1.9 1.4L6.5 13H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2Z" />
    </svg>
  );
}

export function IconLock(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

export function IconKey(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <circle cx="7.5" cy="15.5" r="4.5" />
      <path d="M10.7 12.3L21 2" />
      <path d="M16 7l3 3" />
    </svg>
  );
}

export function IconSparkle(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M12 2l1.9 5.8L19.5 9l-5.6 1.2L12 16l-1.9-5.8L4.5 9l5.6-1.2L12 2Z" />
      <path d="M19 15l.9 2.4L22 18.3l-2.1.9L19 21.5l-.9-2.3-2.1-.9 2.1-.9L19 15Z" />
    </svg>
  );
}

export function IconShield(p: IconProps) {
  return (
    <svg {...BASE} width={p.size ?? 18} height={p.size ?? 18} className={p.className}>
      <path d="M12 2l8 3.5V11c0 5-3.5 8.6-8 11-4.5-2.4-8-6-8-11V5.5L12 2Z" />
      <path d="M9 11.5l2 2 4-4" />
    </svg>
  );
}
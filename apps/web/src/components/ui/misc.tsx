'use client';

import type { BadgeTone } from './badge';

/**
 * Skeleton — placeholder de carga con shimmer (clase `.skeleton`).
 */
export function Skeleton({ className = '', ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={['skeleton', className].join(' ')} aria-hidden="true" {...rest} />;
}

/**
 * MetricCard — tarjeta de métrica del design system.
 * Mantiene el contrato E2E `.metric-card` / `.metric-label` / `.metric-value`
 * (se aserta count y contenido en dashboard/reportes/caja).
 */
export interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  tone?: 'default' | 'success' | 'warning' | 'danger';
  /** Añade la clase `.money` (valores monetarios, tabular-nums). */
  money?: boolean;
  className?: string;
}

const TONES: Record<NonNullable<MetricCardProps['tone']>, string> = {
  default: '',
  success: 'success',
  warning: 'warning',
  danger: 'danger',
};

export function MetricCard({ label, value, tone = 'default', money = false, className = '' }: MetricCardProps) {
  return (
    <div className={['metric-card', className].join(' ')}>
      <div className="metric-label">{label}</div>
      <div className={['metric-value', TONES[tone], money ? 'money' : ''].join(' ').trim()}>
        {value}
      </div>
    </div>
  );
}

export function Divider({ className = '' }: { className?: string }) {
  return <hr className={['divider', className].join(' ')} />;
}

/**
 * StatusIndicator — punto de estado para listas en vivo.
 */
export function StatusIndicator({ tone, className = '' }: { tone: BadgeTone; className?: string }) {
  const map: Record<BadgeTone, string> = {
    neutral: 'text-textSecondary',
    primary: 'text-primary',
    success: 'text-success',
    warning: 'text-warning',
    danger: 'text-error',
    info: 'text-info',
  };
  return <span aria-hidden="true" className={['status-dot', map[tone], className].join(' ')} />;
}
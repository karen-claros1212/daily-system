'use client';

/**
 * Badge — etiqueta de estado compacta.
 * Mantiene el contrato E2E `.badge` + `.badge-success`/`.badge-warning`
 * (definidos en `@layer components`).
 */
export type BadgeTone = 'neutral' | 'primary' | 'success' | 'warning' | 'danger' | 'info';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  dot?: boolean;
}

const TONES: Record<BadgeTone, string> = {
  neutral: 'badge-neutral',
  primary: 'badge-primary',
  success: 'badge-success',
  warning: 'badge-warning',
  danger: 'badge-danger',
  info: 'badge-info',
};

export function Badge({ tone = 'neutral', dot = false, className = '', children, ...rest }: BadgeProps) {
  return (
    <span className={['badge', TONES[tone], className].join(' ')} {...rest}>
      {dot && <span aria-hidden="true" className="status-dot" />}
      {children}
    </span>
  );
}
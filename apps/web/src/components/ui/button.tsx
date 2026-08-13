'use client';

import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { IconCheck, IconAlert, IconInfo, IconInbox, type IconProps } from './icons';

/**
 * Button — primitive base sobre `elementType` del nodo y las clases
 * `.btn` del design system (ver `@layer components` en globals.css).
 *
 * Acepta un `loading` propio que inyecta un spinner inline y deshabilita la
 * acción (contrato de estados: default / hover / focus-visible / active /
 * disabled / loading).
 */
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'accent' | 'outline' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

const VARIANTS: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'btn-primary',
  accent: 'btn-accent',
  outline: 'btn-outline',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
};

const SIZES: Record<NonNullable<ButtonProps['size']>, string> = {
  sm: 'btn-sm',
  md: '',
  lg: 'btn-lg',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading = false, className = '', disabled, children, ...rest },
  ref,
) {
  const classes = ['btn', VARIANTS[variant], SIZES[size], className]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      ref={ref}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <span aria-hidden="true" className="btn-spinner" />}
      {children}
    </button>
  );
});

/** Botón compacto de icono (tamaño fijo, respeta foco visible). */
export interface IconButtonProps extends IconProps, ButtonHTMLAttributes<HTMLButtonElement> {
  icon: React.ReactNode;
  label: string;
}

export function IconButton({ icon, label, ...rest }: IconButtonProps) {
  return (
    <button type="button" className="icon-btn" aria-label={label} {...rest}>
      {icon}
    </button>
  );
}

/* ── Estados de feedback reutilizables ─────────────────────────────────── */

export interface FlashProps {
  tone?: 'error' | 'success' | 'info' | 'warning';
  icon?: boolean;
  children: React.ReactNode;
  className?: string;
}

const FLASH_TONES: Record<NonNullable<FlashProps['tone']>, string> = {
  error: 'flash-error',
  success: 'flash-success',
  info: 'flash-info',
  warning: 'flash-warning',
};

const FLASH_ICONS = {
  error: IconAlert,
  success: IconCheck,
  info: IconInfo,
  warning: IconAlert,
} as const;

/**
 * Flash — feedback inline (mantiene el contrato E2E `.flash-error`: se usó
 * igual en los specs, solo que ahora con la clase garantizada por el token).
 */
export function Flash({ tone = 'error', icon = true, children, className = '' }: FlashProps) {
  const Icon = FLASH_ICONS[tone];
  return (
    <div className={['flash', FLASH_TONES[tone], className].join(' ')} role="alert">
      {icon && <Icon size={16} aria-hidden="true" className="mt-0.5 flex-shrink-0" />}
      <span>{children}</span>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className = '',
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={['state-box', className].join(' ')}>
      {icon ?? <IconInbox size={28} aria-hidden="true" className="text-textSecondary" />}
      <div>
        <p className="font-semibold">{title}</p>
        {description && (
          <p className="text-sm text-textSecondary mt-1">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function LoadingState({
  label = 'Cargando...',
  className = '',
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div className={['flex items-center gap-2 text-textSecondary', className].join(' ')}>
      <span aria-hidden="true" className="btn-spinner" />
      <span>{label}</span>
    </div>
  );
}
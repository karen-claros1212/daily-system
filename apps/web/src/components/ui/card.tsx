'use client';

/**
 * Card — contenedor base (usa `.card` del design system).
 * `as` permite renderizar como div, article, section… sin duplicar estilos.
 */
export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  padding?: 'md' | 'lg' | 'none';
}

const PADDINGS: Record<NonNullable<CardProps['padding']>, string> = {
  md: 'p-4',
  lg: 'p-6',
  none: '',
};

export function Card({
  elevated = false,
  padding = 'md',
  className = '',
  children,
  ...rest
}: CardProps) {
  return (
    <div
      className={[
        elevated ? 'card-elevated' : 'card',
        PADDINGS[padding],
        className,
      ].join(' ')}
      {...rest}
    >
      {children}
    </div>
  );
}
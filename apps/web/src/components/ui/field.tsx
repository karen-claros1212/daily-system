'use client';

import { useId } from 'react';
import type { InputProps } from './input';

/**
 * Label — etiqueta de campo (usa `.field-label`).
 */
type LabelProps = React.LabelHTMLAttributes<HTMLLabelElement>;

export function Label({ className = '', children, ...rest }: LabelProps) {
  return (
    <label className={['field-label', className].join(' ')} {...rest}>
      {children}
    </label>
  );
}

export type FieldMessageTone = 'error' | 'hint';

/**
 * FormField — envoltura label + control + mensaje con `aria-describedby`,
 * manteniendo `label htmlFor` como contrato E2E (`label[for="activationCode"]`).
 */
export interface FormFieldProps {
  id: string;
  label: string;
  children: React.ReactNode;
  message?: string;
  messageTone?: FieldMessageTone;
  /** El control se renderiza como hijo y ya trae su propio `id`/`invalid`. */
}

export function FormField({ id, label, message, messageTone = 'hint', children }: FormFieldProps) {
  const msgId = useId();
  return (
    <div>
      <Label htmlFor={id}>{label}</Label>
      {children}
      {message && (
        <p
          id={msgId}
          className={['field-message', messageTone === 'error' ? 'field-message-error' : 'field-message-hint'].join(' ')}
        >
          {message}
        </p>
      )}
    </div>
  );
}

export type { InputProps };
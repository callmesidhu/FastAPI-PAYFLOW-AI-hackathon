import type { FC, ReactNode } from 'react';
import { Button } from './Button';

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  action?: ReactNode;
}

export const ErrorState: FC<ErrorStateProps> = ({
  title = 'System Notice',
  message,
  onRetry,
  action,
}) => {
  return (
    <div
      style={{
        padding: '32px',
        backgroundColor: 'var(--color-cream)',
        border: '1px solid var(--color-overdue)',
        borderRadius: 'var(--radius-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
      }}
    >
      <div
        style={{
          fontFamily: 'var(--font-serif)',
          fontSize: '1.25rem',
          letterSpacing: 'var(--tracking-wide)',
          textTransform: 'uppercase',
          fontWeight: 600,
          color: 'var(--color-overdue)',
        }}
      >
        {title}
      </div>
      <p
        style={{
          fontSize: '0.875rem',
          color: 'var(--color-muted)',
          lineHeight: 1.6,
        }}
      >
        {message}
      </p>
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            RETRY ACTION
          </Button>
        )}
        {action}
      </div>
    </div>
  );
};

import type { FC, ReactNode } from 'react';

export type AlertType = 'success' | 'error' | 'warning' | 'info';

export interface AlertProps {
  type?: AlertType;
  title?: string;
  message: string | ReactNode;
  onDismiss?: () => void;
}

export const Alert: FC<AlertProps> = ({ type = 'info', title, message, onDismiss }) => {
  const getColors = () => {
    switch (type) {
      case 'success':
        return {
          bg: 'var(--color-paid-bg)',
          border: '1px solid var(--color-paid)',
          fg: 'var(--color-paid)',
        };
      case 'error':
        return {
          bg: 'var(--color-overdue-bg)',
          border: '1px solid var(--color-overdue)',
          fg: 'var(--color-overdue)',
        };
      case 'warning':
        return {
          bg: 'var(--color-pending-bg)',
          border: '1px solid var(--color-pending)',
          fg: 'var(--color-pending)',
        };
      case 'info':
      default:
        return {
          bg: 'var(--color-cream)',
          border: 'var(--border-hairline)',
          fg: 'var(--color-ink)',
        };
    }
  };

  const colors = getColors();

  return (
    <div
      role="alert"
      style={{
        padding: '16px 20px',
        backgroundColor: colors.bg,
        border: colors.border,
        borderRadius: 'var(--radius-sm)',
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: '16px',
        fontFamily: 'var(--font-sans)',
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {title && (
          <div
            style={{
              fontSize: '0.75rem',
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              fontWeight: 700,
              color: colors.fg,
            }}
          >
            {title}
          </div>
        )}
        <div style={{ fontSize: '0.85rem', color: 'var(--color-ink)', lineHeight: 1.5 }}>{message}</div>
      </div>

      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss alert"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-muted)',
            padding: '2px',
            lineHeight: 1,
            fontSize: '1rem',
          }}
        >
          ×
        </button>
      )}
    </div>
  );
};

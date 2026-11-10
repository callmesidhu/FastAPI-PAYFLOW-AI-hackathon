import type { FC, ReactNode } from 'react';

export interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}

export const EmptyState: FC<EmptyStateProps> = ({ title, description, action, icon }) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '56px 24px',
        backgroundColor: 'var(--color-cream)',
        border: 'var(--border-hairline)',
        borderRadius: 'var(--radius-sm)',
        textAlign: 'center',
      }}
    >
      {icon && (
        <div
          style={{
            color: 'var(--color-muted)',
            marginBottom: '16px',
            opacity: 0.8,
          }}
        >
          {icon}
        </div>
      )}
      <h3
        style={{
          fontFamily: 'var(--font-serif)',
          fontSize: '1.25rem',
          letterSpacing: 'var(--tracking-wide)',
          fontWeight: 600,
          color: 'var(--color-ink)',
          marginBottom: '8px',
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: '0.875rem',
          color: 'var(--color-muted)',
          maxWidth: '420px',
          marginBottom: action ? '24px' : '0',
          lineHeight: 1.5,
        }}
      >
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
};

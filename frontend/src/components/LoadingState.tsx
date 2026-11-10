import type { FC } from 'react';

export interface LoadingStateProps {
  label?: string;
  minHeight?: string;
}

export const LoadingState: FC<LoadingStateProps> = ({
  label = 'PROCESSING REQUEST...',
  minHeight = '280px',
}) => {
  return (
    <div
      style={{
        minHeight,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '16px',
        padding: '32px',
        backgroundColor: 'var(--color-cream)',
        border: 'var(--border-hairline)',
        borderRadius: 'var(--radius-sm)',
      }}
    >
      <div
        style={{
          width: '28px',
          height: '28px',
          border: '2px solid rgba(58, 52, 44, 0.2)',
          borderTopColor: 'var(--color-ink)',
          borderRadius: 'var(--radius-none)',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      <span
        style={{
          fontSize: '0.7rem',
          letterSpacing: 'var(--tracking-widest)',
          textTransform: 'uppercase',
          color: 'var(--color-muted)',
          fontWeight: 600,
        }}
      >
        {label}
      </span>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

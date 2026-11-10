import type { FC } from 'react';

interface LoadingFallbackProps {
  label?: string;
}

export const LoadingFallback: FC<LoadingFallbackProps> = ({
  label = 'INITIALIZING SYSTEM...',
}) => {
  return (
    <div
      style={{
        minHeight: '240px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '16px',
        padding: '32px',
      }}
    >
      <div
        style={{
          width: '24px',
          height: '24px',
          border: '2px solid rgba(58, 52, 44, 0.2)',
          borderTopColor: 'var(--color-ink, #0B0B0B)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
      />
      <span
        style={{
          fontSize: '0.75rem',
          letterSpacing: '0.14em',
          textTransform: 'uppercase',
          color: 'var(--color-muted, #4A4036)',
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

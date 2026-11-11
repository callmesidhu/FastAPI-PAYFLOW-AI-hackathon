import type { FC, ReactNode } from 'react';

export interface PageHeaderProps {
  title: string;
  eyebrow?: string;
  subtitle?: string;
  actions?: ReactNode;
}

export const PageHeader: FC<PageHeaderProps> = ({ title, eyebrow, subtitle, actions }) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        marginBottom: '32px',
        borderBottom: 'var(--border-hairline)',
        paddingBottom: '20px',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          {eyebrow && (
            <div
              style={{
                fontSize: '0.675rem',
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                color: 'var(--color-muted)',
                fontWeight: 600,
                marginBottom: '4px',
              }}
            >
              {eyebrow}
            </div>
          )}
          <h1
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(1.35rem, 4vw, 2rem)',
              letterSpacing: 'var(--tracking-wide)',
              fontWeight: 600,
              color: 'var(--color-ink)',
              margin: 0,
            }}
          >
            {title}
          </h1>
          {subtitle && (
            <p
              style={{
                marginTop: '6px',
                fontSize: '0.875rem',
                color: 'var(--color-muted)',
                maxWidth: '650px',
              }}
            >
              {subtitle}
            </p>
          )}
        </div>

        {actions && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            {actions}
          </div>
        )}
      </div>
    </div>
  );
};

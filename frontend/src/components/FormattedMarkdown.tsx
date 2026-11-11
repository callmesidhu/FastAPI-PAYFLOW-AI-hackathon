import React, { type FC } from 'react';

interface FormattedMarkdownProps {
  content: string;
  style?: React.CSSProperties;
}

export const FormattedMarkdown: FC<FormattedMarkdownProps> = ({ content, style }) => {
  if (!content) return null;

  const lines = content.split('\n');

  const renderInlineFormatted = (text: string) => {
    // Parse bold syntax **text**
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={i} style={{ fontWeight: 600, color: 'var(--color-ink)' }}>
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  return (
    <div
      style={{
        fontSize: '0.875rem',
        lineHeight: 1.7,
        color: 'var(--color-ink)',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        ...style,
      }}
    >
      {lines.map((line, idx) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div key={idx} style={{ height: '4px' }} />;
        }

        // H3 Header: ### Header
        if (trimmed.startsWith('### ')) {
          return (
            <h3
              key={idx}
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.1rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: 'var(--tracking-wide)',
                marginTop: '14px',
                marginBottom: '4px',
                color: 'var(--color-ink)',
                borderBottom: '1px solid rgba(58, 52, 44, 0.15)',
                paddingBottom: '4px',
              }}
            >
              {trimmed.slice(4)}
            </h3>
          );
        }

        // H2 Header: ## Header
        if (trimmed.startsWith('## ')) {
          return (
            <h2
              key={idx}
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.25rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: 'var(--tracking-wide)',
                marginTop: '16px',
                marginBottom: '6px',
                color: 'var(--color-ink)',
              }}
            >
              {trimmed.slice(3)}
            </h2>
          );
        }

        // Bullet point: - item or * item
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                paddingLeft: '6px',
              }}
            >
              <span style={{ color: 'var(--color-muted)', userSelect: 'none' }}>•</span>
              <span style={{ flex: 1 }}>{renderInlineFormatted(trimmed.slice(2))}</span>
            </div>
          );
        }

        // Section header with bold only: **Header:**
        if (trimmed.startsWith('**') && trimmed.endsWith('**') && !trimmed.includes('\n')) {
          return (
            <div
              key={idx}
              style={{
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                fontSize: '0.8rem',
                color: 'var(--color-muted)',
                marginTop: '10px',
              }}
            >
              {trimmed.slice(2, -2)}
            </div>
          );
        }

        // Normal paragraph
        return <p key={idx} style={{ margin: 0 }}>{renderInlineFormatted(trimmed)}</p>;
      })}
    </div>
  );
};

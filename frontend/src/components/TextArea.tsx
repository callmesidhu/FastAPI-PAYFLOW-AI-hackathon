import { forwardRef, type TextareaHTMLAttributes } from 'react';

export interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ label, error, helperText, id, style, className = '', disabled, rows = 3, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
        {label && (
          <label
            htmlFor={inputId}
            style={{
              fontSize: '0.675rem',
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              fontWeight: 600,
              color: error ? 'var(--color-overdue)' : 'var(--color-muted)',
            }}
          >
            {label}
          </label>
        )}

        <textarea
          ref={ref}
          id={inputId}
          disabled={disabled}
          rows={rows}
          style={{
            width: '100%',
            backgroundColor: disabled ? 'var(--color-cream)' : 'var(--color-white)',
            border: error ? '1px solid var(--color-overdue)' : 'var(--border-hairline)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            fontFamily: 'var(--font-sans)',
            fontSize: '0.85rem',
            color: 'var(--color-ink)',
            outline: 'none',
            resize: 'vertical',
            transition: 'border-color var(--transition-fast)',
            ...style,
          }}
          className={`payflow-textarea ${className}`}
          {...props}
        />

        {error ? (
          <span style={{ fontSize: '0.7rem', color: 'var(--color-overdue)' }}>{error}</span>
        ) : helperText ? (
          <span style={{ fontSize: '0.7rem', color: 'var(--color-muted)' }}>{helperText}</span>
        ) : null}
      </div>
    );
  }
);

TextArea.displayName = 'TextArea';

import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';

export interface TextInputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
  ({ label, error, helperText, leftIcon, rightIcon, id, style, className = '', disabled, ...props }, ref) => {
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

        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', width: '100%' }}>
          {leftIcon && (
            <div
              style={{
                position: 'absolute',
                left: '12px',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--color-muted)',
                pointerEvents: 'none',
              }}
            >
              {leftIcon}
            </div>
          )}

          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            style={{
              width: '100%',
              backgroundColor: disabled ? 'var(--color-cream)' : 'var(--color-white)',
              border: error ? '1px solid var(--color-overdue)' : 'var(--border-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: leftIcon ? '10px 12px 10px 36px' : rightIcon ? '10px 36px 10px 12px' : '10px 12px',
              fontFamily: 'var(--font-sans)',
              fontSize: '0.85rem',
              color: 'var(--color-ink)',
              outline: 'none',
              transition: 'border-color var(--transition-fast)',
              ...style,
            }}
            className={`payflow-input ${className}`}
            {...props}
          />

          {rightIcon && (
            <div
              style={{
                position: 'absolute',
                right: '12px',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--color-muted)',
              }}
            >
              {rightIcon}
            </div>
          )}
        </div>

        {error ? (
          <span style={{ fontSize: '0.7rem', color: 'var(--color-overdue)' }}>{error}</span>
        ) : helperText ? (
          <span style={{ fontSize: '0.7rem', color: 'var(--color-muted)' }}>{helperText}</span>
        ) : null}
      </div>
    );
  }
);

TextInput.displayName = 'TextInput';

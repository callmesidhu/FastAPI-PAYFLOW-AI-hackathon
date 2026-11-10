import { forwardRef, type SelectHTMLAttributes } from 'react';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: SelectOption[];
  error?: string;
  helperText?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, options, error, helperText, id, style, className = '', disabled, ...props }, ref) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
        {label && (
          <label
            htmlFor={selectId}
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

        <div style={{ position: 'relative', width: '100%' }}>
          <select
            ref={ref}
            id={selectId}
            disabled={disabled}
            style={{
              width: '100%',
              backgroundColor: disabled ? 'var(--color-cream)' : 'var(--color-white)',
              border: error ? '1px solid var(--color-overdue)' : 'var(--border-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '10px 36px 10px 12px',
              fontFamily: 'var(--font-sans)',
              fontSize: '0.85rem',
              color: 'var(--color-ink)',
              outline: 'none',
              appearance: 'none',
              cursor: disabled ? 'not-allowed' : 'pointer',
              transition: 'border-color var(--transition-fast)',
              ...style,
            }}
            className={`payflow-select ${className}`}
            {...props}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                {opt.label}
              </option>
            ))}
          </select>

          {/* Custom hairline chevron arrow */}
          <div
            style={{
              position: 'absolute',
              right: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              pointerEvents: 'none',
              color: 'var(--color-muted)',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
              <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="square" />
            </svg>
          </div>
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

Select.displayName = 'Select';

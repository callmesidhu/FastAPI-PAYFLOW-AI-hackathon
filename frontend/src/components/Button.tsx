import type { ButtonHTMLAttributes, FC, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
}

export const Button: FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  disabled,
  style,
  className = '',
  ...props
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'primary':
        return {
          backgroundColor: 'var(--color-ink)',
          color: 'var(--color-bg)',
          border: '1px solid var(--color-ink)',
        };
      case 'secondary':
        return {
          backgroundColor: 'var(--color-cream)',
          color: 'var(--color-ink)',
          border: 'var(--border-hairline)',
        };
      case 'outline':
        return {
          backgroundColor: 'transparent',
          color: 'var(--color-ink)',
          border: 'var(--border-hairline)',
        };
      case 'danger':
        return {
          backgroundColor: 'var(--color-overdue)',
          color: '#FFFFFF',
          border: '1px solid var(--color-overdue)',
        };
    }
  };

  const getSizeStyles = (): React.CSSProperties => {
    switch (size) {
      case 'sm':
        return {
          padding: '6px 12px',
          fontSize: '0.7rem',
          letterSpacing: 'var(--tracking-wider)',
        };
      case 'md':
        return {
          padding: '10px 18px',
          fontSize: '0.75rem',
          letterSpacing: 'var(--tracking-wide)',
        };
      case 'lg':
        return {
          padding: '14px 26px',
          fontSize: '0.825rem',
          letterSpacing: 'var(--tracking-wide)',
        };
    }
  };

  const baseStyles: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    fontFamily: 'var(--font-sans)',
    fontWeight: 600,
    textTransform: 'uppercase',
    borderRadius: 'var(--radius-sm)',
    cursor: disabled || isLoading ? 'not-allowed' : 'pointer',
    opacity: disabled || isLoading ? 0.6 : 1,
    transition: 'background-color var(--transition-fast), color var(--transition-fast)',
    ...getVariantStyles(),
    ...getSizeStyles(),
    ...style,
  };

  return (
    <button
      disabled={disabled || isLoading}
      style={baseStyles}
      className={`payflow-btn payflow-btn-${variant} ${className}`}
      {...props}
    >
      {isLoading ? (
        <span
          style={{
            width: '12px',
            height: '12px',
            border: '2px solid currentColor',
            borderTopColor: 'transparent',
            borderRadius: '50%',
            animation: 'spin 0.6s linear infinite',
            display: 'inline-block',
          }}
        />
      ) : (
        leftIcon
      )}
      {children}
      {!isLoading && rightIcon}
    </button>
  );
};

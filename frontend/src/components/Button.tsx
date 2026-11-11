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
          color: '#FAF7F2',
          border: '1px solid var(--color-ink)',
          boxShadow: '0 2px 4px rgba(11, 11, 11, 0.12)',
        };
      case 'secondary':
        return {
          backgroundColor: '#FFFFFF',
          color: 'var(--color-ink)',
          border: '1px solid var(--color-hairline)',
          boxShadow: '0 1px 2px rgba(11, 11, 11, 0.04)',
        };
      case 'outline':
        return {
          backgroundColor: 'transparent',
          color: 'var(--color-ink)',
          border: '1px solid var(--color-hairline)',
        };
      case 'danger':
        return {
          backgroundColor: 'var(--color-overdue)',
          color: '#FFFFFF',
          border: '1px solid var(--color-overdue)',
          boxShadow: '0 2px 4px rgba(158, 71, 56, 0.2)',
        };
    }
  };

  const getSizeStyles = (): React.CSSProperties => {
    switch (size) {
      case 'sm':
        return {
          padding: '7px 14px',
          fontSize: '0.7rem',
          letterSpacing: 'var(--tracking-wider)',
        };
      case 'md':
        return {
          padding: '11px 20px',
          fontSize: '0.75rem',
          letterSpacing: 'var(--tracking-wide)',
        };
      case 'lg':
        return {
          padding: '13px 24px',
          fontSize: '0.8rem',
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
    transition: 'all var(--transition-fast)',
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

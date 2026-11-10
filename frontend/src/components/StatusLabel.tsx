import type { FC } from 'react';

export type InvoiceStatusType =
  | 'draft'
  | 'pending_approval'
  | 'created'
  | 'sent'
  | 'unpaid'
  | 'partially_paid'
  | 'paid'
  | 'overdue'
  | 'cancelled'
  | 'failed';

export interface StatusLabelProps {
  status: InvoiceStatusType | string;
  size?: 'sm' | 'md';
}

export const StatusLabel: FC<StatusLabelProps> = ({ status, size = 'md' }) => {
  const normalized = status.toLowerCase();

  const getStatusConfig = () => {
    switch (normalized) {
      case 'paid':
        return {
          bg: 'var(--color-paid-bg)',
          fg: 'var(--color-paid)',
          border: '1px solid var(--color-paid)',
          label: 'PAID',
        };
      case 'pending':
      case 'pending_approval':
        return {
          bg: 'var(--color-pending-bg)',
          fg: 'var(--color-pending)',
          border: '1px solid var(--color-pending)',
          label: normalized === 'pending_approval' ? 'PENDING APPROVAL' : 'PENDING',
        };
      case 'overdue':
        return {
          bg: 'var(--color-overdue-bg)',
          fg: 'var(--color-overdue)',
          border: '1px solid var(--color-overdue)',
          label: 'OVERDUE',
        };
      case 'sent':
      case 'created':
      case 'unpaid':
        return {
          bg: 'rgba(58, 52, 44, 0.08)',
          fg: 'var(--color-ink)',
          border: 'var(--border-hairline)',
          label: normalized.toUpperCase(),
        };
      case 'cancelled':
      case 'failed':
        return {
          bg: 'rgba(140, 74, 63, 0.1)',
          fg: 'var(--color-overdue)',
          border: '1px solid var(--color-overdue)',
          label: normalized.toUpperCase(),
        };
      case 'draft':
      default:
        return {
          bg: 'var(--color-cream)',
          fg: 'var(--color-muted)',
          border: 'var(--border-subtle)',
          label: normalized.toUpperCase().replace(/_/g, ' '),
        };
    }
  };

  const config = getStatusConfig();

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: size === 'sm' ? '2px 6px' : '4px 8px',
        fontSize: size === 'sm' ? '0.625rem' : '0.675rem',
        fontWeight: 600,
        fontFamily: 'var(--font-sans)',
        letterSpacing: 'var(--tracking-wider)',
        textTransform: 'uppercase',
        backgroundColor: config.bg,
        color: config.fg,
        border: config.border,
        /* Strict square geometry — maximum 2px radius, NOT a pill! */
        borderRadius: 'var(--radius-sm)',
        lineHeight: 1,
      }}
      className={`payflow-status-label status-${normalized}`}
    >
      {config.label}
    </span>
  );
};

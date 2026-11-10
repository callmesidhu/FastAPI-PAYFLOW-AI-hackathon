import type { FC } from 'react';
import { PageHeader, StatusLabel } from '../../components';
import { useAuth } from '../../lib/auth-context';

export const SettingsView: FC = () => {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader
        eyebrow="CONFIGURATION & INTEGRATIONS"
        title="Settings & Diagnostics"
        subtitle="Operational parameters, PayPal Developer Sandbox configuration, and account profile."
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Profile Card */}
        <div
          style={{
            backgroundColor: 'var(--color-cream)',
            border: 'var(--border-hairline)',
            borderRadius: 'var(--radius-sm)',
            padding: '24px',
          }}
        >
          <div
            style={{
              fontSize: '0.75rem',
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              fontWeight: 700,
              marginBottom: '16px',
            }}
          >
            Business Owner Profile
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>NAME</div>
              <div style={{ fontWeight: 600 }}>{user?.name}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>EMAIL</div>
              <div style={{ fontWeight: 600 }}>{user?.email}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>STUDIO / BUSINESS</div>
              <div style={{ fontWeight: 600 }}>{user?.business_name || '—'}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>ACCOUNT STATUS</div>
              <div style={{ marginTop: '2px' }}>
                <StatusLabel status="paid" size="sm" />
              </div>
            </div>
          </div>
        </div>

        {/* Integration Diagnostics Card */}
        <div
          style={{
            backgroundColor: 'var(--color-cream)',
            border: 'var(--border-hairline)',
            borderRadius: 'var(--radius-sm)',
            padding: '24px',
          }}
        >
          <div
            style={{
              fontSize: '0.75rem',
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              fontWeight: 700,
              marginBottom: '16px',
            }}
          >
            System & Environment Invariants
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.825rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(58, 52, 44, 0.15)', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-muted)' }}>PayPal REST API Target</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>https://api-m.sandbox.paypal.com</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(58, 52, 44, 0.15)', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-muted)' }}>Financial Calculations</span>
              <span style={{ fontWeight: 600 }}>Python Decimal (0 floating-point arithmetic)</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(58, 52, 44, 0.15)', paddingBottom: '8px' }}>
              <span style={{ color: 'var(--color-muted)' }}>Multi-Tenant Data Isolation</span>
              <span style={{ fontWeight: 600 }}>Strict user_id filter on all DB queries</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--color-muted)' }}>Password Cryptography</span>
              <span style={{ fontWeight: 600 }}>Argon2id (time_cost=2, memory=100MiB, p=8)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

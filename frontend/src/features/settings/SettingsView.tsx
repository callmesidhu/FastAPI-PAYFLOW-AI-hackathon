import { useEffect, useState, type FC } from 'react';
import { Button, PageHeader, StatusLabel } from '../../components';
import { apiClient } from '../../lib/api-client';
import { useAuth } from '../../lib/auth-context';

interface PayPalDiagnosticStatus {
  configured: boolean;
  connected: boolean;
  environment: string;
  base_url: string;
  webhook_configured: boolean;
  token_masked?: string | null;
  message: string;
}

interface SystemDiagnosticsResponse {
  status: string;
  timestamp: string;
  environment: string;
  services: {
    backend: { status: string; app: string; version: string };
    database: { status: string; database_name: string };
    paypal_sandbox: {
      configured: boolean;
      connected: boolean;
      target_host: string;
      webhook_configured: boolean;
      message: string;
    };
    ai_provider: {
      provider: string;
      model: string;
      configured: boolean;
      fallback_mode: boolean;
      status: string;
    };
  };
  metrics: {
    api: { total_requests: number; errors_by_category: Record<string, number>; error_rate_pct: number };
    paypal: { total_calls: number; failures_by_category: Record<string, number> };
    ai_provider: { total_calls: number; failures_by_category: Record<string, number> };
    webhooks: { total_events: number; verification_failures: Record<string, number> };
    scheduler: { total_runs: number; failures_by_category: Record<string, number> };
  };
  recovery_guidance: {
    ai_unavailable: string;
    paypal_unavailable: string;
    webhook_failure: string;
    database_interruption: string;
  };
}

export const SettingsView: FC = () => {
  const { user } = useAuth();
  const [paypalStatus, setPaypalStatus] = useState<PayPalDiagnosticStatus | null>(null);
  const [checkingPaypal, setCheckingPaypal] = useState<boolean>(false);
  const [checkError, setCheckError] = useState<string | null>(null);

  const [diagnostics, setDiagnostics] = useState<SystemDiagnosticsResponse | null>(null);
  const [loadingDiag, setLoadingDiag] = useState<boolean>(false);

  const fetchPayPalStatus = async () => {
    try {
      setCheckingPaypal(true);
      setCheckError(null);
      const data = await apiClient<PayPalDiagnosticStatus>('/api/paypal/status');
      setPaypalStatus(data);
    } catch (err: any) {
      console.warn('PayPal status diagnostic failed:', err);
      setCheckError(err.message || 'Unable to check PayPal connectivity.');
    } finally {
      setCheckingPaypal(false);
    }
  };

  const fetchDiagnostics = async () => {
    try {
      setLoadingDiag(true);
      const data = await apiClient<SystemDiagnosticsResponse>('/api/diagnostics');
      setDiagnostics(data);
    } catch (err: any) {
      console.warn('Diagnostics telemetry failed:', err);
    } finally {
      setLoadingDiag(false);
    }
  };

  useEffect(() => {
    void fetchPayPalStatus();
    void fetchDiagnostics();
  }, []);

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

        {/* PayPal Developer Sandbox Diagnostic Card */}
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
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: '0.75rem',
                  letterSpacing: 'var(--tracking-wider)',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                }}
              >
                PayPal Developer Sandbox Diagnostics
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', marginTop: '2px' }}>
                Verified against official PayPal REST API (OAuth 2.0 Client Credentials & Invoicing v2)
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void fetchPayPalStatus()}
              disabled={checkingPaypal}
            >
              {checkingPaypal ? 'CHECKING...' : 'RE-CHECK CONNECTION'}
            </Button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>CONNECTIVITY</div>
              <div style={{ marginTop: '4px' }}>
                {checkingPaypal ? (
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-muted)' }}>Probing sandbox...</span>
                ) : paypalStatus?.connected ? (
                  <StatusLabel status="paid" label="CONNECTED (SANDBOX ACTIVE)" size="sm" />
                ) : (
                  <StatusLabel status="pending" label={paypalStatus?.configured ? "AUTHENTICATION PENDING" : "CREDENTIALS NEEDED"} size="sm" />
                )}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>ENVIRONMENT</div>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginTop: '2px' }}>
                Official PayPal Sandbox
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>TARGET REST HOST</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', fontWeight: 600, marginTop: '2px' }}>
                {paypalStatus?.base_url || 'https://api-m.sandbox.paypal.com'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>OAUTH TOKEN STATUS</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', marginTop: '2px' }}>
                {paypalStatus?.token_masked ? (
                  <span style={{ color: 'var(--color-paid)', fontWeight: 600 }}>Bearer {paypalStatus.token_masked}</span>
                ) : (
                  <span style={{ color: 'var(--color-muted)' }}>Not acquired</span>
                )}
              </div>
            </div>
          </div>

          <div
            style={{
              padding: '12px 16px',
              backgroundColor: 'var(--color-sand)',
              border: 'var(--border-hairline)',
              fontSize: '0.75rem',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <span style={{ fontWeight: 600 }}>Diagnostics message: </span>
              <span>{checkError || paypalStatus?.message || 'Probing sandbox credentials...'}</span>
            </div>
            <div style={{ fontSize: '0.7rem', color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-wide)' }}>
              Webhook: {paypalStatus?.webhook_configured ? 'Configured ✓' : 'Not Set (Optional)'}
            </div>
          </div>
        </div>

        {/* Operational Observability & Diagnostics Card (Prompt 40) */}
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
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '16px',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: '0.75rem',
                  letterSpacing: 'var(--tracking-wider)',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                }}
              >
                Operational Observability & Safe Telemetry
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', marginTop: '2px' }}>
                Protected system telemetry, AI provider status, and categorized error counters (Zero PII or secrets logged).
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void fetchDiagnostics()}
              disabled={loadingDiag}
            >
              {loadingDiag ? 'REFRESHING...' : 'REFRESH TELEMETRY'}
            </Button>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '16px',
              marginBottom: '20px',
            }}
          >
            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>AI PROVIDER STATUS</div>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', marginTop: '2px' }}>
                {diagnostics?.services.ai_provider.provider.toUpperCase() || 'GEMINI'}{' '}
                <span style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                  ({diagnostics?.services.ai_provider.model})
                </span>
              </div>
              <div style={{ marginTop: '4px' }}>
                <StatusLabel
                  status={diagnostics?.services.ai_provider.fallback_mode ? 'pending' : 'paid'}
                  label={diagnostics?.services.ai_provider.fallback_mode ? 'FALLBACK MOCK ACTIVE' : 'PROVIDER CONNECTED'}
                  size="sm"
                />
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>TOTAL API REQUESTS</div>
              <div style={{ fontWeight: 700, fontSize: '1.1rem', fontFamily: 'var(--font-serif)', marginTop: '2px' }}>
                {diagnostics?.metrics.api.total_requests ?? 0}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-muted)', marginTop: '2px' }}>
                Error rate: {diagnostics?.metrics.api.error_rate_pct ?? 0}%
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>PAYPAL SANDBOX CALLS</div>
              <div style={{ fontWeight: 700, fontSize: '1.1rem', fontFamily: 'var(--font-serif)', marginTop: '2px' }}>
                {diagnostics?.metrics.paypal.total_calls ?? 0}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-muted)', marginTop: '2px' }}>
                Failures: {Object.keys(diagnostics?.metrics.paypal.failures_by_category || {}).length}
              </div>
            </div>

            <div>
              <div style={{ fontSize: '0.675rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)' }}>WEBHOOK VERIFICATIONS</div>
              <div style={{ fontWeight: 700, fontSize: '1.1rem', fontFamily: 'var(--font-serif)', marginTop: '2px' }}>
                {diagnostics?.metrics.webhooks.total_events ?? 0}
              </div>
              <div style={{ fontSize: '0.7rem', color: 'var(--color-muted)', marginTop: '2px' }}>
                Rejections: {Object.keys(diagnostics?.metrics.webhooks.verification_failures || {}).length}
              </div>
            </div>
          </div>

          {/* Incident Recovery Guidance (Prompt 40) */}
          <div
            style={{
              padding: '16px',
              backgroundColor: 'var(--color-sand)',
              border: 'var(--border-hairline)',
              borderRadius: 'var(--radius-sm)',
            }}
          >
            <div
              style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: 'var(--tracking-wide)',
                marginBottom: '10px',
              }}
            >
              Incident Recovery & Graceful Degradation Protocols
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.775rem', lineHeight: 1.5 }}>
              <div>
                <strong>• If AI Provider Outage Occurs:</strong> Manual invoice creation at <code>/invoices/new</code> remains 100% operational. The system does not block invoice issuance or PayPal dispatch if LLM APIs fail.
              </div>
              <div>
                <strong>• If PayPal Sandbox Unreachable:</strong> Invoices remain securely persisted as local drafts with approval locks intact. Merged states re-sync automatically upon network restoration.
              </div>
              <div>
                <strong>• If Webhook Verification Fails:</strong> Incoming unverified payloads are dropped without state mutation. Reconcile verified state at any time via manual status query.
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

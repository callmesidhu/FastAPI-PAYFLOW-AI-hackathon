import { useEffect, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, DataTable, EmptyState, LoadingState, PageHeader, StatusLabel } from '../../components';
import { apiClient } from '../../lib/api-client';
import { useAuth } from '../../lib/auth-context';

interface CurrencySummary {
  currency: string;
  outstanding: string;
  overdue: string;
  collected_this_month: string;
}

interface InvoiceDetail {
  internal_id: string;
  invoice_number: string;
  customer_id: string;
  total: string;
  currency: string;
  due_date: string;
  status: string;
}

interface DashboardSummary {
  total_invoices: number;
  draft_count: number;
  pending_approval_count: number;
  sent_count: number;
  paid_count: number;
  overdue_count: number;
  by_currency: CurrencySummary[];
  attention_needed: InvoiceDetail[];
  recent_invoices: InvoiceDetail[];
  collections_trend: Array<{ period: string; amount: string; currency: string }>;
  has_trend_data: boolean;
}

export const DashboardView: FC = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async () => {
    try {
      setIsLoading(true);
      const res = await apiClient<DashboardSummary>('/api/dashboard/summary');
      setData(res);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to reconcile receivables summary.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow={`ORGANIZATION // ${user?.business_name || user?.name?.toUpperCase() || 'STUDIO'}`}
        title="Receivables Dashboard"
        subtitle="Real-time accounts receivable overview. Monetary totals reconcile authoritatively with backend records."
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button variant="outline" size="sm" onClick={() => navigate('/assistant')}>
              AI ASSISTANT
            </Button>
            <Button variant="primary" size="sm" onClick={() => navigate('/invoices')}>
              + NEW DRAFT
            </Button>
          </div>
        }
      />

      {/* Black Feature Card with Centered Uppercase Text & Inset Hairline Border */}
      <section
        style={{
          backgroundColor: 'var(--color-ink)',
          color: 'var(--color-bg)',
          padding: '36px 32px',
          border: 'var(--border-hairline)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: '32px',
          position: 'relative',
          textAlign: 'center',
        }}
      >
        <div
          style={{
            border: '1px solid rgba(217, 207, 186, 0.3)',
            padding: '24px 32px',
            borderRadius: 'var(--radius-sm)',
            maxWidth: '720px',
            margin: '0 auto',
          }}
        >
          <div
            style={{
              fontSize: '0.675rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--color-sand)',
              marginBottom: '8px',
            }}
          >
            ACCOUNTS RECEIVABLE CONTROL OVERVIEW • PAYPAL SANDBOX
          </div>
          <h2
            style={{
              color: '#FAF7F2',
              fontSize: '1.65rem',
              margin: '0 0 10px 0',
              fontFamily: 'var(--font-serif)',
              letterSpacing: 'var(--tracking-wide)',
            }}
          >
            {user?.business_name ? `${user.business_name.toUpperCase()}` : `${user?.name?.toUpperCase()} STUDIO`}
          </h2>
          <p
            style={{
              color: 'var(--color-sand)',
              fontSize: '0.85rem',
              lineHeight: 1.6,
              maxWidth: '560px',
              margin: '0 auto',
            }}
          >
            ALL TRANSACTIONS ARE RESTRICTED TO THE PAYPAL SANDBOX API. INVOICE CREATION, DISPATCH, AND
            FOLLOW-UP REMINDERS REQUIRE YOUR EXPLICIT HUMAN AUTHORIZATION.
          </p>
        </div>
      </section>

      {isLoading ? (
        <LoadingState label="RECONCILING RECEIVABLES LEDGER..." />
      ) : error ? (
        <EmptyState
          title="Diagnostic Notice"
          description={error}
          action={
            <Button variant="secondary" size="sm" onClick={() => void loadDashboard()}>
              RETRY RECONCILIATION
            </Button>
          }
        />
      ) : !data ? null : (
        <>
          {/* Summary Metric Blocks with Strict Per-Currency Separation */}
          <div style={{ marginBottom: '32px' }}>
            <div
              style={{
                fontSize: '0.7rem',
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-muted)',
                marginBottom: '12px',
              }}
            >
              Receivables Reconciliation by Currency
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: '16px',
              }}
            >
              {data.by_currency.map((c) => (
                <div
                  key={c.currency}
                  style={{
                    backgroundColor: 'var(--color-cream)',
                    border: 'var(--border-hairline)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '24px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '16px',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      borderBottom: 'var(--border-hairline)',
                      paddingBottom: '10px',
                    }}
                  >
                    <span
                      style={{
                        fontFamily: 'var(--font-serif)',
                        fontWeight: 700,
                        fontSize: '1.1rem',
                        letterSpacing: 'var(--tracking-wide)',
                      }}
                    >
                      {c.currency} PORTFOLIO
                    </span>
                    <span
                      style={{
                        fontSize: '0.675rem',
                        letterSpacing: 'var(--tracking-widest)',
                        color: 'var(--color-muted)',
                      }}
                    >
                      ISO 4217
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                    <div>
                      <div style={{ fontSize: '0.625rem', letterSpacing: 'var(--tracking-wider)', color: 'var(--color-muted)', textTransform: 'uppercase' }}>
                        OUTSTANDING
                      </div>
                      <div
                        style={{
                          fontSize: '1.4rem',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          color: 'var(--color-pending)',
                          marginTop: '2px',
                        }}
                      >
                        ${c.outstanding}
                      </div>
                    </div>

                    <div>
                      <div style={{ fontSize: '0.625rem', letterSpacing: 'var(--tracking-wider)', color: 'var(--color-overdue)', textTransform: 'uppercase' }}>
                        OVERDUE
                      </div>
                      <div
                        style={{
                          fontSize: '1.4rem',
                          fontFamily: 'var(--font-mono)',
                          fontWeight: 700,
                          color: 'var(--color-overdue)',
                          marginTop: '2px',
                        }}
                      >
                        ${c.overdue}
                      </div>
                    </div>
                  </div>

                  <div
                    style={{
                      borderTop: '1px solid rgba(58, 52, 44, 0.15)',
                      paddingTop: '10px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ fontSize: '0.675rem', color: 'var(--color-muted)', textTransform: 'uppercase', letterSpacing: 'var(--tracking-wide)' }}>
                      Collected This Month
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--color-paid)' }}>
                      ${c.collected_this_month}
                    </span>
                  </div>
                </div>
              ))}

              {/* Invoice Counts Block */}
              <div
                style={{
                  backgroundColor: 'var(--color-sand)',
                  border: 'var(--border-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div
                  style={{
                    fontSize: '0.7rem',
                    letterSpacing: 'var(--tracking-wider)',
                    textTransform: 'uppercase',
                    fontWeight: 700,
                    color: 'var(--color-muted)',
                    borderBottom: 'var(--border-hairline)',
                    paddingBottom: '10px',
                    marginBottom: '12px',
                  }}
                >
                  Portfolio Volume
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.8rem' }}>
                  <div>
                    <span style={{ color: 'var(--color-muted)' }}>Total Invoices:</span>{' '}
                    <strong>{data.total_invoices}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-muted)' }}>Pending Send:</span>{' '}
                    <strong>{data.pending_approval_count}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-muted)' }}>Sent / Unpaid:</span>{' '}
                    <strong>{data.sent_count}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--color-muted)' }}>Overdue:</span>{' '}
                    <strong style={{ color: 'var(--color-overdue)' }}>{data.overdue_count}</strong>
                  </div>
                </div>
                <div style={{ marginTop: '16px' }}>
                  <Button
                    variant="outline"
                    size="sm"
                    style={{ width: '100%' }}
                    onClick={() => navigate('/invoices')}
                  >
                    VIEW INVOICE DIRECTORY →
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* Attention Needed Section */}
          <div style={{ marginBottom: '32px' }}>
            <div
              style={{
                fontSize: '0.75rem',
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-overdue)',
                marginBottom: '12px',
              }}
            >
              Attention Required
            </div>

            {data.attention_needed.length === 0 ? (
              <div
                style={{
                  padding: '20px',
                  backgroundColor: 'var(--color-cream)',
                  border: 'var(--border-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.85rem',
                  color: 'var(--color-muted)',
                }}
              >
                No invoices currently overdue or pending approval. All accounts are in good standing.
              </div>
            ) : (
              <DataTable<InvoiceDetail>
                columns={[
                  { key: 'invoice_number', header: 'Reference', width: '180px' },
                  { key: 'customer_id', header: 'Customer ID' },
                  {
                    key: 'total',
                    header: 'Amount',
                    align: 'right',
                    render: (it) => (
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {it.currency} ${it.total}
                      </span>
                    ),
                  },
                  { key: 'due_date', header: 'Due Date', width: '140px' },
                  {
                    key: 'status',
                    header: 'Status',
                    width: '180px',
                    render: (it) => <StatusLabel status={it.status} size="sm" />,
                  },
                ]}
                data={data.attention_needed}
                keyExtractor={(it) => it.internal_id}
                onRowClick={(it) => navigate(`/invoices?id=${it.internal_id}`)}
              />
            )}
          </div>

          {/* Recent Invoices & Collections Trend */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
              gap: '24px',
            }}
          >
            {/* Recent Invoices Column */}
            <div>
              <div
                style={{
                  fontSize: '0.75rem',
                  letterSpacing: 'var(--tracking-wider)',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                  marginBottom: '12px',
                }}
              >
                Recent Invoices
              </div>

              {data.recent_invoices.length === 0 ? (
                <EmptyState
                  title="No Invoices Yet"
                  description="When invoices are created, they will appear here in chronological order."
                />
              ) : (
                <DataTable<InvoiceDetail>
                  columns={[
                    { key: 'invoice_number', header: 'Invoice', width: '140px' },
                    {
                      key: 'total',
                      header: 'Amount',
                      align: 'right',
                      render: (it) => (
                        <span style={{ fontFamily: 'var(--font-mono)' }}>
                          {it.currency} ${it.total}
                        </span>
                      ),
                    },
                    {
                      key: 'status',
                      header: 'Status',
                      width: '140px',
                      render: (it) => <StatusLabel status={it.status} size="sm" />,
                    },
                  ]}
                  data={data.recent_invoices}
                  keyExtractor={(it) => it.internal_id}
                  onRowClick={(it) => navigate(`/invoices?id=${it.internal_id}`)}
                />
              )}
            </div>

            {/* Collections Trend Column */}
            <div>
              <div
                style={{
                  fontSize: '0.75rem',
                  letterSpacing: 'var(--tracking-wider)',
                  textTransform: 'uppercase',
                  fontWeight: 700,
                  marginBottom: '12px',
                }}
              >
                Collections Velocity Trend
              </div>

              {!data.has_trend_data ? (
                <EmptyState
                  title="Insufficient Historical Volume"
                  description="A collections trend requires at least 3 months of verified payment settlements. As payments are verified via PayPal Sandbox, settlement velocity will graph here."
                />
              ) : (
                <div
                  style={{
                    backgroundColor: 'var(--color-cream)',
                    border: 'var(--border-hairline)',
                    padding: '24px',
                  }}
                >
                  Trend data available.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

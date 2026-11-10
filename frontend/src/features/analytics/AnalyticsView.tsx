import { useEffect, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { AgCustomerBalanceGrid, Button, EmptyState, LoadingState, PageHeader } from '../../components';
import { apiClient } from '../../lib/api-client';

interface AgingBucketDetail {
  amount: string;
  count: number;
  invoice_numbers: string[];
}

interface AgingBuckets {
  bucket_0_7_days: AgingBucketDetail;
  bucket_8_30_days: AgingBucketDetail;
  bucket_31_60_days: AgingBucketDetail;
  bucket_60_plus_days: AgingBucketDetail;
}

interface CurrencyAnalytics {
  currency: string;
  total_outstanding: string;
  total_overdue: string;
  total_collected_period: string;
  open_invoices_count: number;
  overdue_invoices_count: number;
  paid_invoices_count: number;
  aging_buckets: AgingBuckets;
}

interface CustomerBalance {
  customer_id: string;
  customer_name: string;
  customer_email: string;
  currency: string;
  outstanding_amount: string;
  overdue_amount: string;
  open_invoices_count: number;
  invoice_numbers: string[];
}

interface ReceivablesAnalyticsResponse {
  period_start: string;
  period_end: string;
  timezone: string;
  by_currency: CurrencyAnalytics[];
  customer_balances: CustomerBalance[];
  has_data: boolean;
}

interface AISummaryResponse {
  summary: string;
  has_sufficient_data: boolean;
  insufficient_data_reason?: string | null;
  payment_velocity_estimate?: string | null;
  by_currency: Array<Record<string, unknown>>;
  analyzed_at: string;
}

export const AnalyticsView: FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [analytics, setAnalytics] = useState<ReceivablesAnalyticsResponse | null>(null);
  const [aiSummary, setAiSummary] = useState<AISummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState<string>('ALL');
  const [periodPreset, setPeriodPreset] = useState<'30' | '90' | '365'>('30');
  const [balanceViewMode, setBalanceViewMode] = useState<'ag-grid' | 'table'>('ag-grid');
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const today = new Date();
      const endStr = today.toISOString().split('T')[0] || '';
      const startD = new Date(today);
      startD.setDate(startD.getDate() - parseInt(periodPreset, 10));
      const startStr = startD.toISOString().split('T')[0] || '';

      const data = await apiClient<ReceivablesAnalyticsResponse>(
        `/api/analytics/receivables?start_date=${startStr}&end_date=${endStr}&timezone=UTC`
      );
      setAnalytics(data);

      // Trigger AI summary
      fetchAiSummary(startStr, endStr);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load receivables analytics.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const fetchAiSummary = async (startStr: string, endStr: string) => {
    setSummaryLoading(true);
    try {
      const summary = await apiClient<AISummaryResponse>('/api/analytics/ai-summary', {
        method: 'POST',
        body: JSON.stringify({
          start_date: startStr,
          end_date: endStr,
          timezone: 'UTC',
        }),
      });
      setAiSummary(summary);
    } catch {
      // AI summary non-blocking
    } finally {
      setSummaryLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, [periodPreset]);

  if (loading) {
    return <LoadingState label="Aggregating authoritative receivables ledgers..." />;
  }

  const currencies = analytics?.by_currency || [];
  const displayCurrencies =
    selectedCurrency === 'ALL'
      ? currencies
      : currencies.filter((c) => c.currency === selectedCurrency);

  const customerBalances = analytics?.customer_balances || [];
  const displayCustomerBalances =
    selectedCurrency === 'ALL'
      ? customerBalances
      : customerBalances.filter((cb) => cb.currency === selectedCurrency);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <PageHeader
          eyebrow="FINANCIAL INTELLIGENCE"
          title="Receivables Analytics"
          subtitle="Timezone-aware aging schedules (0–7, 8–30, 31–60, 60+ days), per-currency totals, and factual AI audit summaries."
        />
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', paddingTop: '10px' }}>
          {/* Period Preset Selector */}
          <div style={{ display: 'flex', border: 'var(--border-hairline)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
            <button
              type="button"
              onClick={() => setPeriodPreset('30')}
              style={{
                padding: '6px 12px',
                border: 'none',
                backgroundColor: periodPreset === '30' ? 'var(--color-ink)' : 'var(--color-bg)',
                color: periodPreset === '30' ? 'var(--color-bg)' : 'var(--color-ink)',
                fontSize: '0.75rem',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              LAST 30D
            </button>
            <button
              type="button"
              onClick={() => setPeriodPreset('90')}
              style={{
                padding: '6px 12px',
                border: 'none',
                backgroundColor: periodPreset === '90' ? 'var(--color-ink)' : 'var(--color-bg)',
                color: periodPreset === '90' ? 'var(--color-bg)' : 'var(--color-ink)',
                fontSize: '0.75rem',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              LAST 90D
            </button>
            <button
              type="button"
              onClick={() => setPeriodPreset('365')}
              style={{
                padding: '6px 12px',
                border: 'none',
                backgroundColor: periodPreset === '365' ? 'var(--color-ink)' : 'var(--color-bg)',
                color: periodPreset === '365' ? 'var(--color-bg)' : 'var(--color-ink)',
                fontSize: '0.75rem',
                cursor: 'pointer',
                fontFamily: 'var(--font-sans)',
              }}
            >
              1 YEAR
            </button>
          </div>

          {/* Currency Filter */}
          {currencies.length > 1 && (
            <select
              value={selectedCurrency}
              onChange={(e) => setSelectedCurrency(e.target.value)}
              style={{
                padding: '6px 10px',
                border: 'var(--border-hairline)',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--color-bg)',
                color: 'var(--color-ink)',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-sans)',
              }}
            >
              <option value="ALL">ALL CURRENCIES</option>
              {currencies.map((c) => (
                <option key={c.currency} value={c.currency}>
                  {c.currency}
                </option>
              ))}
            </select>
          )}

          <Button variant="outline" size="sm" onClick={fetchAnalytics}>
            REFRESH
          </Button>
        </div>
      </div>

      {error && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--color-overdue-bg)',
            border: '1px solid var(--color-overdue)',
            color: 'var(--color-overdue)',
            fontSize: '0.85rem',
            marginBottom: '20px',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          {error}
        </div>
      )}

      {!analytics?.has_data ? (
        <EmptyState
          title="Insufficient Historical Receivables"
          description="Analytics require finalized invoice history to generate aging buckets and collections velocity trends. As you create invoices and record settlements via PayPal Sandbox, currency-isolated charts will populate here."
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '28px', marginTop: '16px' }}>
          {/* AI Executive Intelligence Block */}
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
                marginBottom: '12px',
                borderBottom: 'var(--border-hairline)',
                paddingBottom: '8px',
              }}
            >
              <div
                style={{
                  fontSize: '0.7rem',
                  letterSpacing: 'var(--tracking-widest)',
                  textTransform: 'uppercase',
                  fontWeight: 600,
                  color: 'var(--color-muted)',
                }}
              >
                AI EXECUTIVE AR INTELLIGENCE (FACTUAL AUDIT)
              </div>
              {summaryLoading && (
                <span style={{ fontSize: '0.75rem', fontStyle: 'italic', color: 'var(--color-muted)' }}>
                  Synthesizing audit findings...
                </span>
              )}
            </div>

            {aiSummary ? (
              <div>
                <div
                  style={{
                    fontSize: '0.875rem',
                    lineHeight: 1.7,
                    whiteSpace: 'pre-wrap',
                    color: 'var(--color-ink)',
                  }}
                >
                  {aiSummary.summary}
                </div>

                {aiSummary.payment_velocity_estimate && (
                  <div
                    style={{
                      marginTop: '16px',
                      padding: '10px 14px',
                      backgroundColor: 'var(--color-bg)',
                      borderLeft: '3px solid var(--color-pending)',
                      fontSize: '0.8rem',
                      color: 'var(--color-ink)',
                    }}
                  >
                    <strong>Velocity Projection:</strong> {aiSummary.payment_velocity_estimate}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ fontSize: '0.85rem', color: 'var(--color-muted)', fontStyle: 'italic' }}>
                Loading AI receivables intelligence narrative...
              </div>
            )}
          </div>

          {/* Per-Currency Position & Aging Schedules */}
          {displayCurrencies.map((curr) => (
            <div
              key={curr.currency}
              style={{
                backgroundColor: 'var(--color-bg)',
                border: 'var(--border-hairline)',
                borderRadius: 'var(--radius-sm)',
                padding: '24px',
              }}
            >
              {/* Currency Header */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  marginBottom: '20px',
                  borderBottom: 'var(--border-hairline)',
                  paddingBottom: '12px',
                }}
              >
                <div>
                  <h3
                    style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: '1.25rem',
                      letterSpacing: 'var(--tracking-wide)',
                      margin: 0,
                    }}
                  >
                    {curr.currency} RECEIVABLES PORTFOLIO
                  </h3>
                  <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                    Authoritative ledger balances strictly isolated to {curr.currency}
                  </div>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--color-muted)' }}>
                  {curr.open_invoices_count} Open • {curr.overdue_invoices_count} Overdue
                </div>
              </div>

              {/* KPI Summary Cards */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: '16px',
                  marginBottom: '24px',
                }}
              >
                <div
                  style={{
                    backgroundColor: 'var(--color-cream)',
                    border: 'var(--border-hairline)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '16px',
                  }}
                >
                  <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: 'var(--tracking-widest)', color: 'var(--color-muted)' }}>
                    TOTAL OUTSTANDING
                  </div>
                  <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', marginTop: '6px', color: 'var(--color-ink)' }}>
                    ${curr.total_outstanding}
                  </div>
                </div>

                <div
                  style={{
                    backgroundColor: 'var(--color-overdue-bg)',
                    border: '1px solid var(--color-overdue)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '16px',
                  }}
                >
                  <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: 'var(--tracking-widest)', color: 'var(--color-overdue)' }}>
                    TOTAL OVERDUE
                  </div>
                  <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', marginTop: '6px', color: 'var(--color-overdue)' }}>
                    ${curr.total_overdue}
                  </div>
                </div>

                <div
                  style={{
                    backgroundColor: 'var(--color-paid-bg)',
                    border: '1px solid var(--color-paid)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '16px',
                  }}
                >
                  <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: 'var(--tracking-widest)', color: 'var(--color-paid)' }}>
                    COLLECTED IN PERIOD
                  </div>
                  <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.5rem', marginTop: '6px', color: 'var(--color-paid)' }}>
                    ${curr.total_collected_period}
                  </div>
                </div>
              </div>

              {/* Standard AR Aging Buckets */}
              <div style={{ marginBottom: '8px' }}>
                <div
                  style={{
                    fontSize: '0.7rem',
                    letterSpacing: 'var(--tracking-widest)',
                    textTransform: 'uppercase',
                    color: 'var(--color-muted)',
                    marginBottom: '12px',
                    fontWeight: 600,
                  }}
                >
                  STANDARD AR AGING SCHEDULE & INVOICE CITATIONS
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                    gap: '12px',
                  }}
                >
                  {/* Bucket 0-7 Days */}
                  <div
                    style={{
                      padding: '14px',
                      backgroundColor: 'var(--color-cream)',
                      border: 'var(--border-hairline)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    <div style={{ fontSize: '0.65rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase' }}>
                      0–7 DAYS (DUE SOON)
                    </div>
                    <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', margin: '4px 0' }}>
                      ${curr.aging_buckets.bucket_0_7_days.amount}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                      {curr.aging_buckets.bucket_0_7_days.count} invoice(s)
                    </div>
                    {curr.aging_buckets.bucket_0_7_days.invoice_numbers.length > 0 && (
                      <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {curr.aging_buckets.bucket_0_7_days.invoice_numbers.map((invNum) => (
                          <span
                            key={invNum}
                            style={{
                              fontSize: '0.65rem',
                              padding: '2px 6px',
                              backgroundColor: 'var(--color-bg)',
                              border: 'var(--border-hairline)',
                              borderRadius: 'var(--radius-sm)',
                            }}
                          >
                            {invNum}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Bucket 8-30 Days */}
                  <div
                    style={{
                      padding: '14px',
                      backgroundColor: 'var(--color-cream)',
                      border: 'var(--border-hairline)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    <div style={{ fontSize: '0.65rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase' }}>
                      8–30 DAYS PAST DUE
                    </div>
                    <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', margin: '4px 0', color: curr.aging_buckets.bucket_8_30_days.count > 0 ? 'var(--color-pending)' : 'inherit' }}>
                      ${curr.aging_buckets.bucket_8_30_days.amount}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                      {curr.aging_buckets.bucket_8_30_days.count} invoice(s)
                    </div>
                    {curr.aging_buckets.bucket_8_30_days.invoice_numbers.length > 0 && (
                      <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {curr.aging_buckets.bucket_8_30_days.invoice_numbers.map((invNum) => (
                          <span
                            key={invNum}
                            style={{
                              fontSize: '0.65rem',
                              padding: '2px 6px',
                              backgroundColor: 'var(--color-bg)',
                              border: 'var(--border-hairline)',
                              borderRadius: 'var(--radius-sm)',
                            }}
                          >
                            {invNum}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Bucket 31-60 Days */}
                  <div
                    style={{
                      padding: '14px',
                      backgroundColor: 'var(--color-cream)',
                      border: 'var(--border-hairline)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    <div style={{ fontSize: '0.65rem', color: 'var(--color-muted)', letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase' }}>
                      31–60 DAYS PAST DUE
                    </div>
                    <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', margin: '4px 0', color: curr.aging_buckets.bucket_31_60_days.count > 0 ? 'var(--color-overdue)' : 'inherit' }}>
                      ${curr.aging_buckets.bucket_31_60_days.amount}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                      {curr.aging_buckets.bucket_31_60_days.count} invoice(s)
                    </div>
                    {curr.aging_buckets.bucket_31_60_days.invoice_numbers.length > 0 && (
                      <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {curr.aging_buckets.bucket_31_60_days.invoice_numbers.map((invNum) => (
                          <span
                            key={invNum}
                            style={{
                              fontSize: '0.65rem',
                              padding: '2px 6px',
                              backgroundColor: 'var(--color-bg)',
                              border: 'var(--border-hairline)',
                              borderRadius: 'var(--radius-sm)',
                            }}
                          >
                            {invNum}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Bucket 60+ Days */}
                  <div
                    style={{
                      padding: '14px',
                      backgroundColor: curr.aging_buckets.bucket_60_plus_days.count > 0 ? 'var(--color-overdue-bg)' : 'var(--color-cream)',
                      border: curr.aging_buckets.bucket_60_plus_days.count > 0 ? '1px solid var(--color-overdue)' : 'var(--border-hairline)',
                      borderRadius: 'var(--radius-sm)',
                    }}
                  >
                    <div style={{ fontSize: '0.65rem', color: 'var(--color-overdue)', letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase', fontWeight: 600 }}>
                      60+ DAYS (CRITICAL)
                    </div>
                    <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.25rem', margin: '4px 0', color: 'var(--color-overdue)' }}>
                      ${curr.aging_buckets.bucket_60_plus_days.amount}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                      {curr.aging_buckets.bucket_60_plus_days.count} invoice(s)
                    </div>
                    {curr.aging_buckets.bucket_60_plus_days.invoice_numbers.length > 0 && (
                      <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {curr.aging_buckets.bucket_60_plus_days.invoice_numbers.map((invNum) => (
                          <span
                            key={invNum}
                            style={{
                              fontSize: '0.65rem',
                              padding: '2px 6px',
                              backgroundColor: 'var(--color-bg)',
                              border: '1px solid var(--color-overdue)',
                              borderRadius: 'var(--radius-sm)',
                              color: 'var(--color-overdue)',
                            }}
                          >
                            {invNum}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Customer Receivables Balances Table */}
          <div
            style={{
              backgroundColor: 'var(--color-bg)',
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
                borderBottom: 'var(--border-hairline)',
                paddingBottom: '8px',
                flexWrap: 'wrap',
                gap: 8,
              }}
            >
              <h3
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.15rem',
                  letterSpacing: 'var(--tracking-wide)',
                  margin: 0,
                }}
              >
                CUSTOMER RECEIVABLES BALANCES
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: '0.65rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-muted)' }}>
                    VIEW:
                  </span>
                  <Button
                    variant={balanceViewMode === 'ag-grid' ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => setBalanceViewMode('ag-grid')}
                    style={{ padding: '2px 8px', fontSize: '0.65rem' }}
                  >
                    AG Grid
                  </Button>
                  <Button
                    variant={balanceViewMode === 'table' ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => setBalanceViewMode('table')}
                    style={{ padding: '2px 8px', fontSize: '0.65rem' }}
                  >
                    Standard
                  </Button>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                  {displayCustomerBalances.length} client account(s)
                </div>
              </div>
            </div>

            {displayCustomerBalances.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--color-muted)', fontSize: '0.85rem' }}>
                No outstanding balances for active customers.
              </div>
            ) : balanceViewMode === 'ag-grid' ? (
              <AgCustomerBalanceGrid rowData={displayCustomerBalances} />
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table
                  style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: '0.85rem',
                    textAlign: 'left',
                  }}
                >
                  <thead>
                    <tr style={{ borderBottom: 'var(--border-hairline)', backgroundColor: 'var(--color-cream)' }}>
                      <th style={{ padding: '10px 12px', fontWeight: 600, fontSize: '0.7rem', letterSpacing: 'var(--tracking-wider)' }}>
                        CUSTOMER
                      </th>
                      <th style={{ padding: '10px 12px', fontWeight: 600, fontSize: '0.7rem', letterSpacing: 'var(--tracking-wider)' }}>
                        CURRENCY
                      </th>
                      <th style={{ padding: '10px 12px', fontWeight: 600, fontSize: '0.7rem', letterSpacing: 'var(--tracking-wider)' }}>
                        OUTSTANDING
                      </th>
                      <th style={{ padding: '10px 12px', fontWeight: 600, fontSize: '0.7rem', letterSpacing: 'var(--tracking-wider)' }}>
                        OVERDUE
                      </th>
                      <th style={{ padding: '10px 12px', fontWeight: 600, fontSize: '0.7rem', letterSpacing: 'var(--tracking-wider)' }}>
                        OPEN INVOICES
                      </th>
                      <th style={{ padding: '10px 12px', fontWeight: 600, fontSize: '0.7rem', letterSpacing: 'var(--tracking-wider)', textAlign: 'right' }}>
                        ACTION
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayCustomerBalances.map((cb, idx) => (
                      <tr
                        key={`${cb.customer_id}-${cb.currency}-${idx}`}
                        style={{
                          borderBottom: 'var(--border-hairline)',
                          backgroundColor: idx % 2 === 0 ? 'var(--color-bg)' : 'var(--color-cream)',
                        }}
                      >
                        <td style={{ padding: '12px' }}>
                          <div style={{ fontWeight: 600 }}>{cb.customer_name}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>{cb.customer_email}</div>
                        </td>
                        <td style={{ padding: '12px', fontWeight: 600 }}>{cb.currency}</td>
                        <td style={{ padding: '12px', fontWeight: 700, fontFamily: 'var(--font-serif)' }}>
                          ${cb.outstanding_amount}
                        </td>
                        <td
                          style={{
                            padding: '12px',
                            fontWeight: 700,
                            fontFamily: 'var(--font-serif)',
                            color: parseFloat(cb.overdue_amount) > 0 ? 'var(--color-overdue)' : 'inherit',
                          }}
                        >
                          ${cb.overdue_amount}
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span>{cb.open_invoices_count}</span>
                          {cb.invoice_numbers.length > 0 && (
                            <span style={{ fontSize: '0.75rem', color: 'var(--color-muted)', marginLeft: '6px' }}>
                              ({cb.invoice_numbers.slice(0, 3).join(', ')}{cb.invoice_numbers.length > 3 ? '...' : ''})
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '12px', textAlign: 'right' }}>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => navigate('/invoices')}
                          >
                            VIEW INVOICES →
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

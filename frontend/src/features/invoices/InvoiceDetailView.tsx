import { useEffect, useState, type FC } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  ConfirmDialog,
  DataTable,
  ErrorState,
  LoadingState,
  PageHeader,
  StatusLabel,
} from '../../components';
import { apiClient } from '../../lib/api-client';

interface LineItem {
  name: string;
  description?: string | null;
  quantity: string | number;
  unit_price: string;
  tax: string;
  total: string;
}

interface InvoiceDetail {
  internal_id: string;
  user_id: string;
  customer_id: string;
  customer_name?: string | null;
  invoice_number: string;
  items: LineItem[];
  subtotal: string;
  tax: string;
  total: string;
  currency: string;
  issue_date: string;
  due_date: string;
  status: string;
  paypal_invoice_id?: string | null;
  paypal_invoice_url?: string | null;
  sent_at?: string | null;
  paid_at?: string | null;
  created_at: string;
  updated_at: string;
  notes?: string | null;
}

interface TimelineEvent {
  id: string;
  action: string;
  action_label: string;
  actor_type: string;
  timestamp: string;
  result: string;
  metadata?: Record<string, any>;
}

interface InvoiceTimelineResponse {
  invoice_id: string;
  invoice_number: string;
  events: TimelineEvent[];
}

export const InvoiceDetailView: FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Dialog & Action loading states
  const [showDeleteDialog, setShowDeleteDialog] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isSubmittingApproval, setIsSubmittingApproval] = useState<boolean>(false);

  // PayPal Send Dialog state
  const [showSendDialog, setShowSendDialog] = useState<boolean>(false);
  const [isSending, setIsSending] = useState<boolean>(false);
  const [sendNote, setSendNote] = useState<string>('');

  const loadInvoice = async () => {
    if (!id) return;
    try {
      setIsLoading(true);
      setError(null);
      const data = await apiClient<InvoiceDetail>(`/api/invoices/${id}`);
      setInvoice(data);

      try {
        const timelineData = await apiClient<InvoiceTimelineResponse>(`/api/invoices/${id}/timeline`);
        if (timelineData && timelineData.events) {
          setTimelineEvents(timelineData.events);
        }
      } catch (tlErr) {
        console.warn('Could not load invoice timeline:', tlErr);
      }
    } catch (err: any) {
      console.error('Failed to load invoice:', err);
      setError(err.message || 'Invoice record could not be retrieved.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void loadInvoice();
  }, [id]);

  const handleDelete = async () => {
    if (!id) return;
    try {
      setIsDeleting(true);
      await apiClient(`/api/invoices/${id}`, { method: 'DELETE' });
      navigate('/invoices');
    } catch (err: any) {
      setActionNotice({ type: 'error', message: err.message || 'Failed to delete invoice.' });
      setShowDeleteDialog(false);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSubmitForApproval = async () => {
    if (!id) return;
    try {
      setIsSubmittingApproval(true);
      setActionNotice(null);
      const res = await apiClient<{ approval_id: string; message: string }>(
        `/api/invoices/${id}/submit-for-approval`,
        { method: 'POST' }
      );
      setActionNotice({
        type: 'success',
        message: res.message || 'Invoice successfully submitted to the Approval Center.',
      });
      await loadInvoice();
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: err.message || 'Could not submit invoice for approval.',
      });
    } finally {
      setIsSubmittingApproval(false);
    }
  };

  const handleApproveAndSend = async () => {
    if (!id) return;
    try {
      setIsSending(true);
      setActionNotice(null);
      const endpoint = invoice?.status === 'created'
        ? `/api/paypal/invoices/${id}/send`
        : `/api/paypal/invoices/${id}/approve-and-send`;

      const res = await apiClient<{
        invoice_id: string;
        invoice_number: string;
        paypal_invoice_id: string;
        paypal_invoice_url: string;
        message: string;
      }>(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          note: sendNote.trim() || undefined,
          send_to_recipient: true,
        }),
      });

      setActionNotice({
        type: 'success',
        message: res.message || 'Invoice dispatched via PayPal Developer Sandbox.',
      });
      setShowSendDialog(false);
      await loadInvoice();
    } catch (err: any) {
      setActionNotice({
        type: 'error',
        message: err.message || 'Failed to dispatch invoice via PayPal Sandbox.',
      });
    } finally {
      setIsSending(false);
    }
  };

  if (isLoading) {
    return <LoadingState label="RETRIEVING INVOICE RECORD..." />;
  }

  if (error || !invoice) {
    return (
      <ErrorState
        title="Invoice Not Found"
        message={error || 'The requested invoice does not exist or is not accessible.'}
        onRetry={() => void loadInvoice()}
      />
    );
  }

  const isOverdue =
    ['sent', 'unpaid', 'overdue'].includes(invoice.status) &&
    Boolean(invoice.due_date) &&
    new Date(invoice.due_date).getTime() < new Date(new Date().toISOString().split('T')[0] || '').getTime();

  return (
    <div style={{ maxWidth: 1040, margin: '0 auto', paddingBottom: 64 }}>
      {/* Header with Navigation and Quick Actions */}
      <PageHeader
        eyebrow={`INVOICE LEDGER // ${invoice.currency}`}
        title={invoice.invoice_number}
        subtitle={`Issued on ${invoice.issue_date} • Payment due ${invoice.due_date}`}
        actions={
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <Button variant="outline" size="sm" onClick={() => navigate('/invoices')}>
              ← Invoices
            </Button>

            {invoice.status === 'draft' && (
              <>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => navigate(`/invoices/${invoice.internal_id}/edit`)}
                >
                  Edit Draft
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  disabled={isSubmittingApproval}
                  onClick={() => void handleSubmitForApproval()}
                >
                  {isSubmittingApproval ? 'Submitting...' : 'Submit for Approval'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDeleteDialog(true)}
                  style={{ color: 'var(--color-overdue)' }}
                >
                  Delete
                </Button>
              </>
            )}

            {invoice.status === 'pending_approval' && (
              <Button variant="outline" size="sm" onClick={() => navigate('/approvals')}>
                Review in Approval Center →
              </Button>
            )}

            {['pending_approval', 'created'].includes(invoice.status) && (
              <Button variant="primary" size="sm" onClick={() => setShowSendDialog(true)}>
                Approve & Send via PayPal Sandbox
              </Button>
            )}

            {invoice.paypal_invoice_url && (
              <a
                href={invoice.paypal_invoice_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '8px 16px',
                  backgroundColor: 'var(--color-sand)',
                  border: 'var(--border-hairline)',
                  color: 'var(--color-ink)',
                  textDecoration: 'none',
                  fontSize: 12,
                  fontWeight: 600,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                }}
              >
                PayPal Invoice ↗
              </a>
            )}
          </div>
        }
      />

      {actionNotice && (
        <div style={{ marginBottom: 24 }}>
          <Alert
            type={actionNotice.type}
            message={actionNotice.message}
            onDismiss={() => setActionNotice(null)}
          />
        </div>
      )}

      {/* Top Highlight Cards: Total, Client, Dates */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))',
          gap: 20,
          marginBottom: 32,
        }}
      >
        {/* Total Amount Card */}
        <div
          style={{
            backgroundColor: 'var(--color-ink)',
            color: '#FAF7F2',
            padding: 24,
            border: 'var(--border-hairline)',
          }}
        >
          <div
            style={{
              fontSize: 11,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--color-sand)',
              marginBottom: 12,
            }}
          >
            Total Invoiced
          </div>
          <div style={{ fontFamily: 'var(--font-heading)', fontSize: 32, color: '#FAF7F2' }}>
            ${parseFloat(invoice.total).toLocaleString('en-US', { minimumFractionDigits: 2 })}{' '}
            <span style={{ fontSize: 16, fontFamily: 'var(--font-body)', color: 'var(--color-sand)' }}>
              {invoice.currency}
            </span>
          </div>
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <StatusLabel status={invoice.status} />
            {isOverdue && (
              <span
                style={{
                  fontSize: 10,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  padding: '2px 8px',
                  backgroundColor: 'var(--color-overdue-bg)',
                  color: 'var(--color-overdue)',
                  border: '1px solid var(--color-overdue)',
                  fontWeight: 600,
                }}
              >
                OVERDUE
              </span>
            )}
          </div>
        </div>

        {/* Client Details Card */}
        <div
          style={{
            backgroundColor: 'var(--color-sand)',
            padding: 24,
            border: 'var(--border-hairline)',
          }}
        >
          <div
            style={{
              fontSize: 11,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--color-muted)',
              marginBottom: 12,
            }}
          >
            Client Recipient
          </div>
          <div style={{ fontFamily: 'var(--font-heading)', fontSize: 20, color: 'var(--color-ink)' }}>
            {invoice.customer_name || 'Customer'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 4, fontFamily: 'monospace' }}>
            ID: {invoice.customer_id}
          </div>
          <div style={{ marginTop: 16 }}>
            <span
              style={{
                fontSize: 11,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                color: 'var(--color-muted)',
              }}
            >
              Ownership: Verified Tenant
            </span>
          </div>
        </div>

        {/* Chronology & Dates Card */}
        <div
          style={{
            backgroundColor: 'var(--color-sand)',
            padding: 24,
            border: 'var(--border-hairline)',
          }}
        >
          <div
            style={{
              fontSize: 11,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--color-muted)',
              marginBottom: 12,
            }}
          >
            Schedule & Terms
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--color-muted)' }}>Issue Date:</span>
              <span style={{ fontWeight: 500 }}>{invoice.issue_date}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--color-muted)' }}>Due Date:</span>
              <span style={{ fontWeight: 600, color: isOverdue ? 'var(--color-overdue)' : 'inherit' }}>
                {invoice.due_date}
              </span>
            </div>
            {invoice.sent_at && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-muted)' }}>Dispatched:</span>
                <span>{new Date(invoice.sent_at).toLocaleDateString()}</span>
              </div>
            )}
            {invoice.paid_at && (
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-muted)' }}>Settled:</span>
                <span style={{ color: 'var(--color-paid)', fontWeight: 600 }}>
                  {new Date(invoice.paid_at).toLocaleDateString()}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* PayPal Sandbox Status Banner */}
      <div
        style={{
          backgroundColor: 'var(--color-cream)',
          border: 'var(--border-hairline)',
          padding: 20,
          marginBottom: 32,
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span
              style={{
                fontSize: 10,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                backgroundColor: 'var(--color-sand)',
                padding: '2px 8px',
                border: 'var(--border-hairline)',
                fontWeight: 600,
              }}
            >
              PayPal Sandbox Channel
            </span>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)' }}>
              {invoice.paypal_invoice_id ? `PayPal ID: ${invoice.paypal_invoice_id}` : 'Pending Send Execution'}
            </span>
          </div>
          <p style={{ margin: 0, fontSize: 12, color: 'var(--color-muted)' }}>
            Official REST Invoicing API integration. No live funds are transacted. Real PayPal webhook events sync payment status.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          {['draft', 'pending_approval', 'created'].includes(invoice.status) && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowSendDialog(true)}
            >
              Approve & Send via PayPal Sandbox →
            </Button>
          )}

          {invoice.paypal_invoice_url && (
            <a
              href={invoice.paypal_invoice_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                padding: '10px 18px',
                backgroundColor: 'var(--color-ink)',
                color: '#FAF7F2',
                textDecoration: 'none',
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
              }}
            >
              Open in PayPal Sandbox ↗
            </a>
          )}
        </div>
      </div>

      {/* Line Items Table */}
      <div
        style={{
          backgroundColor: 'var(--color-sand)',
          border: 'var(--border-hairline)',
          padding: 24,
          marginBottom: 32,
        }}
      >
        <div
          style={{
            fontFamily: 'var(--font-heading)',
            fontSize: 16,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: 'var(--color-ink)',
            marginBottom: 16,
            borderBottom: 'var(--border-hairline)',
            paddingBottom: 8,
          }}
        >
          Itemized Deliverables & Charges
        </div>

        <DataTable<LineItem>
          columns={[
            {
              key: 'item',
              header: 'DESCRIPTION',
              render: (row: LineItem) => (
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--color-ink)' }}>{row.name}</div>
                  {row.description && (
                    <div style={{ fontSize: 12, color: 'var(--color-muted)', marginTop: 2 }}>
                      {row.description}
                    </div>
                  )}
                </div>
              ),
            },
            {
              key: 'quantity',
              header: 'QTY',
              render: (row: LineItem) => <span style={{ fontFamily: 'monospace' }}>{row.quantity}</span>,
            },
            {
              key: 'unit_price',
              header: `UNIT (${invoice.currency})`,
              render: (row: LineItem) => (
                <span style={{ fontFamily: 'monospace' }}>
                  {parseFloat(row.unit_price).toFixed(2)}
                </span>
              ),
            },
            {
              key: 'tax',
              header: 'TAX',
              render: (row: LineItem) => (
                <span style={{ fontFamily: 'monospace' }}>
                  {parseFloat(row.tax || '0').toFixed(2)}
                </span>
              ),
            },
            {
              key: 'total',
              header: 'LINE TOTAL',
              render: (row: LineItem) => (
                <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                  {parseFloat(row.total).toFixed(2)}
                </span>
              ),
            },
          ]}
          data={invoice.items || []}
          keyExtractor={(row, index) => `${row.name}-${index}`}
          emptyMessage="No items in this invoice."
        />

        {/* Calculation Reconciliation */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            marginTop: 20,
            borderTop: 'var(--border-hairline)',
            paddingTop: 16,
          }}
        >
          <div style={{ width: '100%', maxWidth: 280, display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--color-muted)' }}>Subtotal:</span>
              <span style={{ fontFamily: 'monospace' }}>
                {parseFloat(invoice.subtotal).toFixed(2)} {invoice.currency}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--color-muted)' }}>Taxes:</span>
              <span style={{ fontFamily: 'monospace' }}>
                {parseFloat(invoice.tax).toFixed(2)} {invoice.currency}
              </span>
            </div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                borderTop: 'var(--border-hairline)',
                paddingTop: 8,
                fontSize: 16,
                fontWeight: 600,
              }}
            >
              <span>Grand Total:</span>
              <span style={{ fontFamily: 'var(--font-heading)' }}>
                ${parseFloat(invoice.total).toFixed(2)} {invoice.currency}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Notes & Activity Timeline */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))',
          gap: 24,
        }}
      >
        {/* Notes */}
        <div
          style={{
            backgroundColor: 'var(--color-sand)',
            border: 'var(--border-hairline)',
            padding: 24,
          }}
        >
          <div
            style={{
              fontFamily: 'var(--font-heading)',
              fontSize: 16,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--color-ink)',
              marginBottom: 12,
              borderBottom: 'var(--border-hairline)',
              paddingBottom: 8,
            }}
          >
            Terms & Client Notes
          </div>
          <p
            style={{
              margin: 0,
              fontSize: 13,
              lineHeight: 1.6,
              color: 'var(--color-ink)',
              whiteSpace: 'pre-wrap',
            }}
          >
            {invoice.notes || 'No specific terms recorded for this invoice.'}
          </p>
        </div>

        {/* Activity Timeline */}
        <div
          style={{
            backgroundColor: 'var(--color-sand)',
            border: 'var(--border-hairline)',
            padding: 24,
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 16,
              borderBottom: 'var(--border-hairline)',
              paddingBottom: 8,
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-heading)',
                fontSize: 16,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--color-ink)',
              }}
            >
              Append-Only Audit Timeline
            </div>
            <span
              style={{
                fontSize: 10,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: 'var(--color-muted)',
                fontWeight: 600,
              }}
            >
              Ledger Immutable
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {timelineEvents.length > 0 ? (
              timelineEvents.map((evt) => {
                const isPaypal = evt.actor_type === 'paypal_webhook';
                const isSystem = evt.actor_type === 'system';
                const isAI = evt.actor_type === 'ai_assistant';
                const dotColor = isPaypal
                  ? 'var(--color-paid)'
                  : evt.action.includes('approval') || evt.action.includes('submit')
                  ? 'var(--color-pending)'
                  : 'var(--color-ink)';

                const actorLabel = isPaypal
                  ? 'PAYPAL'
                  : isAI
                  ? 'AI AGENT'
                  : isSystem
                  ? 'SYSTEM'
                  : 'MERCHANT';

                return (
                  <div key={evt.id} style={{ display: 'flex', gap: 12 }}>
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 1,
                        backgroundColor: dotColor,
                        marginTop: 6,
                        flexShrink: 0,
                      }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)' }}>
                          {evt.action_label}
                        </span>
                        <span
                          style={{
                            fontSize: 9,
                            letterSpacing: '0.08em',
                            textTransform: 'uppercase',
                            padding: '1px 6px',
                            backgroundColor: 'var(--color-cream)',
                            border: 'var(--border-hairline)',
                            color: 'var(--color-muted)',
                            fontWeight: 600,
                          }}
                        >
                          {actorLabel}
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 2 }}>
                        {new Date(evt.timestamp).toLocaleString()}
                      </div>
                      {evt.metadata && Object.keys(evt.metadata).length > 0 && (
                        <div
                          style={{
                            marginTop: 4,
                            fontSize: 11,
                            fontFamily: 'monospace',
                            color: 'var(--color-muted)',
                            wordBreak: 'break-all',
                          }}
                        >
                          {evt.metadata.capture_id && <span>Capture: {evt.metadata.capture_id} • </span>}
                          {evt.metadata.paypal_invoice_id && <span>PayPal ID: {evt.metadata.paypal_invoice_id} • </span>}
                          {evt.metadata.amount && <span>Settled: ${parseFloat(evt.metadata.amount).toFixed(2)} {invoice.currency}</span>}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <>
                {/* Fallback to basic invoice timestamps */}
                <div style={{ display: 'flex', gap: 12 }}>
                  <div
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 1,
                      backgroundColor: 'var(--color-ink)',
                      marginTop: 6,
                    }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>Draft Created</div>
                    <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                      {new Date(invoice.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>

                {invoice.status !== 'draft' && (
                  <div style={{ display: 'flex', gap: 12 }}>
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 1,
                        backgroundColor: 'var(--color-pending)',
                        marginTop: 6,
                      }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>Submitted for Human Approval</div>
                      <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                        {new Date(invoice.updated_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}

                {invoice.sent_at && (
                  <div style={{ display: 'flex', gap: 12 }}>
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 1,
                        backgroundColor: 'var(--color-sand)',
                        border: '1px solid var(--color-ink)',
                        marginTop: 6,
                      }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>Dispatched via PayPal Sandbox</div>
                      <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                        {new Date(invoice.sent_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}

                {invoice.paid_at && (
                  <div style={{ display: 'flex', gap: 12 }}>
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 1,
                        backgroundColor: 'var(--color-paid)',
                        marginTop: 6,
                      }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-paid)' }}>
                        Payment Reconciled (PayPal Webhook)
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                        {new Date(invoice.paid_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showDeleteDialog}
        title="Delete Draft Invoice?"
        message={`Are you sure you want to permanently delete draft invoice ${invoice.invoice_number}? This action cannot be undone.`}
        confirmLabel={isDeleting ? 'Deleting...' : 'Delete Draft'}
        cancelLabel="Keep Draft"
        variant="danger"
        isLoading={isDeleting}
        onConfirm={() => void handleDelete()}
        onCancel={() => setShowDeleteDialog(false)}
      />

      {/* Approve & Send via PayPal Sandbox Dialog */}
      <ConfirmDialog
        isOpen={showSendDialog}
        title="Approve & Send via PayPal Sandbox"
        message={
          <div>
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: 'var(--color-sand)',
                border: '1px dashed var(--color-hairline)',
                marginBottom: 16,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: '0.1em',
                    backgroundColor: 'var(--color-ink)',
                    color: '#FAF7F2',
                    padding: '2px 6px',
                  }}
                >
                  SANDBOX SIMULATION
                </span>
                <span style={{ fontSize: 12, fontWeight: 600 }}>Zero Real Funds Transacted</span>
              </div>
              <div style={{ fontSize: 11, color: 'var(--color-muted)' }}>
                This invoice will be delivered via official PayPal Developer Sandbox APIs. Test sandbox accounts can preview and settle this payment without real money.
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 160px), 1fr))', gap: 12, fontSize: 12, marginBottom: 16 }}>
              <div>
                <div style={{ color: 'var(--color-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Customer Recipient</div>
                <div style={{ fontWeight: 600, marginTop: 2 }}>{invoice.customer_name || 'Customer'}</div>
              </div>
              <div>
                <div style={{ color: 'var(--color-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Invoiced Amount</div>
                <div style={{ fontWeight: 600, marginTop: 2, fontFamily: 'var(--font-heading)', fontSize: 14 }}>
                  ${parseFloat(invoice.total).toLocaleString('en-US', { minimumFractionDigits: 2 })} {invoice.currency}
                </div>
              </div>
              <div>
                <div style={{ color: 'var(--color-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Payment Due</div>
                <div style={{ fontWeight: 600, marginTop: 2 }}>{invoice.due_date}</div>
              </div>
              <div>
                <div style={{ color: 'var(--color-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Target Destination</div>
                <div style={{ fontWeight: 600, marginTop: 2, fontFamily: 'monospace', fontSize: 11 }}>
                  PayPal Sandbox Invoicing v2
                </div>
              </div>
            </div>

            {invoice.paypal_invoice_url && (
              <div style={{ marginBottom: 16, fontSize: 11 }}>
                <span style={{ color: 'var(--color-muted)' }}>Sandbox Link: </span>
                <span style={{ fontFamily: 'monospace', wordBreak: 'break-all' }}>{invoice.paypal_invoice_url}</span>
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <label
                style={{
                  display: 'block',
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  marginBottom: 6,
                }}
              >
                Delivery Note (Optional)
              </label>
              <textarea
                value={sendNote}
                onChange={(e) => setSendNote(e.target.value)}
                placeholder="Add an optional greeting or memo included in the PayPal Sandbox notification..."
                rows={3}
                style={{
                  width: '100%',
                  boxSizing: 'border-box',
                  border: 'var(--border-hairline)',
                  backgroundColor: 'var(--color-cream)',
                  padding: '8px 12px',
                  fontSize: 12,
                  fontFamily: 'var(--font-sans)',
                  color: 'var(--color-ink)',
                  resize: 'vertical',
                }}
              />
            </div>
          </div>
        }
        confirmLabel={isSending ? 'DISPATCHING VIA SANDBOX...' : 'APPROVE & SEND VIA PAYPAL SANDBOX'}
        cancelLabel="CANCEL"
        variant="primary"
        isLoading={isSending}
        onConfirm={() => void handleApproveAndSend()}
        onCancel={() => setShowSendDialog(false)}
      />
    </div>
  );
};

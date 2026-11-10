import { useEffect, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Alert,
  Button,
  ConfirmDialog,
  EmptyState,
  LoadingState,
  PageHeader,
  StatusLabel,
} from '../../components';
import { apiClient } from '../../lib/api-client';

interface ApprovalItem {
  id: string;
  user_id: string;
  action_type: string;
  resource_type: string;
  resource_id: string;
  payload_snapshot: Record<string, any>;
  payload_hash: string;
  status: 'pending' | 'approved' | 'rejected' | 'invalidated' | 'expired';
  created_at: string;
  approved_at?: string | null;
  rejected_at?: string | null;
  execution_result_ref?: string | null;
  display_title?: string | null;
  customer_name?: string | null;
  invoice_number?: string | null;
  amount?: string | null;
  currency?: string | null;
}

interface ApprovalListResponse {
  items: ApprovalItem[];
  total: number;
  pending_count: number;
}

export const ApprovalsView: FC = () => {
  const navigate = useNavigate();

  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const [expandedPayloadId, setExpandedPayloadId] = useState<string | null>(null);

  const [actionAlert, setActionAlert] = useState<{ type: 'success' | 'error' | 'warning'; message: string } | null>(null);

  // Dialog state
  const [confirmingApproval, setConfirmingApproval] = useState<ApprovalItem | null>(null);
  const [confirmingRejection, setConfirmingRejection] = useState<ApprovalItem | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  const loadApprovals = async () => {
    try {
      setLoading(true);
      setActionAlert(null);
      const filter = activeTab === 'pending' ? 'pending' : activeTab === 'approved' ? 'approved' : '';
      let url = '/api/approvals';
      if (filter) url += `?status=${filter}`;
      const res = await apiClient<ApprovalListResponse>(url);
      setApprovals(res.items || []);
    } catch (err: any) {
      console.warn('Failed to fetch approvals:', err);
      setApprovals([]);
      setActionAlert({ type: 'error', message: err.message || 'Unable to load approval requests.' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadApprovals();
  }, [activeTab]);

  const handleApprove = async () => {
    if (!confirmingApproval) return;
    try {
      setIsProcessing(true);
      setActionAlert(null);
      const res = await apiClient<{ message: string; status: string }>(
        `/api/approvals/${confirmingApproval.id}/approve`,
        {
          method: 'POST',
          body: JSON.stringify({ reason: 'Authorized by business owner' }),
        }
      );
      setActionAlert({
        type: 'success',
        message: res.message || `Approval granted for ${confirmingApproval.display_title || 'action'}.`,
      });
      setConfirmingApproval(null);
      await loadApprovals();
    } catch (err: any) {
      let msg = err.message || 'Could not approve action.';
      if (err.status === 409) {
        msg = 'Conflict: Underlying invoice contents were modified since submission. Approval has been invalidated.';
      }
      setActionAlert({ type: 'error', message: msg });
      setConfirmingApproval(null);
      await loadApprovals();
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!confirmingRejection) return;
    try {
      setIsProcessing(true);
      setActionAlert(null);
      const res = await apiClient<{ message: string; status: string }>(
        `/api/approvals/${confirmingRejection.id}/reject`,
        {
          method: 'POST',
          body: JSON.stringify({ reason: 'Rejected by business owner' }),
        }
      );
      setActionAlert({
        type: 'warning',
        message: res.message || 'Action rejected. Invoice returned to draft.',
      });
      setConfirmingRejection(null);
      await loadApprovals();
    } catch (err: any) {
      setActionAlert({ type: 'error', message: err.message || 'Could not reject action.' });
      setConfirmingRejection(null);
    } finally {
      setIsProcessing(false);
    }
  };

  const pendingApprovalsCount = approvals.filter((a) => a.status === 'pending').length;

  return (
    <div style={{ maxWidth: 1040, margin: '0 auto', paddingBottom: 64 }}>
      <PageHeader
        eyebrow="HUMAN-IN-THE-LOOP POLICY ENGINE"
        title="Approval Center"
        subtitle="Review, authorize, or dismiss sensitive outbound business actions. Invoices and payments are never dispatched without explicit authorization."
      />

      {actionAlert && (
        <div style={{ marginBottom: 24 }}>
          <Alert
            type={actionAlert.type}
            message={actionAlert.message}
            onDismiss={() => setActionAlert(null)}
          />
        </div>
      )}

      {/* Tabs */}
      <div
        style={{
          display: 'flex',
          borderBottom: 'var(--border-hairline)',
          marginBottom: 24,
          gap: 4,
        }}
      >
        <button
          type="button"
          onClick={() => setActiveTab('pending')}
          style={{
            padding: '10px 20px',
            background: activeTab === 'pending' ? 'var(--color-sand)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'pending' ? '2px solid var(--color-ink)' : '2px solid transparent',
            color: 'var(--color-ink)',
            fontWeight: activeTab === 'pending' ? 600 : 400,
            fontSize: 13,
            cursor: 'pointer',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span>Pending Authorization</span>
          {activeTab === 'pending' && pendingApprovalsCount > 0 && (
            <span
              style={{
                backgroundColor: 'var(--color-pending)',
                color: '#FAF7F2',
                fontSize: 11,
                padding: '1px 6px',
                borderRadius: 2,
                fontWeight: 600,
              }}
            >
              {pendingApprovalsCount}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('approved')}
          style={{
            padding: '10px 20px',
            background: activeTab === 'approved' ? 'var(--color-sand)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'approved' ? '2px solid var(--color-ink)' : '2px solid transparent',
            color: 'var(--color-ink)',
            fontWeight: activeTab === 'approved' ? 600 : 400,
            fontSize: 13,
            cursor: 'pointer',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}
        >
          Approved History
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('rejected')}
          style={{
            padding: '10px 20px',
            background: activeTab === 'rejected' ? 'var(--color-sand)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'rejected' ? '2px solid var(--color-ink)' : '2px solid transparent',
            color: 'var(--color-ink)',
            fontWeight: activeTab === 'rejected' ? 600 : 400,
            fontSize: 13,
            cursor: 'pointer',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}
        >
          Rejected & Invalidated
        </button>
      </div>

      {/* Main Content */}
      {loading ? (
        <LoadingState label="RETRIEVING APPROVAL REQUESTS..." />
      ) : approvals.length === 0 ? (
        <EmptyState
          title={
            activeTab === 'pending'
              ? 'No Actions Awaiting Authorization'
              : 'No Records in Selected View'
          }
          description={
            activeTab === 'pending'
              ? 'All invoice drafts and payment reminders have been authorized or dismissed. When an invoice draft is submitted for sending, it will appear here for your explicit authorization.'
              : 'There are no historical approval logs matching the active filter tab.'
          }
          action={
            activeTab === 'pending' ? (
              <Button variant="secondary" size="sm" onClick={() => navigate('/invoices')}>
                Go to Invoices
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {approvals.map((appr) => {
            const isExpanded = expandedPayloadId === appr.id;

            return (
              <div
                key={appr.id}
                style={{
                  backgroundColor: 'var(--color-sand)',
                  border: 'var(--border-hairline)',
                  padding: 24,
                  position: 'relative',
                }}
              >
                {/* Header row */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-start',
                    borderBottom: 'var(--border-hairline)',
                    paddingBottom: 12,
                    marginBottom: 16,
                    flexWrap: 'wrap',
                    gap: 12,
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span
                        style={{
                          fontSize: 11,
                          letterSpacing: '0.08em',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          color: 'var(--color-ink)',
                        }}
                      >
                        {appr.display_title || appr.action_type.toUpperCase()}
                      </span>
                      <StatusLabel status={appr.status} size="sm" />
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 4 }}>
                      Requested: {new Date(appr.created_at).toLocaleString()}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 11, textTransform: 'uppercase', color: 'var(--color-muted)' }}>
                      Authorized Amount
                    </div>
                    <div style={{ fontFamily: 'var(--font-heading)', fontSize: 22, color: 'var(--color-ink)' }}>
                      ${parseFloat(appr.amount || '0').toFixed(2)}{' '}
                      <span style={{ fontSize: 13, fontFamily: 'var(--font-body)', color: 'var(--color-muted)' }}>
                        {appr.currency || 'USD'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Parameters Grid */}
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                    gap: 16,
                    marginBottom: 16,
                    fontSize: 13,
                  }}
                >
                  <div>
                    <span style={{ color: 'var(--color-muted)', display: 'block', fontSize: 11, textTransform: 'uppercase' }}>
                      Client Recipient
                    </span>
                    <span style={{ fontWeight: 600 }}>{appr.customer_name || 'Customer'}</span>
                  </div>

                  <div>
                    <span style={{ color: 'var(--color-muted)', display: 'block', fontSize: 11, textTransform: 'uppercase' }}>
                      Invoice Reference
                    </span>
                    <button
                      type="button"
                      onClick={() => navigate(`/invoices/${appr.resource_id}`)}
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: 0,
                        color: 'var(--color-ink)',
                        fontWeight: 600,
                        textDecoration: 'underline',
                        cursor: 'pointer',
                        fontFamily: 'monospace',
                        fontSize: 13,
                      }}
                    >
                      {appr.invoice_number || appr.resource_id}
                    </button>
                  </div>

                  <div>
                    <span style={{ color: 'var(--color-muted)', display: 'block', fontSize: 11, textTransform: 'uppercase' }}>
                      Cryptographic Fingerprint
                    </span>
                    <span
                      style={{
                        fontFamily: 'monospace',
                        fontSize: 11,
                        color: 'var(--color-muted)',
                        wordBreak: 'break-all',
                      }}
                      title={appr.payload_hash}
                    >
                      SHA-256: {appr.payload_hash.substring(0, 16)}...
                    </span>
                  </div>
                </div>

                {/* Expandable Payload Snapshot Drawer */}
                <div style={{ marginBottom: 16 }}>
                  <button
                    type="button"
                    onClick={() => setExpandedPayloadId(isExpanded ? null : appr.id)}
                    style={{
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      color: 'var(--color-ink)',
                      textDecoration: 'underline',
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    {isExpanded ? '− Hide Sealed Payload Snapshot' : '+ Inspect Sealed Payload Snapshot (JSON)'}
                  </button>

                  {isExpanded && (
                    <div
                      style={{
                        marginTop: 10,
                        padding: 14,
                        backgroundColor: 'var(--color-cream)',
                        border: 'var(--border-hairline)',
                        fontSize: 11,
                        fontFamily: 'monospace',
                        overflowX: 'auto',
                        whiteSpace: 'pre-wrap',
                      }}
                    >
                      {JSON.stringify(appr.payload_snapshot, null, 2)}
                    </div>
                  )}
                </div>

                {/* Status-specific action footer */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderTop: 'var(--border-hairline)',
                    paddingTop: 16,
                    flexWrap: 'wrap',
                    gap: 12,
                  }}
                >
                  <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>
                    {appr.status === 'pending' ? (
                      <span>Requires explicit account owner authorization before dispatch.</span>
                    ) : appr.status === 'approved' ? (
                      <span style={{ color: 'var(--color-paid)', fontWeight: 600 }}>
                        ✓ Authorized on {appr.approved_at ? new Date(appr.approved_at).toLocaleString() : 'recently'}.
                      </span>
                    ) : (
                      <span style={{ color: 'var(--color-overdue)' }}>
                        ✗ Request {appr.status}. Re-submission required for execution.
                      </span>
                    )}
                  </div>

                  {appr.status === 'pending' && (
                    <div style={{ display: 'flex', gap: 12 }}>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setConfirmingRejection(appr)}
                        disabled={isProcessing}
                      >
                        Reject & Revert
                      </Button>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => setConfirmingApproval(appr)}
                        disabled={isProcessing}
                      >
                        Authorize & Approve
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Approve Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(confirmingApproval)}
        title="Authorize Action?"
        message={`Authorize dispatch of ${confirmingApproval?.display_title || 'action'} for $${confirmingApproval?.amount || '0'} ${confirmingApproval?.currency || 'USD'}? This marks the operation approved for PayPal execution.`}
        confirmLabel={isProcessing ? 'Authorizing...' : 'AUTHORIZE & APPROVE'}
        cancelLabel="CANCEL"
        variant="primary"
        isLoading={isProcessing}
        onConfirm={() => void handleApprove()}
        onCancel={() => setConfirmingApproval(null)}
      />

      {/* Reject Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(confirmingRejection)}
        title="Reject Action?"
        message={`Reject ${confirmingRejection?.display_title || 'action'}? The associated invoice will be reverted to draft status so you can revise or delete it.`}
        confirmLabel={isProcessing ? 'Rejecting...' : 'REJECT & REVERT'}
        cancelLabel="CANCEL"
        variant="danger"
        isLoading={isProcessing}
        onConfirm={() => void handleReject()}
        onCancel={() => setConfirmingRejection(null)}
      />
    </div>
  );
};

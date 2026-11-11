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
  TextArea,
  TextInput,
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

interface ReminderItem {
  id: string;
  user_id: string;
  invoice_id: string;
  invoice_number: string;
  customer_id: string;
  customer_name: string;
  customer_email: string;
  stage: string;
  status: 'draft' | 'ready_for_approval' | 'approved' | 'sent' | 'failed' | 'dismissed';
  subject: string;
  message_body: string;
  payment_link?: string | null;
  channel: string;
  channel_configured: boolean;
  channel_label: string;
  retry_count: number;
  delivery_error?: string | null;
  created_at: string;
  updated_at: string;
  sent_at?: string | null;
  approval_id?: string | null;
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
  const [activeTab, setActiveTab] = useState<'pending' | 'approved' | 'rejected' | 'reminders'>('pending');
  const [expandedPayloadId, setExpandedPayloadId] = useState<string | null>(null);

  // Reminder State (Prompts 21 & 22)
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [editingReminderId, setEditingReminderId] = useState<string | null>(null);
  const [editSubject, setEditSubject] = useState<string>('');
  const [editBody, setEditBody] = useState<string>('');
  const [isEvaluatingReminders, setIsEvaluatingReminders] = useState<boolean>(false);

  const [actionAlert, setActionAlert] = useState<{ type: 'success' | 'error' | 'warning'; message: string } | null>(null);

  // Dialog state
  const [confirmingApproval, setConfirmingApproval] = useState<ApprovalItem | null>(null);
  const [confirmingRejection, setConfirmingRejection] = useState<ApprovalItem | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [dispatchingId, setDispatchingId] = useState<string | null>(null);

  const loadApprovals = async () => {
    try {
      setLoading(true);
      setActionAlert(null);
      if (activeTab === 'reminders') {
        const remRes = await apiClient<{ items: ReminderItem[]; total: number }>('/api/reminders');
        setReminders(remRes.items || []);
      } else {
        const filter =
          activeTab === 'pending'
            ? 'pending'
            : activeTab === 'approved'
            ? 'approved'
            : activeTab === 'rejected'
            ? 'rejected'
            : '';
        let url = '/api/approvals';
        if (filter) url += `?status=${filter}`;
        const res = await apiClient<ApprovalListResponse>(url);
        setApprovals(res.items || []);
      }
    } catch (err: any) {
      console.warn('Failed to fetch approvals/reminders:', err);
      setActionAlert({ type: 'error', message: err.message || 'Unable to load approval requests.' });
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluateReminders = async () => {
    try {
      setIsEvaluatingReminders(true);
      setActionAlert(null);
      const res = await apiClient<{ drafts_created_count: number; skipped_existing_count: number }>(
        '/api/reminders/evaluate',
        {
          method: 'POST',
          body: JSON.stringify({}),
        }
      );
      setActionAlert({
        type: 'success',
        message: `Evaluation completed: ${res.drafts_created_count} reminder draft(s) prepared for review. (${res.skipped_existing_count} already up-to-date).`,
      });
      await loadApprovals();
    } catch (err: any) {
      setActionAlert({ type: 'error', message: err.message || 'Failed to run reminder evaluation.' });
    } finally {
      setIsEvaluatingReminders(false);
    }
  };

  const handleApproveReminder = async (remId: string) => {
    try {
      setIsProcessing(true);
      await apiClient(`/api/reminders/${remId}/approve`, { method: 'POST' });
      setActionAlert({ type: 'success', message: 'Payment reminder approved for dispatch.' });
      await loadApprovals();
    } catch (err: any) {
      setActionAlert({ type: 'error', message: err.message || 'Failed to approve reminder.' });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDispatchReminder = async (remId: string) => {
    try {
      setDispatchingId(remId);
      const res = await apiClient<{ message: string; channel: string }>('/api/reminders/' + remId + '/dispatch', {
        method: 'POST',
      });
      setActionAlert({ type: 'success', message: res.message });
      await loadApprovals();
    } catch (err: any) {
      setActionAlert({ type: 'error', message: err.message || 'Failed to dispatch reminder.' });
    } finally {
      setDispatchingId(null);
    }
  };

  const handleRetryReminder = async (remId: string) => {
    try {
      setDispatchingId(remId);
      const res = await apiClient<{ message: string }>('/api/reminders/' + remId + '/retry', {
        method: 'POST',
      });
      setActionAlert({ type: 'success', message: res.message });
      await loadApprovals();
    } catch (err: any) {
      setActionAlert({ type: 'error', message: err.message || 'Retry failed.' });
    } finally {
      setDispatchingId(null);
    }
  };

  const handleSaveReminderEdit = async (remId: string) => {
    try {
      setIsProcessing(true);
      await apiClient(`/api/reminders/${remId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          subject: editSubject.trim() || undefined,
          message_body: editBody.trim() || undefined,
        }),
      });
      setEditingReminderId(null);
      setActionAlert({ type: 'success', message: 'Reminder copy updated successfully.' });
      await loadApprovals();
    } catch (err: any) {
      setActionAlert({ type: 'error', message: err.message || 'Failed to update reminder.' });
    } finally {
      setIsProcessing(false);
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

  const handleDispatchToPayPal = async (appr: ApprovalItem) => {
    try {
      setDispatchingId(appr.id);
      setActionAlert(null);
      const res = await apiClient<{
        invoice_id: string;
        invoice_number: string;
        paypal_invoice_id: string;
        paypal_invoice_url: string;
        message: string;
      }>('/api/paypal/invoices', {
        method: 'POST',
        body: JSON.stringify({
          invoice_id: appr.resource_id,
          approval_id: appr.id,
        }),
      });
      setActionAlert({
        type: 'success',
        message: `Successfully created invoice in PayPal Sandbox (ID: ${res.paypal_invoice_id}).`,
      });
      await loadApprovals();
    } catch (err: any) {
      setActionAlert({
        type: 'error',
        message: err.message || 'Failed to dispatch invoice to PayPal Sandbox.',
      });
    } finally {
      setDispatchingId(null);
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
        className="payflow-tabs-scroll"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
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

        <button
          type="button"
          onClick={() => setActiveTab('reminders')}
          style={{
            padding: '10px 20px',
            background: activeTab === 'reminders' ? 'var(--color-sand)' : 'transparent',
            border: 'none',
            borderBottom: activeTab === 'reminders' ? '2px solid var(--color-ink)' : '2px solid transparent',
            color: 'var(--color-ink)',
            fontWeight: activeTab === 'reminders' ? 600 : 400,
            fontSize: 13,
            cursor: 'pointer',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <span>Payment Reminders</span>
          {reminders.filter((r) => r.status === 'ready_for_approval').length > 0 && (
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
              {reminders.filter((r) => r.status === 'ready_for_approval').length}
            </span>
          )}
        </button>
      </div>

      {/* Main Content */}
      {loading ? (
        <LoadingState label="RETRIEVING APPROVAL REQUESTS..." />
      ) : activeTab === 'reminders' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Reminders Controls & Channel Status */}
          <div
            style={{
              padding: '16px 20px',
              backgroundColor: 'var(--color-cream)',
              border: 'var(--border-hairline)',
              borderRadius: 'var(--radius-sm)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div>
              <div style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600 }}>
                DELIVERY CHANNEL STATUS (PROMPT 22)
              </div>
              <div style={{ fontSize: 13, marginTop: 4, fontWeight: 500 }}>
                {reminders[0]?.channel_label || 'Ready for approval (Manual delivery: no transactional email configured)'}
              </div>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={handleEvaluateReminders}
              disabled={isEvaluatingReminders}
            >
              {isEvaluatingReminders ? 'SCANNING INVOICES...' : 'EVALUATE REMINDERS NOW →'}
            </Button>
          </div>

          {reminders.length === 0 ? (
            <EmptyState
              title="No Payment Reminders in Ledger"
              description="Click 'Evaluate Reminders Now' to scan invoices against policy stages (upcoming, due today, 1-3d, 4-7d, 8-14d, 15+d overdue). Eligible invoices will appear here as unapproved drafts."
              action={
                <Button variant="secondary" size="sm" onClick={handleEvaluateReminders}>
                  Scan Invoices Now
                </Button>
              }
            />
          ) : (
            reminders.map((rem) => (
              <div
                key={rem.id}
                style={{
                  backgroundColor: 'var(--color-sand)',
                  border: 'var(--border-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  padding: 24,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 16,
                }}
              >
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-muted)' }}>
                      INVOICE REMINDER • STAGE: {rem.stage.toUpperCase().replace(/_/g, ' ')}
                    </div>
                    <div style={{ fontFamily: 'var(--font-heading)', fontSize: 18, color: 'var(--color-ink)', marginTop: 4 }}>
                      {rem.invoice_number} — {rem.customer_name}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--color-muted)' }}>
                      Recipient: {rem.customer_email} • Channel: {rem.channel.toUpperCase()}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <StatusLabel status={rem.status} size="sm" />
                  </div>
                </div>

                {/* Inline Editing Form or Message Preview */}
                {editingReminderId === rem.id ? (
                  <div style={{ backgroundColor: 'var(--color-cream)', padding: 16, border: 'var(--border-hairline)' }}>
                    <div style={{ marginBottom: 12 }}>
                      <TextInput
                        label="SUBJECT LINE"
                        value={editSubject}
                        onChange={(e) => setEditSubject(e.target.value)}
                      />
                    </div>
                    <div style={{ marginBottom: 16 }}>
                      <TextArea
                        label="MESSAGE BODY (RESPECTFUL & FACTUAL)"
                        rows={6}
                        value={editBody}
                        onChange={(e) => setEditBody(e.target.value)}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: 10 }}>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => void handleSaveReminderEdit(rem.id)}
                        disabled={isProcessing}
                      >
                        SAVE EDITED COPY
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEditingReminderId(null)}
                      >
                        CANCEL
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      backgroundColor: 'var(--color-cream)',
                      border: 'var(--border-hairline)',
                      padding: 16,
                      fontSize: 13,
                      lineHeight: 1.6,
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'var(--font-body)',
                    }}
                  >
                    <div style={{ fontWeight: 600, marginBottom: 8, borderBottom: 'var(--border-hairline)', paddingBottom: 6 }}>
                      Subject: {rem.subject}
                    </div>
                    {rem.message_body}
                  </div>
                )}

                {/* Failure error notification */}
                {rem.delivery_error && (
                  <div style={{ padding: '8px 12px', backgroundColor: 'var(--color-overdue-bg)', border: '1px solid var(--color-overdue)', color: 'var(--color-overdue)', fontSize: 12 }}>
                    <strong>Delivery Error (Attempt {rem.retry_count}/3):</strong> {rem.delivery_error}
                  </div>
                )}

                {/* Action Buttons */}
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  {rem.status === 'ready_for_approval' && (
                    <>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => void handleApproveReminder(rem.id)}
                        disabled={isProcessing}
                      >
                        APPROVE REMINDER →
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setEditingReminderId(rem.id);
                          setEditSubject(rem.subject);
                          setEditBody(rem.message_body);
                        }}
                      >
                        EDIT COPY
                      </Button>
                    </>
                  )}

                  {rem.status === 'approved' && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => void handleDispatchReminder(rem.id)}
                      disabled={dispatchingId === rem.id}
                    >
                      {dispatchingId === rem.id ? 'DISPATCHING...' : 'DISPATCH REMINDER →'}
                    </Button>
                  )}

                  {rem.status === 'failed' && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => void handleRetryReminder(rem.id)}
                      disabled={dispatchingId === rem.id || rem.retry_count >= 3}
                    >
                      {dispatchingId === rem.id ? 'RETRYING...' : `RETRY DISPATCH (${rem.retry_count}/3) →`}
                    </Button>
                  )}

                  {rem.status === 'sent' && (
                    <div style={{ fontSize: 12, color: 'var(--color-paid)', fontWeight: 600 }}>
                      ✓ Dispatched via {rem.channel.toUpperCase()} {rem.sent_at ? `on ${new Date(rem.sent_at).toLocaleDateString()}` : ''}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
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
                    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))',
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
                        {appr.execution_result_ref && ` (PayPal Ref: ${appr.execution_result_ref})`}
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

                  {appr.status === 'approved' && (
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                      {!appr.execution_result_ref && appr.action_type === 'create_paypal_invoice' ? (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => void handleDispatchToPayPal(appr)}
                          disabled={dispatchingId === appr.id}
                        >
                          {dispatchingId === appr.id ? 'CREATING IN PAYPAL...' : 'DISPATCH TO PAYPAL SANDBOX →'}
                        </Button>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => navigate(`/invoices/${appr.resource_id}`)}
                        >
                          View Invoice Details →
                        </Button>
                      )}
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

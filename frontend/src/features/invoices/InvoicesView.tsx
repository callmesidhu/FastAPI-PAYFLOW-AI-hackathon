import { useEffect, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AgInvoiceGrid,
  Alert,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  LoadingState,
  PageHeader,
  Select,
  StatusLabel,
  TextInput,
} from '../../components';
import { apiClient } from '../../lib/api-client';

interface InvoiceListItem {
  internal_id: string;
  invoice_number: string;
  customer_id: string;
  customer_name?: string | null;
  total: string;
  currency: string;
  issue_date: string;
  due_date: string;
  status: string;
}

interface InvoiceListResponse {
  items: InvoiceListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export const InvoicesView: FC = () => {
  const navigate = useNavigate();

  const [invoices, setInvoices] = useState<InvoiceListItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [viewMode, setViewMode] = useState<'ag-grid' | 'table'>('ag-grid');
  const [actionAlert, setActionAlert] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Draft deletion dialog
  const [invoiceToDelete, setInvoiceToDelete] = useState<InvoiceListItem | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  const loadInvoices = async () => {
    try {
      setLoading(true);
      setActionAlert(null);
      let query = '/api/invoices?page=1&page_size=50';
      if (statusFilter) query += `&status=${statusFilter}`;
      if (searchTerm.trim()) query += `&q=${encodeURIComponent(searchTerm.trim())}`;
      const res = await apiClient<InvoiceListResponse>(query);
      setInvoices(res.items || []);
    } catch (err: any) {
      console.warn('Failed to fetch invoices:', err);
      setInvoices([]);
      setActionAlert({ type: 'error', message: err.message || 'Unable to retrieve invoice records.' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadInvoices();
  }, [statusFilter]);

  const handleDeleteDraft = async () => {
    if (!invoiceToDelete) return;
    try {
      setIsDeleting(true);
      await apiClient(`/api/invoices/${invoiceToDelete.internal_id}`, { method: 'DELETE' });
      setActionAlert({
        type: 'success',
        message: `Draft invoice ${invoiceToDelete.invoice_number} was successfully deleted.`,
      });
      setInvoiceToDelete(null);
      await loadInvoices();
    } catch (err: any) {
      setActionAlert({
        type: 'error',
        message: err.message || 'Failed to delete invoice draft.',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSubmitForApproval = async (e: React.MouseEvent, invoice: InvoiceListItem) => {
    e.stopPropagation();
    try {
      await apiClient(`/api/invoices/${invoice.internal_id}/submit-for-approval`, { method: 'POST' });
      setActionAlert({
        type: 'success',
        message: `Invoice ${invoice.invoice_number} submitted to Approval Center.`,
      });
      await loadInvoices();
    } catch (err: any) {
      setActionAlert({
        type: 'error',
        message: err.message || 'Could not submit invoice for approval.',
      });
    }
  };

  const handleSubmitForApprovalRow = async (invoice: InvoiceListItem) => {
    try {
      await apiClient(`/api/invoices/${invoice.internal_id}/submit-for-approval`, { method: 'POST' });
      setActionAlert({
        type: 'success',
        message: `Invoice ${invoice.invoice_number} submitted to Approval Center.`,
      });
      await loadInvoices();
    } catch (err: any) {
      setActionAlert({
        type: 'error',
        message: err.message || 'Could not submit invoice for approval.',
      });
    }
  };

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', paddingBottom: 64 }}>
      <PageHeader
        eyebrow="RECEIVABLES & SETTLEMENTS"
        title="Invoices"
        subtitle="Manage invoice lifecycle from structured draft through human authorization and PayPal Sandbox delivery."
        actions={
          <Button variant="primary" size="sm" onClick={() => navigate('/invoices/new')}>
            + NEW DRAFT INVOICE
          </Button>
        }
      />

      {actionAlert && (
        <div style={{ marginBottom: 20 }}>
          <Alert
            type={actionAlert.type}
            message={actionAlert.message}
            onDismiss={() => setActionAlert(null)}
          />
        </div>
      )}

      {/* Filter and Search Bar */}
      <div
        style={{
          display: 'flex',
          gap: 16,
          marginBottom: 24,
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          backgroundColor: 'var(--color-sand)',
          padding: 16,
          border: 'var(--border-hairline)',
        }}
      >
        <div style={{ flex: '1 1 220px', minWidth: 0 }}>
          <TextInput
            label="SEARCH INVOICES"
            placeholder="Search by invoice #, customer name, notes..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void loadInvoices();
            }}
          />
        </div>

        <div style={{ flex: '1 1 180px', minWidth: 160 }}>
          <Select
            label="STATUS FILTER"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            options={[
              { value: '', label: 'All Statuses' },
              { value: 'draft', label: 'Draft' },
              { value: 'pending_approval', label: 'Pending Approval' },
              { value: 'sent', label: 'Sent (PayPal)' },
              { value: 'paid', label: 'Paid / Reconciled' },
              { value: 'overdue', label: 'Overdue' },
              { value: 'cancelled', label: 'Cancelled' },
            ]}
          />
        </div>

        <Button variant="secondary" size="md" onClick={() => void loadInvoices()}>
          Filter
        </Button>
      </div>

      {/* Grid Mode Selector Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
          marginBottom: 16,
          padding: '8px 12px',
          backgroundColor: 'var(--color-cream)',
          border: 'var(--border-hairline)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: 'var(--color-muted)',
            }}
          >
            GRID ENGINE:
          </span>
          <Button
            variant={viewMode === 'ag-grid' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setViewMode('ag-grid')}
            style={{ padding: '3px 10px', fontSize: 11 }}
          >
            AG Grid Explorer (Sponsor)
          </Button>
          <Button
            variant={viewMode === 'table' ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setViewMode('table')}
            style={{ padding: '3px 10px', fontSize: 11 }}
          >
            Minimalist Table
          </Button>
        </div>

        <span style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'monospace' }}>
          {invoices.length} {invoices.length === 1 ? 'record' : 'records'} loaded
        </span>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <LoadingState label="RETRIEVING INVOICE RECORDS..." />
      ) : invoices.length === 0 ? (
        <EmptyState
          title="No Invoices Found"
          description={
            statusFilter || searchTerm
              ? 'No invoices match your active search or filter criteria.'
              : 'You have not created any invoices yet. Begin by drafting your first receivable.'
          }
          action={
            <Button variant="primary" size="sm" onClick={() => navigate('/invoices/new')}>
              Draft First Invoice
            </Button>
          }
        />
      ) : viewMode === 'ag-grid' ? (
        <AgInvoiceGrid
          rowData={invoices}
          onSubmitForApproval={(inv) => void handleSubmitForApprovalRow(inv)}
          onDeleteDraft={(inv) => setInvoiceToDelete(inv)}
        />
      ) : (
        <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
          <DataTable<InvoiceListItem>
            columns={[
              {
                key: 'invoice_number',
                header: 'INVOICE #',
                width: '160px',
                render: (it: InvoiceListItem) => (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/invoices/${it.internal_id}`);
                    }}
                    style={{
                      background: 'none',
                      border: 'none',
                      padding: 0,
                      color: 'var(--color-ink)',
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontFamily: 'monospace',
                      textDecoration: 'underline',
                      fontSize: 13,
                    }}
                  >
                    {it.invoice_number}
                  </button>
                ),
              },
              {
                key: 'customer',
                header: 'CLIENT / CUSTOMER',
                render: (it: InvoiceListItem) => (
                  <div>
                    <div style={{ fontWeight: 500, color: 'var(--color-ink)' }}>
                      {it.customer_name || 'Customer'}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'monospace' }}>
                      {it.customer_id}
                    </div>
                  </div>
                ),
              },
              {
                key: 'amount',
                header: 'AMOUNT',
                align: 'right',
                width: '140px',
                render: (it: InvoiceListItem) => (
                  <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                    ${parseFloat(it.total).toFixed(2)}{' '}
                    <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>{it.currency}</span>
                  </span>
                ),
              },
              {
                key: 'issue_date',
                header: 'ISSUE DATE',
                width: '120px',
                render: (it: InvoiceListItem) => <span style={{ fontSize: 13 }}>{it.issue_date}</span>,
              },
              {
                key: 'due_date',
                header: 'DUE DATE',
                width: '130px',
                render: (it: InvoiceListItem) => {
                  const todayStr = new Date().toISOString().split('T')[0] || '';
                  const isPastDue =
                    ['sent', 'unpaid', 'overdue'].includes(it.status) &&
                    Boolean(it.due_date) &&
                    new Date(it.due_date).getTime() < new Date(todayStr).getTime();

                  return (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 13, color: isPastDue ? 'var(--color-overdue)' : 'inherit', fontWeight: isPastDue ? 600 : 400 }}>
                        {it.due_date}
                      </span>
                      {isPastDue && (
                        <span
                          style={{
                            fontSize: 9,
                            padding: '1px 4px',
                            backgroundColor: 'var(--color-overdue-bg)',
                            color: 'var(--color-overdue)',
                            border: '1px solid var(--color-overdue)',
                            textTransform: 'uppercase',
                          }}
                        >
                          LATE
                        </span>
                      )}
                    </div>
                  );
                },
              },
              {
                key: 'status',
                header: 'STATUS',
                width: '150px',
                render: (it: InvoiceListItem) => <StatusLabel status={it.status} size="sm" />,
              },
              {
                key: 'actions',
                header: 'ACTIONS',
                width: '180px',
                align: 'right',
                render: (it: InvoiceListItem) => (
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/invoices/${it.internal_id}`);
                      }}
                    >
                      View
                    </Button>

                    {it.status === 'draft' && (
                      <>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/invoices/${it.internal_id}/edit`);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={(e) => void handleSubmitForApproval(e, it)}
                        >
                          Submit
                        </Button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setInvoiceToDelete(it);
                          }}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--color-overdue)',
                            cursor: 'pointer',
                            fontSize: 12,
                            padding: '4px 6px',
                          }}
                          title="Delete draft"
                        >
                          ✕
                        </button>
                      </>
                    )}

                    {it.status === 'pending_approval' && (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate('/approvals');
                        }}
                      >
                        Approve →
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
            data={invoices}
            keyExtractor={(it: InvoiceListItem) => it.internal_id}
            onRowClick={(it: InvoiceListItem) => navigate(`/invoices/${it.internal_id}`)}
          />
        </div>
      )}

      {/* Delete Draft Confirmation Dialog */}
      <ConfirmDialog
        isOpen={Boolean(invoiceToDelete)}
        title="Delete Draft Invoice?"
        message={
          invoiceToDelete
            ? `Are you sure you want to permanently delete draft ${invoiceToDelete.invoice_number}? This cannot be undone.`
            : ''
        }
        confirmLabel={isDeleting ? 'Deleting...' : 'Delete Draft'}
        cancelLabel="Keep Draft"
        variant="danger"
        isLoading={isDeleting}
        onConfirm={() => void handleDeleteDraft()}
        onCancel={() => setInvoiceToDelete(null)}
      />
    </div>
  );
};

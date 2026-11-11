import { useEffect, useState, type FC, type FormEvent } from 'react';
import {
  Alert,
  Button,
  ConfirmDialog,
  DataTable,
  EmptyState,
  LoadingState,
  PageHeader,
  StatusLabel,
  TextArea,
  TextInput,
} from '../../components';
import { apiClient } from '../../lib/api-client';

interface BillingAddress {
  address_line_1?: string | null;
  address_line_2?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  country_code: string;
}

interface CustomerItem {
  id: string;
  name: string;
  email: string;
  company?: string | null;
  billing_address?: BillingAddress | null;
  notes?: string | null;
  is_active: boolean;
  invoice_count: number;
  created_at: string;
  updated_at: string;
}

interface CustomerListResponse {
  items: CustomerItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export const CustomersView: FC = () => {
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Add Customer Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [formName, setFormName] = useState<string>('');
  const [formEmail, setFormEmail] = useState<string>('');
  const [formCompany, setFormCompany] = useState<string>('');
  const [formAddress1, setFormAddress1] = useState<string>('');
  const [formCity, setFormCity] = useState<string>('');
  const [formState, setFormState] = useState<string>('');
  const [formPostal, setFormPostal] = useState<string>('');
  const [formCountry, setFormCountry] = useState<string>('US');
  const [formNotes, setFormNotes] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);

  // Customer Detail / Archive state
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerItem | null>(null);
  const [customerToArchive, setCustomerToArchive] = useState<CustomerItem | null>(null);
  const [isArchiving, setIsArchiving] = useState<boolean>(false);

  const loadCustomers = async () => {
    try {
      setLoading(true);
      let query = '/api/customers?page=1&page_size=50';
      if (search.trim()) query += `&q=${encodeURIComponent(search.trim())}`;
      const res = await apiClient<CustomerListResponse>(query);
      setCustomers(res.items || []);
    } catch (err: any) {
      console.warn('Failed to fetch customers:', err);
      setCustomers([]);
      setStatusMessage({ type: 'error', message: err.message || 'Unable to load customer directory.' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCustomers();
  }, []);

  const resetForm = () => {
    setFormName('');
    setFormEmail('');
    setFormCompany('');
    setFormAddress1('');
    setFormCity('');
    setFormState('');
    setFormPostal('');
    setFormCountry('US');
    setFormNotes('');
    setFormError(null);
  };

  const handleCreateCustomer = async (e: FormEvent) => {
    e.preventDefault();
    if (!formName.trim() || !formEmail.trim()) {
      setFormError('Contact name and billing email are required.');
      return;
    }

    setFormError(null);
    setIsSubmitting(true);

    try {
      const payload: any = {
        name: formName.trim(),
        email: formEmail.trim(),
        company: formCompany.trim() || undefined,
        notes: formNotes.trim() || undefined,
      };

      if (formAddress1.trim() || formCity.trim()) {
        payload.billing_address = {
          address_line_1: formAddress1.trim() || undefined,
          city: formCity.trim() || undefined,
          state: formState.trim() || undefined,
          postal_code: formPostal.trim() || undefined,
          country_code: formCountry.trim().toUpperCase() || 'US',
        };
      }

      const created = await apiClient<CustomerItem>('/api/customers', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      setStatusMessage({
        type: 'success',
        message: `Customer ${created.name} (${created.email}) created successfully.`,
      });
      setIsAddModalOpen(false);
      resetForm();
      await loadCustomers();
    } catch (err: any) {
      setFormError(err.message || 'Failed to create customer record.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleArchiveCustomer = async () => {
    if (!customerToArchive) return;
    try {
      setIsArchiving(true);
      await apiClient(`/api/customers/${customerToArchive.id}`, { method: 'DELETE' });
      setStatusMessage({
        type: 'success',
        message: `Customer ${customerToArchive.name} was safely archived.`,
      });
      setCustomerToArchive(null);
      setSelectedCustomer(null);
      await loadCustomers();
    } catch (err: any) {
      setStatusMessage({
        type: 'error',
        message: err.message || 'Failed to archive customer record.',
      });
      setCustomerToArchive(null);
    } finally {
      setIsArchiving(false);
    }
  };

  return (
    <div>
      <PageHeader
        eyebrow="CLIENT RELATIONSHIPS"
        title="Customers"
        subtitle="Manage client identities and verified billing contact information scoped strictly to your account."
        actions={
          <Button variant="primary" size="sm" onClick={() => setIsAddModalOpen(true)}>
            + ADD CUSTOMER
          </Button>
        }
      />

      {statusMessage && (
        <div style={{ marginBottom: '24px' }}>
          <Alert
            type={statusMessage.type}
            message={statusMessage.message}
            onDismiss={() => setStatusMessage(null)}
          />
        </div>
      )}

      {/* Search Bar */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 220px', minWidth: 0 }}>
          <TextInput
            placeholder="Search customers by name, company, or email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void loadCustomers();
            }}
          />
        </div>
        <Button variant="secondary" size="md" onClick={() => void loadCustomers()}>
          SEARCH
        </Button>
      </div>

      {loading ? (
        <LoadingState label="FETCHING CUSTOMER DIRECTORY..." />
      ) : customers.length === 0 ? (
        <EmptyState
          title="No Customers Registered"
          description="You have not created any customer accounts yet. Add clients before generating invoices."
          action={
            <Button variant="primary" size="sm" onClick={() => setIsAddModalOpen(true)}>
              ADD FIRST CUSTOMER
            </Button>
          }
        />
      ) : (
        <DataTable<CustomerItem>
          columns={[
            { key: 'name', header: 'Contact Name', width: '220px' },
            { key: 'company', header: 'Company / Studio', render: (c) => c.company || '—' },
            { key: 'email', header: 'Billing Email' },
            {
              key: 'invoices',
              header: 'Invoices',
              width: '100px',
              render: (c) => `${c.invoice_count || 0}`,
            },
            {
              key: 'status',
              header: 'Status',
              width: '100px',
              render: (c) => <StatusLabel status={c.is_active ? 'paid' : 'draft'} size="sm" />,
            },
            {
              key: 'created_at',
              header: 'Added',
              width: '120px',
              render: (c) => c.created_at.slice(0, 10),
            },
          ]}
          data={customers}
          keyExtractor={(c) => c.id}
          onRowClick={(c) => setSelectedCustomer(c)}
        />
      )}

      {/* =========================================================================
          ADD CUSTOMER MODAL
          ========================================================================= */}
      {isAddModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 999,
            backgroundColor: 'rgba(11, 11, 11, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
        >
          <div
            className="payflow-modal-card"
            style={{
              width: '100%',
              maxWidth: '560px',
              maxHeight: '90vh',
              overflowY: 'auto',
              backgroundColor: 'var(--color-bg)',
              border: 'var(--border-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '32px',
            }}
          >
            <div style={{ marginBottom: '20px' }}>
              <div
                style={{
                  fontSize: '0.675rem',
                  letterSpacing: 'var(--tracking-widest)',
                  textTransform: 'uppercase',
                  color: 'var(--color-muted)',
                  marginBottom: '4px',
                }}
              >
                NEW CLIENT PROFILE
              </div>
              <h2
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.4rem',
                  margin: 0,
                  fontWeight: 700,
                  letterSpacing: 'var(--tracking-wide)',
                }}
              >
                Register Customer
              </h2>
            </div>

            {formError && (
              <div style={{ marginBottom: '16px' }}>
                <Alert type="error" message={formError} onDismiss={() => setFormError(null)} />
              </div>
            )}

            <form onSubmit={handleCreateCustomer} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <TextInput
                label="Full Name or Representative *"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="Sarah Connor"
                required
              />

              <TextInput
                label="Billing Email Address *"
                type="email"
                value={formEmail}
                onChange={(e) => setFormEmail(e.target.value)}
                placeholder="billing@cyberdyne.example.com"
                required
              />

              <TextInput
                label="Company / Studio Name (Optional)"
                value={formCompany}
                onChange={(e) => setFormCompany(e.target.value)}
                placeholder="Cyberdyne Systems LLC"
              />

              {/* Billing Address Subsection */}
              <div
                style={{
                  padding: '16px',
                  backgroundColor: 'var(--color-cream)',
                  border: 'var(--border-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                }}
              >
                <div
                  style={{
                    fontSize: '0.675rem',
                    letterSpacing: 'var(--tracking-wider)',
                    textTransform: 'uppercase',
                    fontWeight: 600,
                    color: 'var(--color-ink)',
                  }}
                >
                  Postal Billing Address (Optional, for PayPal Invoices)
                </div>

                <TextInput
                  label="Address Line 1"
                  value={formAddress1}
                  onChange={(e) => setFormAddress1(e.target.value)}
                  placeholder="100 Tech Blvd"
                />

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 160px), 1fr))', gap: '12px' }}>
                  <TextInput
                    label="City"
                    value={formCity}
                    onChange={(e) => setFormCity(e.target.value)}
                    placeholder="Austin"
                  />
                  <TextInput
                    label="State / Region"
                    value={formState}
                    onChange={(e) => setFormState(e.target.value)}
                    placeholder="TX"
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 160px), 1fr))', gap: '12px' }}>
                  <TextInput
                    label="Postal / ZIP Code"
                    value={formPostal}
                    onChange={(e) => setFormPostal(e.target.value)}
                    placeholder="78701"
                  />
                  <TextInput
                    label="Country Code (ISO-2)"
                    value={formCountry}
                    onChange={(e) => setFormCountry(e.target.value.toUpperCase())}
                    placeholder="US"
                    maxLength={2}
                  />
                </div>
              </div>

              <TextArea
                label="Internal Billing Notes (Optional)"
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="Payment terms: Net-14. Preferred contact: via email."
                rows={2}
              />

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px', flexWrap: 'wrap' }}>
                <Button
                  type="button"
                  variant="outline"
                  size="md"
                  disabled={isSubmitting}
                  onClick={() => {
                    setIsAddModalOpen(false);
                    resetForm();
                  }}
                >
                  CANCEL
                </Button>
                <Button type="submit" variant="primary" size="md" isLoading={isSubmitting}>
                  CREATE CUSTOMER →
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          CUSTOMER DETAIL MODAL
          ========================================================================= */}
      {selectedCustomer && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 999,
            backgroundColor: 'rgba(11, 11, 11, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
          }}
        >
          <div
            className="payflow-modal-card"
            style={{
              width: '100%',
              maxWidth: '520px',
              maxHeight: '90vh',
              overflowY: 'auto',
              backgroundColor: 'var(--color-bg)',
              border: 'var(--border-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '32px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <div
                  style={{
                    fontSize: '0.675rem',
                    letterSpacing: 'var(--tracking-widest)',
                    textTransform: 'uppercase',
                    color: 'var(--color-muted)',
                    marginBottom: '4px',
                  }}
                >
                  CUSTOMER RECORD
                </div>
                <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: '1.4rem', margin: 0, fontWeight: 700 }}>
                  {selectedCustomer.name}
                </h2>
              </div>
              <StatusLabel status={selectedCustomer.is_active ? 'paid' : 'draft'} size="sm" />
            </div>

            <div
              style={{
                backgroundColor: 'var(--color-cream)',
                border: 'var(--border-hairline)',
                padding: '20px',
                borderRadius: 'var(--radius-sm)',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                fontSize: '0.85rem',
                marginBottom: '20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-muted)' }}>Email</span>
                <span style={{ fontWeight: 600 }}>{selectedCustomer.email}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-muted)' }}>Company</span>
                <span style={{ fontWeight: 600 }}>{selectedCustomer.company || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--color-muted)' }}>Linked Invoices</span>
                <span style={{ fontWeight: 600 }}>{selectedCustomer.invoice_count || 0} invoice(s)</span>
              </div>
              {selectedCustomer.billing_address && (
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--color-muted)' }}>Location</span>
                  <span style={{ fontWeight: 600 }}>
                    {[
                      selectedCustomer.billing_address.city,
                      selectedCustomer.billing_address.state,
                      selectedCustomer.billing_address.country_code,
                    ]
                      .filter(Boolean)
                      .join(', ')}
                  </span>
                </div>
              )}
              {selectedCustomer.notes && (
                <div style={{ borderTop: '1px solid rgba(58, 52, 44, 0.15)', paddingTop: '10px' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--color-muted)', textTransform: 'uppercase', marginBottom: '2px' }}>
                    Billing Notes
                  </div>
                  <div>{selectedCustomer.notes}</div>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
              <Button
                variant="danger"
                size="sm"
                onClick={() => setCustomerToArchive(selectedCustomer)}
              >
                ARCHIVE CUSTOMER
              </Button>
              <Button variant="outline" size="sm" onClick={() => setSelectedCustomer(null)}>
                CLOSE
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          ARCHIVE CONFIRMATION DIALOG
          ========================================================================= */}
      <ConfirmDialog
        isOpen={!!customerToArchive}
        title="ARCHIVE CUSTOMER"
        message={
          customerToArchive?.invoice_count && customerToArchive.invoice_count > 0 ? (
            <span>
              This customer has <strong>{customerToArchive.invoice_count} linked invoice(s)</strong>.
              Deletion is blocked to maintain historical financial integrity.
            </span>
          ) : (
            `Are you sure you want to archive "${customerToArchive?.name}"? The customer will be hidden from active lists.`
          )
        }
        confirmLabel={
          customerToArchive?.invoice_count && customerToArchive.invoice_count > 0
            ? 'CANNOT DELETE'
            : 'CONFIRM ARCHIVE'
        }
        variant="danger"
        isLoading={isArchiving}
        onConfirm={handleArchiveCustomer}
        onCancel={() => setCustomerToArchive(null)}
      />
    </div>
  );
};

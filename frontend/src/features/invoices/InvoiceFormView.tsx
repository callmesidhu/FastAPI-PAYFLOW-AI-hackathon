import { useEffect, useState, type FC, type FormEvent } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  LoadingState,
  PageHeader,
  Select,
  TextArea,
  TextInput,
} from '../../components';
import { apiClient } from '../../lib/api-client';

interface CustomerOption {
  id: string;
  name: string;
  email: string;
  company?: string | null;
}

interface LineItemState {
  id: string;
  name: string;
  description: string;
  quantity: string;
  unit_price: string;
  tax: string;
}

interface InvoiceDetailResponse {
  internal_id: string;
  invoice_number: string;
  customer_id: string;
  customer_name?: string | null;
  currency: string;
  issue_date: string;
  due_date: string;
  status: string;
  notes?: string | null;
  items: Array<{
    name: string;
    description?: string | null;
    quantity: string | number;
    unit_price: string;
    tax: string;
    total: string;
  }>;
}

export const InvoiceFormView: FC = () => {
  const { id } = useParams<{ id?: string }>();
  const isEditMode = Boolean(id);
  const navigate = useNavigate();

  // Form State
  const [customerId, setCustomerId] = useState<string>('');
  const [invoiceNumber, setInvoiceNumber] = useState<string>('');
  const [currency, setCurrency] = useState<string>('USD');
  const [issueDate, setIssueDate] = useState<string>(() => {
    const today = new Date().toISOString().split('T')[0];
    return today || '2026-11-10';
  });
  const [dueDate, setDueDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    const due = d.toISOString().split('T')[0];
    return due || '2026-11-24';
  });
  const [notes, setNotes] = useState<string>('Payment due within 14 days via PayPal Sandbox.');

  const [items, setItems] = useState<LineItemState[]>([
    {
      id: 'item-1',
      name: '',
      description: '',
      quantity: '1.00',
      unit_price: '0.00',
      tax: '0.00',
    },
  ]);

  // Aux state
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  // Quick inline customer creation state
  const [showQuickCustomer, setShowQuickCustomer] = useState<boolean>(false);
  const [newCustName, setNewCustName] = useState<string>('');
  const [newCustEmail, setNewCustEmail] = useState<string>('');
  const [newCustCompany, setNewCustCompany] = useState<string>('');
  const [quickCustLoading, setQuickCustLoading] = useState<boolean>(false);

  // AI Fast-Draft state (Prompt 19)
  const [fastDraftText, setFastDraftText] = useState<string>('');
  const [fastDraftLoading, setFastDraftLoading] = useState<boolean>(false);
  const [fastDraftSuggestionNotice, setFastDraftSuggestionNotice] = useState<string | null>(null);
  const [fastDraftClarification, setFastDraftClarification] = useState<string | null>(null);
  const [fastDraftMatches, setFastDraftMatches] = useState<CustomerOption[]>([]);

  const handleFastDraftExtract = async (overrideText?: string) => {
    const textToExtract = overrideText || fastDraftText;
    if (!textToExtract.trim() || fastDraftLoading) return;
    setFastDraftLoading(true);
    setFastDraftClarification(null);
    setFastDraftMatches([]);
    setFastDraftSuggestionNotice(null);

    try {
      const res = await apiClient<{
        is_suggestion: boolean;
        clarification_needed: boolean;
        clarification_question?: string | null;
        ambiguity_reason?: string | null;
        customer_matches: CustomerOption[];
        extracted_draft?: {
          customer_id?: string | null;
          customer_name: string;
          currency: string;
          due_date: string;
          notes?: string | null;
          items: Array<{ name: string; quantity: string | number; unit_price: string | number; tax: string | number }>;
        } | null;
      }>('/api/ai/extract-invoice', {
        method: 'POST',
        body: JSON.stringify({
          text: textToExtract.trim(),
          timezone: 'UTC',
        }),
      });

      if (res.clarification_needed) {
        setFastDraftClarification(res.clarification_question || 'Additional clarification required.');
        if (res.customer_matches && res.customer_matches.length > 0) {
          setFastDraftMatches(res.customer_matches);
        }
        return;
      }

      if (res.extracted_draft) {
        const d = res.extracted_draft;
        if (d.customer_id) {
          setCustomerId(d.customer_id);
        }
        if (d.currency) {
          setCurrency(d.currency);
        }
        if (d.due_date) {
          setDueDate(d.due_date);
        }
        if (d.notes) {
          setNotes(d.notes);
        }
        if (d.items && d.items.length > 0) {
          setItems(
            d.items.map((it, idx) => ({
              id: `fast-item-${idx + 1}`,
              name: it.name,
              description: '',
              quantity: String(it.quantity),
              unit_price: String(it.unit_price),
              tax: String(it.tax || '0.00'),
            }))
          );
        }
        setFastDraftSuggestionNotice(
          '✦ AI SUGGESTION EXTRACTED (UNCONFIRMED): Pre-filled below. Review and edit before saving as an authoritative draft.'
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to extract invoice parameters.';
      setFastDraftClarification(msg);
    } finally {
      setFastDraftLoading(false);
    }
  };

  // Load initial data: customers and existing invoice if editing
  useEffect(() => {
    let isMounted = true;

    const loadData = async () => {
      try {
        setIsLoading(true);
        setErrorBanner(null);

        // Fetch customers
        const custRes = await apiClient<{ items: CustomerOption[] }>('/api/customers?page_size=100');
        if (isMounted) {
          const list = custRes.items || [];
          setCustomers(list);
          if (list.length > 0 && list[0] && !customerId) {
            setCustomerId(list[0].id);
          }
        }

        // If editing existing invoice, load its fields
        if (isEditMode && id) {
          const inv = await apiClient<InvoiceDetailResponse>(`/api/invoices/${id}`);
          if (isMounted) {
            if (inv.status !== 'draft') {
              setErrorBanner(`Invoice ${inv.invoice_number} is in '${inv.status}' status and cannot be edited. Only drafts are editable.`);
              return;
            }
            setCustomerId(inv.customer_id);
            setInvoiceNumber(inv.invoice_number);
            setCurrency(inv.currency);
            setIssueDate(inv.issue_date);
            setDueDate(inv.due_date);
            setNotes(inv.notes || '');
            if (inv.items && inv.items.length > 0) {
              setItems(
                inv.items.map((it, idx) => ({
                  id: `item-${idx + 1}`,
                  name: it.name,
                  description: it.description || '',
                  quantity: String(it.quantity),
                  unit_price: String(it.unit_price),
                  tax: String(it.tax || '0.00'),
                }))
              );
            }
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setErrorBanner(err.message || 'Failed to load invoice form data.');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void loadData();

    return () => {
      isMounted = false;
    };
  }, [id, isEditMode]);

  // Line item manipulation
  const handleAddItem = () => {
    setItems((prev) => [
      ...prev,
      {
        id: `item-${Date.now()}`,
        name: '',
        description: '',
        quantity: '1.00',
        unit_price: '0.00',
        tax: '0.00',
      },
    ]);
  };

  const handleRemoveItem = (index: number) => {
    if (items.length <= 1) return;
    setItems((prev) => prev.filter((_, idx) => idx !== index));
  };

  const handleItemChange = (index: number, field: keyof LineItemState, value: string) => {
    setItems((prev) => {
      const copy = [...prev];
      const target = copy[index];
      if (target) {
        copy[index] = {
          ...target,
          [field]: value,
        };
      }
      return copy;
    });
  };

  // Live client preview calculation (server remains authoritative)
  const previewSubtotal = items.reduce((sum, item) => {
    const qty = parseFloat(item.quantity) || 0;
    const price = parseFloat(item.unit_price) || 0;
    return sum + qty * price;
  }, 0);

  const previewTax = items.reduce((sum, item) => {
    const tax = parseFloat(item.tax) || 0;
    return sum + tax;
  }, 0);

  const previewTotal = previewSubtotal + previewTax;

  // Quick customer error state
  const [quickCustError, setQuickCustError] = useState<string | null>(null);

  // Handle quick inline customer creation
  const handleCreateQuickCustomer = async () => {
    setQuickCustError(null);
    if (!newCustName.trim() || !newCustEmail.trim()) {
      setQuickCustError('Please enter a customer name and valid email.');
      return;
    }
    try {
      setQuickCustLoading(true);
      const newCust = await apiClient<CustomerOption>('/api/customers', {
        method: 'POST',
        body: JSON.stringify({
          name: newCustName.trim(),
          email: newCustEmail.trim(),
          company: newCustCompany.trim() || undefined,
        }),
      });
      setCustomers((prev) => [newCust, ...prev]);
      setCustomerId(newCust.id);
      setShowQuickCustomer(false);
      setNewCustName('');
      setNewCustEmail('');
      setNewCustCompany('');
    } catch (err: any) {
      setQuickCustError(err.message || 'Failed to create customer.');
    } finally {
      setQuickCustLoading(false);
    }
  };

  // Form submission: save draft, and optionally submit for approval
  const handleSubmit = async (e: FormEvent, submitForApproval = false) => {
    e.preventDefault();
    setErrorBanner(null);

    // Basic frontend checks
    if (!customerId) {
      setErrorBanner('Please select or create a customer.');
      return;
    }

    if (items.some((it) => !it.name.trim())) {
      setErrorBanner('All line items must have a service or product name.');
      return;
    }

    if (new Date(dueDate) < new Date(issueDate)) {
      setErrorBanner('Due date cannot precede the issue date.');
      return;
    }

    try {
      setIsSubmitting(true);

      const payload = {
        customer_id: customerId,
        invoice_number: invoiceNumber.trim() || undefined,
        currency,
        issue_date: issueDate,
        due_date: dueDate,
        notes: notes.trim() || undefined,
        items: items.map((it) => ({
          name: it.name.trim(),
          description: it.description.trim() || undefined,
          quantity: it.quantity,
          unit_price: it.unit_price,
          tax: it.tax || '0.00',
        })),
      };

      let savedInvoice: InvoiceDetailResponse;

      if (isEditMode && id) {
        // Edit draft
        savedInvoice = await apiClient<InvoiceDetailResponse>(`/api/invoices/${id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        });
      } else {
        // Create new draft
        savedInvoice = await apiClient<InvoiceDetailResponse>('/api/invoices', {
          method: 'POST',
          body: JSON.stringify(payload),
        });
      }

      if (submitForApproval) {
        // Immediately submit for human approval
        await apiClient(`/api/invoices/${savedInvoice.internal_id}/submit-for-approval`, {
          method: 'POST',
        });
        navigate('/approvals');
      } else {
        navigate(`/invoices/${savedInvoice.internal_id}`);
      }
    } catch (err: any) {
      console.error('Invoice save failed:', err);
      // Format backend validation message
      let msg = err.message || 'Failed to save invoice.';
      if (err.data?.detail) {
        if (typeof err.data.detail === 'string') {
          msg = err.data.detail;
        } else if (Array.isArray(err.data.detail)) {
          msg = err.data.detail.map((d: any) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(', ');
        }
      }
      setErrorBanner(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return <LoadingState label="LOADING INVOICE COMPOSER..." />;
  }

  return (
    <div style={{ maxWidth: 1040, margin: '0 auto', paddingBottom: 64 }}>
      <PageHeader
        eyebrow={isEditMode ? 'EDIT DRAFT INVOICE' : 'NEW RECEIVABLE'}
        title={isEditMode ? `Edit Invoice ${invoiceNumber || ''}` : 'Draft New Invoice'}
        subtitle="Authoritative server-side Decimal calculations apply. Drafts can be reviewed and submitted for approval."
        actions={
          <Button variant="outline" size="sm" onClick={() => navigate('/invoices')}>
            ← Back to Invoices
          </Button>
        }
      />

      {errorBanner && (
        <div style={{ marginBottom: 24 }}>
          <Alert
            type="error"
            title="Unable to Save Invoice"
            message={errorBanner}
            onDismiss={() => setErrorBanner(null)}
          />
        </div>
      )}

      {!isEditMode && (
        <div
          style={{
            backgroundColor: 'var(--color-cream)',
            border: 'var(--border-hairline)',
            borderRadius: 'var(--radius-sm)',
            padding: 20,
            marginBottom: 24,
          }}
        >
          <div
            style={{
              fontSize: 12,
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--color-muted)',
              fontWeight: 600,
              marginBottom: 6,
            }}
          >
            AI NATURAL LANGUAGE FAST-DRAFT (PROMPT 19)
          </div>
          <p style={{ fontSize: 13, color: 'var(--color-ink)', margin: '0 0 12px 0' }}>
            Type a natural billing instruction (e.g. <em>"Create a $500 invoice for John Smith for website development, due in seven days"</em>) to extract and auto-populate this form.
          </p>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <div style={{ flex: 1 }}>
              <TextInput
                value={fastDraftText}
                onChange={(e) => setFastDraftText(e.target.value)}
                placeholder="e.g. Create a $500 invoice for John Smith for website development, due in seven days"
                disabled={fastDraftLoading}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    void handleFastDraftExtract();
                  }
                }}
              />
            </div>
            <Button
              type="button"
              variant="primary"
              size="md"
              onClick={() => void handleFastDraftExtract()}
              disabled={fastDraftLoading || !fastDraftText.trim()}
            >
              {fastDraftLoading ? 'EXTRACTING...' : 'EXTRACT WITH AI →'}
            </Button>
          </div>

          {fastDraftClarification && (
            <div
              style={{
                marginTop: 12,
                padding: '10px 14px',
                backgroundColor: 'var(--color-overdue-bg)',
                border: '1px solid var(--color-overdue)',
                color: 'var(--color-overdue)',
                fontSize: 13,
                borderRadius: 'var(--radius-sm)',
              }}
            >
              <strong>Clarification Needed:</strong> {fastDraftClarification}
            </div>
          )}

          {fastDraftMatches.length > 0 && (
            <div style={{ marginTop: 12, padding: 12, backgroundColor: 'var(--color-bg)', border: 'var(--border-hairline)' }}>
              <div style={{ fontSize: 11, textTransform: 'uppercase', fontWeight: 600, marginBottom: 8 }}>
                Select Customer from Disambiguation List:
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {fastDraftMatches.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => {
                      setCustomerId(m.id);
                      setFastDraftMatches([]);
                      setFastDraftClarification(null);
                      setFastDraftSuggestionNotice(`Selected client: ${m.name} (${m.email}). Review pre-filled parameters below.`);
                    }}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: 'var(--color-sand)',
                      border: 'var(--border-hairline)',
                      borderRadius: 'var(--radius-sm)',
                      cursor: 'pointer',
                      fontSize: 12,
                      fontFamily: 'var(--font-body)',
                    }}
                  >
                    → {m.name} ({m.email})
                  </button>
                ))}
              </div>
            </div>
          )}

          {fastDraftSuggestionNotice && (
            <div
              style={{
                marginTop: 12,
                padding: '10px 14px',
                backgroundColor: 'var(--color-paid-bg)',
                border: '1px solid var(--color-paid)',
                color: 'var(--color-paid)',
                fontSize: 13,
                borderRadius: 'var(--radius-sm)',
              }}
            >
              {fastDraftSuggestionNotice}
            </div>
          )}
        </div>
      )}

      <form onSubmit={(e) => void handleSubmit(e, false)}>
        {/* Section 1: Customer & Invoice Reference */}
        <div
          style={{
            backgroundColor: 'var(--color-sand)',
            border: 'var(--border-hairline)',
            padding: 24,
            marginBottom: 24,
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
            1. Client & Billing Parameters
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 20 }}>
            <div>
              <Select
                label="CLIENT / CUSTOMER *"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                options={customers.map((c) => ({
                  value: c.id,
                  label: `${c.name} (${c.email})${c.company ? ` — ${c.company}` : ''}`,
                }))}
                helperText={customers.length === 0 ? 'No customers found. Create one below.' : undefined}
              />
              <div style={{ marginTop: 8 }}>
                <button
                  type="button"
                  onClick={() => setShowQuickCustomer(!showQuickCustomer)}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    color: 'var(--color-ink)',
                    textDecoration: 'underline',
                    fontSize: 12,
                    cursor: 'pointer',
                    fontFamily: 'var(--font-body)',
                  }}
                >
                  {showQuickCustomer ? '− Hide customer creator' : '+ Quick-create new client'}
                </button>
              </div>

              {/* Inline quick customer modal/box */}
              {showQuickCustomer && (
                <div
                  style={{
                    marginTop: 12,
                    padding: 16,
                    backgroundColor: 'var(--color-cream)',
                    border: 'var(--border-hairline)',
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8, textTransform: 'uppercase' }}>
                    Quick Client Entry
                  </div>
                  {quickCustError && (
                    <div style={{ marginBottom: 8 }}>
                      <Alert type="error" message={quickCustError} onDismiss={() => setQuickCustError(null)} />
                    </div>
                  )}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <TextInput
                      label="Client Name"
                      value={newCustName}
                      onChange={(e) => setNewCustName(e.target.value)}
                      placeholder="e.g. Acme Studio"
                    />
                    <TextInput
                      label="Client Email"
                      type="email"
                      value={newCustEmail}
                      onChange={(e) => setNewCustEmail(e.target.value)}
                      placeholder="billing@acme.com"
                    />
                    <TextInput
                      label="Company (Optional)"
                      value={newCustCompany}
                      onChange={(e) => setNewCustCompany(e.target.value)}
                      placeholder="Acme Corp LLC"
                    />
                    <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={quickCustLoading}
                        onClick={() => void handleCreateQuickCustomer()}
                      >
                        {quickCustLoading ? 'Saving...' : 'Add Client'}
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setShowQuickCustomer(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <TextInput
              label="INVOICE NUMBER (OPTIONAL)"
              value={invoiceNumber}
              onChange={(e) => setInvoiceNumber(e.target.value)}
              placeholder="Auto-generated if blank (e.g. INV-2026-0001)"
              helperText="Leave blank to use sequential numbering"
            />

            <Select
              label="CURRENCY (ISO 4217) *"
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              options={[
                { value: 'USD', label: 'USD — US Dollar ($)' },
                { value: 'EUR', label: 'EUR — Euro (€)' },
                { value: 'GBP', label: 'GBP — British Pound (£)' },
                { value: 'CAD', label: 'CAD — Canadian Dollar ($)' },
                { value: 'AUD', label: 'AUD — Australian Dollar ($)' },
                { value: 'JPY', label: 'JPY — Japanese Yen (¥)' },
              ]}
            />
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 20,
              marginTop: 20,
            }}
          >
            <TextInput
              label="ISSUE DATE *"
              type="date"
              value={issueDate}
              onChange={(e) => setIssueDate(e.target.value)}
            />
            <TextInput
              label="DUE DATE *"
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              helperText="Must be on or after issue date"
            />
          </div>
        </div>

        {/* Section 2: Dynamic Line Items */}
        <div
          style={{
            backgroundColor: 'var(--color-sand)',
            border: 'var(--border-hairline)',
            padding: 24,
            marginBottom: 24,
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              borderBottom: 'var(--border-hairline)',
              paddingBottom: 8,
              marginBottom: 16,
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
              2. Line Items ({items.length})
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={handleAddItem}>
              + Add Item
            </Button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {items.map((item, index) => {
              const lineTotal = (
                (parseFloat(item.quantity) || 0) * (parseFloat(item.unit_price) || 0) +
                (parseFloat(item.tax) || 0)
              ).toFixed(2);

              return (
                <div
                  key={item.id}
                  style={{
                    backgroundColor: 'var(--color-cream)',
                    border: 'var(--border-hairline)',
                    padding: 16,
                    position: 'relative',
                  }}
                >
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '2fr 1fr 1fr 1fr auto',
                      gap: 12,
                      alignItems: 'start',
                    }}
                  >
                    <div>
                      <TextInput
                        label={`ITEM #${index + 1} NAME *`}
                        value={item.name}
                        onChange={(e) => handleItemChange(index, 'name', e.target.value)}
                        placeholder="Service or product description"
                      />
                      <div style={{ marginTop: 8 }}>
                        <TextInput
                          label="DESCRIPTION (OPTIONAL)"
                          value={item.description}
                          onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                          placeholder="Scope details or deliverable notes"
                        />
                      </div>
                    </div>

                    <TextInput
                      label="QTY *"
                      type="number"
                      step="0.01"
                      min="0.01"
                      value={item.quantity}
                      onChange={(e) => handleItemChange(index, 'quantity', e.target.value)}
                    />

                    <TextInput
                      label={`UNIT PRICE (${currency}) *`}
                      type="number"
                      step="0.01"
                      min="0.00"
                      value={item.unit_price}
                      onChange={(e) => handleItemChange(index, 'unit_price', e.target.value)}
                    />

                    <TextInput
                      label="TAX"
                      type="number"
                      step="0.01"
                      min="0.00"
                      value={item.tax}
                      onChange={(e) => handleItemChange(index, 'tax', e.target.value)}
                    />

                    <div style={{ paddingTop: 26, textAlign: 'right' }}>
                      <div
                        style={{
                          fontSize: 11,
                          letterSpacing: '0.06em',
                          color: 'var(--color-muted)',
                          textTransform: 'uppercase',
                          marginBottom: 4,
                        }}
                      >
                        Total
                      </div>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>
                        {lineTotal}
                      </div>
                      {items.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveItem(index)}
                          style={{
                            marginTop: 8,
                            background: 'none',
                            border: 'none',
                            color: 'var(--color-overdue)',
                            cursor: 'pointer',
                            fontSize: 11,
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                          }}
                        >
                          ✕ Remove
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Section 3: Notes & Authoritative Calculation Summary */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: 24,
            marginBottom: 32,
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
                marginBottom: 16,
                borderBottom: 'var(--border-hairline)',
                paddingBottom: 8,
              }}
            >
              3. Notes & Payment Terms
            </div>
            <TextArea
              label="CLIENT NOTES / INSTRUCTIONS"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={5}
              placeholder="e.g. Payment due via PayPal Sandbox within 14 business days. Thank you for your partnership."
              helperText="Printed on the invoice document and transmitted to PayPal Sandbox."
            />
          </div>

          {/* Authoritative Live Preview Card */}
          <div
            style={{
              backgroundColor: 'var(--color-ink)',
              color: '#FAF7F2',
              padding: 24,
              border: 'var(--border-hairline)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 11,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  color: 'var(--color-sand)',
                  marginBottom: 16,
                  borderBottom: '1px solid rgba(217, 207, 186, 0.2)',
                  paddingBottom: 8,
                }}
              >
                Financial Breakdown // Preview
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10, fontSize: 14 }}>
                <span style={{ color: 'var(--color-sand)' }}>Subtotal:</span>
                <span style={{ fontFamily: 'monospace' }}>
                  {previewSubtotal.toFixed(2)} {currency}
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16, fontSize: 14 }}>
                <span style={{ color: 'var(--color-sand)' }}>Tax Total:</span>
                <span style={{ fontFamily: 'monospace' }}>
                  {previewTax.toFixed(2)} {currency}
                </span>
              </div>

              <div
                style={{
                  borderTop: '1px solid rgba(217, 207, 186, 0.3)',
                  paddingTop: 16,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  marginBottom: 16,
                }}
              >
                <span style={{ fontSize: 13, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-sand)' }}>
                  Total Payable:
                </span>
                <span style={{ fontFamily: 'var(--font-heading)', fontSize: 28, color: '#FAF7F2' }}>
                  {previewTotal.toFixed(2)}{' '}
                  <span style={{ fontSize: 16, fontFamily: 'var(--font-body)', color: 'var(--color-sand)' }}>
                    {currency}
                  </span>
                </span>
              </div>
            </div>

            <div
              style={{
                fontSize: 11,
                lineHeight: 1.5,
                color: 'rgba(217, 207, 186, 0.75)',
                backgroundColor: 'rgba(217, 207, 186, 0.08)',
                padding: 12,
                border: '1px solid rgba(217, 207, 186, 0.15)',
              }}
            >
              <strong>Authoritative Rule:</strong> Server-side Decimal validation is binding. Amounts are validated
              with exact 0.01 precision (ISO 4217). Float math is strictly disallowed.
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'flex-end',
            gap: 16,
            borderTop: 'var(--border-hairline)',
            paddingTop: 24,
          }}
        >
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate('/invoices')}
            disabled={isSubmitting}
          >
            Cancel
          </Button>

          <Button
            type="submit"
            variant="secondary"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Saving Draft...' : 'Save Draft'}
          </Button>

          <Button
            type="button"
            variant="primary"
            disabled={isSubmitting}
            onClick={(e) => void handleSubmit(e, true)}
          >
            {isSubmitting ? 'Processing...' : 'Save & Submit for Approval'}
          </Button>
        </div>
      </form>
    </div>
  );
};

import { useEffect, useState, type FC } from 'react';
import { Button, DataTable, EmptyState, LoadingState, PageHeader, TextInput } from '../../components';
import { apiClient } from '../../lib/api-client';

interface CustomerItem {
  id: string;
  name: string;
  email: string;
  company?: string | null;
  created_at: string;
  is_active: boolean;
}

interface CustomerListResponse {
  items: CustomerItem[];
  total: number;
}

export const CustomersView: FC = () => {
  const [customers, setCustomers] = useState<CustomerItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');

  const loadCustomers = async () => {
    try {
      setLoading(true);
      let query = '/api/customers?page=1&page_size=50';
      if (search) query += `&q=${encodeURIComponent(search)}`;
      const res = await apiClient<CustomerListResponse>(query);
      setCustomers(res.items || []);
    } catch (err) {
      console.warn('Failed to fetch customers:', err);
      setCustomers([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCustomers();
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="CLIENT RELATIONSHIPS"
        title="Customers"
        subtitle="Manage client identities and verified billing contact information scoped to your account."
        actions={
          <Button variant="primary" size="sm" onClick={() => alert('New customer modal')}>
            + ADD CUSTOMER
          </Button>
        }
      />

      <div style={{ display: 'flex', gap: '16px', marginBottom: '24px' }}>
        <div style={{ flex: 1 }}>
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
            <Button variant="primary" size="sm" onClick={() => alert('Add customer form')}>
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
              key: 'created_at',
              header: 'Added',
              width: '140px',
              render: (c) => c.created_at.slice(0, 10),
            },
          ]}
          data={customers}
          keyExtractor={(c) => c.id}
          onRowClick={(c) => alert(`Selected customer ${c.name}`)}
        />
      )}
    </div>
  );
};

/**
 * Bryntum Calendar Integration — Invoice Due-Date & Follow-up Timeline
 *
 * Implements high-performance visual calendar scheduling for Accounts Receivable:
 * - Invoice due-date mapping across Month, Week, and Agenda views
 * - Overdue, Pending, and Paid event status coding matching Quiet-Luxury palette
 * - Scheduled customer follow-up reminder visualization
 * - Event click routing to invoice details
 * - Real-time filtering by status
 */

import { useEffect, useMemo, useRef, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { BryntumCalendar } from '@bryntum/calendar-react';
import '@bryntum/calendar-trial/calendar.css';
import '@bryntum/calendar-trial/stockholm-light.css';

import { PageHeader } from '../../components/PageHeader';
import { Button } from '../../components/Button';
import { apiClient } from '../../lib/api-client';

interface InvoiceItem {
  internal_id: string;
  invoice_number: string;
  customer_name?: string | null;
  total: string;
  currency: string;
  issue_date: string;
  due_date: string;
  status: string;
}

interface ReminderItem {
  id: string;
  invoice_id: string;
  invoice_number: string;
  customer_name: string;
  channel: string;
  stage: string;
  status: string;
  created_at: string;
  sent_at?: string | null;
}

interface CalendarEvent {
  id: string;
  name: string;
  startDate: string;
  endDate: string;
  allDay: boolean;
  eventColor?: string;
  invoiceId?: string;
  type: 'invoice_due' | 'reminder_followup';
  status: string;
  amount?: string;
  customer?: string;
}

export const BryntumInvoiceCalendar: FC = () => {
  const navigate = useNavigate();
  const calendarRef = useRef<any>(null);

  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [reminders, setReminders] = useState<ReminderItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OVERDUE' | 'SENT' | 'PAID' | 'REMINDERS'>('ALL');

  useEffect(() => {
    let isMounted = true;

    const fetchData = async () => {
      try {
        setLoading(true);
        const [invoicesRes, remindersRes] = await Promise.allSettled([
          apiClient<{ items: InvoiceItem[] }>('/api/invoices?page=1&page_size=100'),
          apiClient<{ items: ReminderItem[] }>('/api/reminders?limit=50'),
        ]);

        if (isMounted) {
          if (invoicesRes.status === 'fulfilled') {
            setInvoices(invoicesRes.value.items || []);
          }
          if (remindersRes.status === 'fulfilled') {
            setReminders(remindersRes.value.items || []);
          }
        }
      } catch (err) {
        console.warn('Failed to fetch calendar data:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    void fetchData();
    return () => {
      isMounted = false;
    };
  }, []);

  // Transform invoices and reminders into Bryntum Calendar events
  const allEvents = useMemo<CalendarEvent[]>(() => {
    const events: CalendarEvent[] = [];

    // Map Invoices by Due Date
    for (const inv of invoices) {
      if (!inv.due_date) continue;
      const isPaid = inv.status === 'PAID';
      const isOverdue = inv.status === 'OVERDUE';
      const color = isPaid ? '#7A7F5A' : isOverdue ? '#8C4A3F' : '#B5835A';

      events.push({
        id: `inv-${inv.internal_id}`,
        name: `${inv.invoice_number} · ${inv.customer_name || 'Client'} (${inv.currency} ${parseFloat(inv.total || '0').toFixed(2)})`,
        startDate: inv.due_date,
        endDate: inv.due_date,
        allDay: true,
        eventColor: color,
        invoiceId: inv.internal_id,
        type: 'invoice_due',
        status: inv.status,
        amount: `${inv.currency} ${inv.total}`,
        customer: inv.customer_name || 'Client',
      });
    }

    // Map Reminders by Sent / Created Follow-up Date
    for (const rem of reminders) {
      const targetDate = rem.sent_at || rem.created_at;
      if (!targetDate) continue;
      const dateStr = targetDate.split('T')[0] || targetDate;
      events.push({
        id: `rem-${rem.id}`,
        name: `Follow-up: ${rem.customer_name} (${rem.stage} · ${rem.channel})`,
        startDate: dateStr,
        endDate: dateStr,
        allDay: true,
        eventColor: '#4A4036',
        invoiceId: rem.invoice_id,
        type: 'reminder_followup',
        status: rem.status,
        customer: rem.customer_name,
      });
    }

    return events;
  }, [invoices, reminders]);

  // Filter events according to active status selector
  const filteredEvents = useMemo(() => {
    if (statusFilter === 'ALL') return allEvents;
    if (statusFilter === 'REMINDERS') return allEvents.filter((e) => e.type === 'reminder_followup');
    return allEvents.filter((e) => e.type === 'invoice_due' && e.status === statusFilter);
  }, [allEvents, statusFilter]);

  const handleEventClick = (eventRecord: any) => {
    const raw = eventRecord?.eventRecord || eventRecord;
    const invId = raw?.invoiceId || raw?.originalData?.invoiceId;
    if (invId) {
      navigate(`/invoices/${invId}`);
    }
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <PageHeader
        eyebrow="SCHEDULE & TIMELINE // BRYNTUM CALENDAR"
        title="Receivables Due Date Calendar"
        subtitle="Visualize receivables aging, statutory due dates, and scheduled customer follow-up cadences in real time."
        actions={
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <Button variant="secondary" onClick={() => navigate('/invoices')}>
              INVOICE DIRECTORY →
            </Button>
            <Button variant="primary" onClick={() => navigate('/invoices/new')}>
              + NEW INVOICE
            </Button>
          </div>
        }
      />

      {/* Filter and Legend Bar */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '12px',
          padding: '14px 18px',
          backgroundColor: 'var(--color-cream)',
          border: 'var(--border-hairline)',
          borderRadius: 'var(--radius-sm)',
        }}
      >
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '11px',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              color: 'var(--color-muted)',
              marginRight: '8px',
            }}
          >
            FILTER VIEW:
          </span>
          {(['ALL', 'OVERDUE', 'SENT', 'PAID', 'REMINDERS'] as const).map((filter) => {
            const isActive = statusFilter === filter;
            return (
              <button
                key={filter}
                type="button"
                onClick={() => setStatusFilter(filter)}
                style={{
                  padding: '6px 12px',
                  fontFamily: 'var(--font-sans)',
                  fontSize: '11px',
                  fontWeight: 600,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  border: isActive ? '1px solid var(--color-ink)' : 'var(--border-hairline)',
                  backgroundColor: isActive ? 'var(--color-ink)' : 'transparent',
                  color: isActive ? 'var(--color-bg)' : 'var(--color-ink)',
                  cursor: 'pointer',
                  borderRadius: '2px',
                }}
              >
                {filter === 'ALL'
                  ? `ALL (${allEvents.length})`
                  : filter === 'REMINDERS'
                  ? `FOLLOW-UPS (${allEvents.filter((e) => e.type === 'reminder_followup').length})`
                  : `${filter} (${allEvents.filter((e) => e.type === 'invoice_due' && e.status === filter).length})`}
              </button>
            );
          })}
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', fontSize: '12px', flexWrap: 'wrap' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', backgroundColor: '#8C4A3F', display: 'inline-block' }} />
            Overdue
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', backgroundColor: '#B5835A', display: 'inline-block' }} />
            Pending / Sent
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', backgroundColor: '#7A7F5A', display: 'inline-block' }} />
            Settled / Paid
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', backgroundColor: '#4A4036', display: 'inline-block' }} />
            Follow-up Reminder
          </span>
        </div>
      </div>

      {/* Main Bryntum Calendar Container */}
      <div
        style={{
          border: 'var(--border-hairline)',
          borderRadius: 'var(--radius-sm)',
          backgroundColor: '#FFFFFF',
          minHeight: '500px',
          height: 'clamp(500px, 72vh, 750px)',
          boxShadow: 'var(--shadow-subtle)',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {loading ? (
          <div
            style={{
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'var(--color-cream)',
              color: 'var(--color-muted)',
              fontFamily: 'var(--font-sans)',
              fontSize: '13px',
              letterSpacing: '0.05em',
            }}
          >
            LOADING RECEIVABLES CALENDAR DATA...
          </div>
        ) : (
          <BryntumCalendar
            ref={calendarRef}
            events={filteredEvents}
            modes={{
              year: false,
              month: true,
              week: true,
              day: false,
              agenda: true,
            }}
            mode="month"
            date={new Date()}
            readOnly={false}
            listeners={{
              eventClick: (e: any) => handleEventClick(e),
            }}
          />
        )}
      </div>

      {/* Context Summary Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))',
          gap: '16px',
        }}
      >
        <div
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-cream)',
            border: 'var(--border-hairline)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-muted)' }}>
            BRYNTUM SPONSOR INTEGRATION
          </div>
          <div style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', fontWeight: 600, marginTop: '4px' }}>
            High-Performance Scheduling
          </div>
          <p style={{ fontSize: '12px', color: 'var(--color-muted)', marginTop: '6px', lineHeight: 1.5 }}>
            Powered by <strong>@bryntum/calendar-react</strong> with native Month, Week, and Agenda rendering, dynamic status color coding, and direct invoice routing.
          </p>
        </div>

        <div
          style={{
            padding: '16px',
            backgroundColor: 'var(--color-cream)',
            border: 'var(--border-hairline)',
            borderRadius: 'var(--radius-sm)',
          }}
        >
          <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--color-muted)' }}>
            AUTOMATED REMINDER TIMELINES
          </div>
          <div style={{ fontFamily: 'var(--font-serif)', fontSize: '18px', fontWeight: 600, marginTop: '4px' }}>
            Human-in-the-Loop Follow-ups
          </div>
          <p style={{ fontSize: '12px', color: 'var(--color-muted)', marginTop: '6px', lineHeight: 1.5 }}>
            Scheduled follow-ups synchronize with the Approval Center. No reminders are dispatched without explicit merchant authorization.
          </p>
        </div>
      </div>
    </div>
  );
};

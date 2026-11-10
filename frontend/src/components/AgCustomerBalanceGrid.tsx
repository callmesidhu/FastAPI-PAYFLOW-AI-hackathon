/**
 * AG Grid Customer Receivables Balance Explorer (Prompt 25).
 *
 * Implements high-performance AG Grid for Customer Receivables Analytics:
 * - Multi-column sorting (Customer, Outstanding, Overdue, Invoices)
 * - Number and text filters
 * - Currency-aware formatting
 * - Quick filter across all accounts
 * - CSV export
 * - Quiet-luxury theme tokens
 */

import React, { useMemo, useRef, useState, type FC } from 'react';
import { type ColDef, type GridApi, type GridReadyEvent } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import { Button } from './Button';

export interface CustomerBalanceRow {
  customer_id: string;
  customer_name: string;
  customer_email: string;
  currency: string;
  outstanding_amount: string;
  overdue_amount: string;
  open_invoices_count: number;
  invoice_numbers: string[];
}

interface AgCustomerBalanceGridProps {
  rowData: CustomerBalanceRow[];
}

export const AgCustomerBalanceGrid: FC<AgCustomerBalanceGridProps> = ({ rowData }) => {
  const gridApiRef = useRef<GridApi<CustomerBalanceRow> | null>(null);
  const [quickFilterText, setQuickFilterText] = useState<string>('');

  const onGridReady = (params: GridReadyEvent<CustomerBalanceRow>) => {
    gridApiRef.current = params.api;
    params.api.sizeColumnsToFit();
  };

  const onExportCsv = () => {
    if (gridApiRef.current) {
      gridApiRef.current.exportDataAsCsv({
        fileName: `payflow-customer-balances-${new Date().toISOString().split('T')[0]}.csv`,
      });
    }
  };

  const columnDefs = useMemo<ColDef<CustomerBalanceRow>[]>(() => {
    return [
      {
        headerName: 'CUSTOMER / CLIENT',
        field: 'customer_name',
        filter: 'agTextColumnFilter',
        sortable: true,
        flex: 1,
        minWidth: 180,
        cellRenderer: (params: any) => {
          const row = params.data as CustomerBalanceRow;
          if (!row) return null;
          return (
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', height: '100%' }}>
              <div style={{ fontWeight: 600, color: 'var(--color-ink)' }}>{row.customer_name}</div>
              <div style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'monospace' }}>
                {row.customer_email}
              </div>
            </div>
          );
        },
      },
      {
        headerName: 'CURRENCY',
        field: 'currency',
        filter: 'agTextColumnFilter',
        sortable: true,
        width: 110,
        cellStyle: { fontFamily: 'monospace', fontWeight: 600 } as any,
      },
      {
        headerName: 'OUTSTANDING',
        field: 'outstanding_amount',
        filter: 'agNumberColumnFilter',
        sortable: true,
        width: 140,
        type: 'rightAligned',
        valueGetter: (params) => parseFloat(params.data?.outstanding_amount || '0'),
        valueFormatter: (params) => {
          if (params.value === undefined || params.value === null) return '';
          return `$${Number(params.value).toFixed(2)}`;
        },
        cellStyle: { fontFamily: 'monospace', fontWeight: 600 } as any,
      },
      {
        headerName: 'OVERDUE AMOUNT',
        field: 'overdue_amount',
        filter: 'agNumberColumnFilter',
        sortable: true,
        width: 150,
        type: 'rightAligned',
        valueGetter: (params) => parseFloat(params.data?.overdue_amount || '0'),
        cellRenderer: (params: any) => {
          const val = parseFloat(params.data?.overdue_amount || '0');
          if (val <= 0) {
            return <span style={{ fontFamily: 'monospace', color: 'var(--color-muted)' }}>$0.00</span>;
          }
          return (
            <span style={{ fontFamily: 'monospace', color: 'var(--color-overdue)', fontWeight: 600 }}>
              ${val.toFixed(2)} ⚠️
            </span>
          );
        },
      },
      {
        headerName: 'OPEN INVOICES',
        field: 'open_invoices_count',
        filter: 'agNumberColumnFilter',
        sortable: true,
        width: 130,
        type: 'rightAligned',
        cellStyle: { fontFamily: 'monospace' } as any,
      },
      {
        headerName: 'INVOICE NUMBERS',
        field: 'invoice_numbers',
        sortable: false,
        filter: false,
        flex: 1,
        minWidth: 160,
        cellRenderer: (params: any) => {
          const row = params.data as CustomerBalanceRow;
          if (!row || !row.invoice_numbers || row.invoice_numbers.length === 0) {
            return <span style={{ fontSize: 11, color: 'var(--color-muted)' }}>—</span>;
          }
          return (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center', height: '100%' }}>
              {row.invoice_numbers.map((num) => (
                <span
                  key={num}
                  style={{
                    fontSize: 10,
                    fontFamily: 'monospace',
                    padding: '1px 5px',
                    backgroundColor: 'var(--color-cream)',
                    border: 'var(--border-hairline)',
                    color: 'var(--color-ink)',
                  }}
                >
                  {num}
                </span>
              ))}
            </div>
          );
        },
      },
    ];
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* Search and Export Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
          padding: '8px 12px',
          backgroundColor: 'var(--color-sand)',
          border: 'var(--border-hairline)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--color-ink)',
            }}
          >
            AG Grid Client Explorer
          </span>
          <input
            type="text"
            placeholder="Search accounts..."
            value={quickFilterText}
            onChange={(e) => setQuickFilterText(e.target.value)}
            style={{
              padding: '4px 8px',
              fontSize: 11,
              backgroundColor: 'var(--color-cream)',
              border: 'var(--border-hairline)',
              color: 'var(--color-ink)',
              fontFamily: 'var(--font-sans)',
            }}
          />
        </div>
        <Button variant="outline" size="sm" onClick={onExportCsv} style={{ padding: '2px 8px', fontSize: 10 }}>
          Export CSV
        </Button>
      </div>

      {/* Styled Grid */}
      <div
        className="ag-theme-quartz"
        style={
          {
            height: 320,
            width: '100%',
            border: 'var(--border-hairline)',
            '--ag-background-color': '#FAF7F2',
            '--ag-foreground-color': '#0B0B0B',
            '--ag-header-background-color': '#EDE6D6',
            '--ag-header-foreground-color': '#0B0B0B',
            '--ag-border-color': '#3A342C',
            '--ag-row-border-color': 'rgba(58, 52, 44, 0.25)',
            '--ag-odd-row-background-color': '#EDE6D6',
            '--ag-even-row-background-color': '#FAF7F2',
            '--ag-header-cell-hover-background-color': '#D9CFBA',
            '--ag-row-hover-color': '#D9CFBA',
            '--ag-selected-row-background-color': '#D9CFBA',
            '--ag-font-family': 'var(--font-sans)',
            '--ag-font-size': '12px',
            '--ag-card-background': '#EDE6D6',
            '--ag-popup-border-color': '#3A342C',
            '--ag-control-panel-background-color': '#EDE6D6',
            '--ag-input-focus-border-color': '#0B0B0B',
            '--ag-checkbox-checked-color': '#0B0B0B',
          } as React.CSSProperties
        }
      >
        <AgGridReact<CustomerBalanceRow>
          rowData={rowData}
          columnDefs={columnDefs}
          onGridReady={onGridReady}
          quickFilterText={quickFilterText}
          pagination={true}
          paginationPageSize={5}
          rowHeight={40}
          headerHeight={36}
          animateRows={false}
        />
      </div>
    </div>
  );
};


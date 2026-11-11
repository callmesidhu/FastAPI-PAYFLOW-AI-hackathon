/**
 * Meaningful AG Grid Sponsor Integration (Prompt 25).
 *
 * Implements a high-performance interactive grid for Accounts Receivable invoices:
 * - Multi-column sorting (Invoice #, Client, Amount, Due Date, Status)
 * - Column-specific filtering (Text, Number, Date, Status)
 * - Real-time quick filter across all row fields
 * - Currency-aware formatting and right alignment
 * - StatusLabel rendering with quiet-luxury styling tokens
 * - Built-in pagination with configurable page sizes (10, 25, 50)
 * - CSV export capability via AG Grid API
 * - Quiet-luxury theme overrides: Cream (#EDE6D6), Sand (#D9CFBA), Ink (#0B0B0B), Hairline (#3A342C)
 */

import React, { useMemo, useRef, useState, type FC } from 'react';
import { useNavigate } from 'react-router-dom';
import { AllCommunityModule, ModuleRegistry, type ColDef, type GridApi, type GridReadyEvent } from 'ag-grid-community';
import { AgGridReact } from 'ag-grid-react';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-quartz.css';

import { StatusLabel } from './StatusLabel';
import { Button } from './Button';

// Register AG Grid Community modules
ModuleRegistry.registerModules([AllCommunityModule]);

export interface AgInvoiceRow {
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

interface AgInvoiceGridProps {
  rowData: AgInvoiceRow[];
  onSubmitForApproval?: (invoice: AgInvoiceRow) => void;
  onDeleteDraft?: (invoice: AgInvoiceRow) => void;
}

export const AgInvoiceGrid: FC<AgInvoiceGridProps> = ({
  rowData,
  onSubmitForApproval,
  onDeleteDraft,
}) => {
  const navigate = useNavigate();
  const gridApiRef = useRef<GridApi<AgInvoiceRow> | null>(null);
  const [quickFilterText, setQuickFilterText] = useState<string>('');

  const onGridReady = (params: GridReadyEvent<AgInvoiceRow>) => {
    gridApiRef.current = params.api;
    params.api.sizeColumnsToFit();
  };

  const onExportCsv = () => {
    if (gridApiRef.current) {
      gridApiRef.current.exportDataAsCsv({
        fileName: `payflow-invoices-${new Date().toISOString().split('T')[0]}.csv`,
      });
    }
  };

  const columnDefs = useMemo<ColDef<AgInvoiceRow>[]>(() => {
    return [
      {
        headerName: 'INVOICE #',
        field: 'invoice_number',
        filter: 'agTextColumnFilter',
        sortable: true,
        width: 160,
        pinned: 'left',
        cellRenderer: (params: any) => {
          const row = params.data as AgInvoiceRow;
          if (!row) return null;
          return (
            <button
              type="button"
              onClick={() => navigate(`/invoices/${row.internal_id}`)}
              style={{
                background: 'none',
                border: 'none',
                padding: 0,
                color: 'var(--color-ink)',
                fontFamily: 'monospace',
                fontWeight: 600,
                fontSize: 13,
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              {row.invoice_number}
            </button>
          );
        },
      },
      {
        headerName: 'CLIENT / CUSTOMER',
        field: 'customer_name',
        filter: 'agTextColumnFilter',
        sortable: true,
        flex: 1,
        minWidth: 180,
        valueGetter: (params: any) => params.data?.customer_name || 'Customer',
        cellRenderer: (params: any) => {
          const row = params.data as AgInvoiceRow;
          if (!row) return null;
          return (
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', height: '100%' }}>
              <div style={{ fontWeight: 500, color: 'var(--color-ink)' }}>
                {row.customer_name || 'Customer'}
              </div>
              <div style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'monospace' }}>
                {row.customer_id}
              </div>
            </div>
          );
        },
      },
      {
        headerName: 'AMOUNT',
        field: 'total',
        filter: 'agNumberColumnFilter',
        sortable: true,
        width: 140,
        type: 'rightAligned',
        valueGetter: (params: any) => parseFloat(params.data?.total || '0'),
        valueFormatter: (params: any) => {
          if (params.value === undefined || params.value === null) return '';
          return `$${Number(params.value).toFixed(2)} ${params.data?.currency || 'USD'}`;
        },
        cellStyle: { fontFamily: 'monospace', fontWeight: 600 } as any,
      },
      {
        headerName: 'ISSUE DATE',
        field: 'issue_date',
        filter: 'agDateColumnFilter',
        sortable: true,
        width: 130,
        cellStyle: { fontFamily: 'monospace', color: 'var(--color-muted)' } as any,
      },
      {
        headerName: 'DUE DATE',
        field: 'due_date',
        filter: 'agDateColumnFilter',
        sortable: true,
        width: 130,
        cellRenderer: (params: any) => {
          const row = params.data as AgInvoiceRow;
          if (!row) return null;
          const isOverdue = row.status !== 'paid' && new Date(row.due_date) < new Date();
          return (
            <span
              style={{
                fontFamily: 'monospace',
                color: isOverdue ? 'var(--color-overdue)' : 'var(--color-ink)',
                fontWeight: isOverdue ? 600 : 400,
              }}
            >
              {row.due_date} {isOverdue && '⚠️'}
            </span>
          );
        },
      },
      {
        headerName: 'STATUS',
        field: 'status',
        filter: 'agTextColumnFilter',
        sortable: true,
        width: 160,
        cellRenderer: (params: any) => {
          const row = params.data as AgInvoiceRow;
          if (!row) return null;
          return (
            <div style={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              <StatusLabel status={row.status} />
            </div>
          );
        },
      },
      {
        headerName: 'ACTIONS',
        width: 180,
        sortable: false,
        filter: false,
        pinned: 'right',
        cellRenderer: (params: any) => {
          const row = params.data as AgInvoiceRow;
          if (!row) return null;
          return (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center', height: '100%' }}>
              <Button
                variant="outline"
                size="sm"
                onClick={() => navigate(`/invoices/${row.internal_id}`)}
                style={{ padding: '2px 8px', fontSize: 10 }}
              >
                VIEW
              </Button>
              {row.status === 'draft' && onSubmitForApproval && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => onSubmitForApproval(row)}
                  style={{ padding: '2px 8px', fontSize: 10 }}
                >
                  SUBMIT
                </Button>
              )}
              {row.status === 'draft' && onDeleteDraft && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onDeleteDraft(row)}
                  style={{ padding: '2px 8px', fontSize: 10, color: 'var(--color-overdue)' }}
                >
                  DELETE
                </Button>
              )}
            </div>
          );
        },
      },
    ];
  }, [navigate, onSubmitForApproval, onDeleteDraft]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* AG Grid Controls Bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
          padding: '12px 16px',
          backgroundColor: 'var(--color-sand)',
          border: 'var(--border-hairline)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--color-ink)',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span
              style={{
                display: 'inline-block',
                width: 6,
                height: 6,
                backgroundColor: 'var(--color-ink)',
              }}
            />
            AG Grid Pro Explorer
          </span>
          <div style={{ flex: '1 1 180px', maxWidth: 260, minWidth: 140 }}>
            <input
              type="text"
              placeholder="Quick search all columns..."
              value={quickFilterText}
              onChange={(e) => setQuickFilterText(e.target.value)}
              style={{
                width: '100%',
                padding: '6px 10px',
                fontSize: 12,
                backgroundColor: 'var(--color-cream)',
                border: 'var(--border-hairline)',
                color: 'var(--color-ink)',
                fontFamily: 'var(--font-sans)',
                boxSizing: 'border-box',
              }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setQuickFilterText('');
              if (gridApiRef.current) {
                gridApiRef.current.setFilterModel(null);
                gridApiRef.current.applyColumnState({ defaultState: { sort: null } });
              }
            }}
          >
            Reset Filters
          </Button>
          <Button variant="secondary" size="sm" onClick={onExportCsv}>
            Export CSV
          </Button>
        </div>
      </div>

      {/* Styled AG Grid Container with Quiet Luxury Design Tokens */}
      <div
        className="ag-theme-quartz"
        style={
          {
            height: 480,
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
        <AgGridReact<AgInvoiceRow>
          rowData={rowData}
          columnDefs={columnDefs}
          onGridReady={onGridReady}
          quickFilterText={quickFilterText}
          pagination={true}
          paginationPageSize={10}
          paginationPageSizeSelector={[10, 25, 50]}
          rowHeight={44}
          headerHeight={40}
          animateRows={false}
          suppressCellFocus={false}
        />
      </div>
    </div>
  );
};

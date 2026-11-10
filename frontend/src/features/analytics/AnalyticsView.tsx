import type { FC } from 'react';
import { EmptyState, PageHeader } from '../../components';

export const AnalyticsView: FC = () => {
  return (
    <div>
      <PageHeader
        eyebrow="FINANCIAL INTELLIGENCE"
        title="Receivables Analytics"
        subtitle="Aging buckets (0–7, 8–30, 31–60, 60+ days), collections velocity, and currency balance breakdowns."
      />

      <EmptyState
        title="Insufficient Historical Data"
        description="Analytics require finalized invoice history to generate meaningful aging buckets and collections velocity trends. As payments and invoices accumulate, currency-isolated charts will populate here."
      />
    </div>
  );
};

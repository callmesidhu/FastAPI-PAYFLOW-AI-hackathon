// ==============================================================================
// PAYFLOW AI — MongoDB Shell Seeder Script (Compass / mongosh)
// Target User: S Sidharth (XYPHX)
// User ID: ec3f64d0-ceeb-4fa4-8a5d-fd3fa8dcd663
// Email: callmesidhu.x@outlook.com
// ==============================================================================

const TARGET_USER_ID = "ec3f64d0-ceeb-4fa4-8a5d-fd3fa8dcd663";
const now = new Date();

print("Cleaning existing demo records for user: " + TARGET_USER_ID);
db.customers.deleteMany({ user_id: TARGET_USER_ID });
db.invoices.deleteMany({ user_id: TARGET_USER_ID });
db.approvals.deleteMany({ user_id: TARGET_USER_ID });
db.reminders.deleteMany({ user_id: TARGET_USER_ID });
db.transactions.deleteMany({ user_id: TARGET_USER_ID });
db.audit_logs.deleteMany({ user_id: TARGET_USER_ID });

// 1. Customers
print("Inserting Customers...");
db.customers.insertMany([
  {
    id: "c1111111-2222-3333-4444-555555555501",
    user_id: TARGET_USER_ID,
    name: "Elena Rostova",
    email: "elena@apexdigital.io",
    company: "Apex Digital Studio",
    billing_address: {
      address_line_1: "450 Mission Street, Suite 800",
      city: "San Francisco",
      state: "CA",
      postal_code: "94105",
      country_code: "US"
    },
    notes: "Key tier-1 client for brand strategy and UI design system architecture.",
    created_at: new Date(Date.now() - 90 * 86400000),
    updated_at: new Date(Date.now() - 90 * 86400000),
    is_active: true
  },
  {
    id: "c1111111-2222-3333-4444-555555555502",
    user_id: TARGET_USER_ID,
    name: "Marcus Vance",
    email: "m.vance@hyperionlogistics.com",
    company: "Hyperion Logistics Group",
    billing_address: {
      address_line_1: "1200 S Michigan Ave",
      city: "Chicago",
      state: "IL",
      postal_code: "60605",
      country_code: "US"
    },
    notes: "Global supply chain tracking and EDI 214 telemetry integration.",
    created_at: new Date(Date.now() - 75 * 86400000),
    updated_at: new Date(Date.now() - 75 * 86400000),
    is_active: true
  },
  {
    id: "c1111111-2222-3333-4444-555555555503",
    user_id: TARGET_USER_ID,
    name: "Claire Beauchamp",
    email: "claire@vanguardadvisory.com",
    company: "Vanguard Advisory Partners",
    billing_address: {
      address_line_1: "375 Park Avenue, 24th Floor",
      city: "New York",
      state: "NY",
      postal_code: "10152",
      country_code: "US"
    },
    notes: "Executive portfolio cashflow intelligence and monthly advisory retainer.",
    created_at: new Date(Date.now() - 60 * 86400000),
    updated_at: new Date(Date.now() - 60 * 86400000),
    is_active: true
  },
  {
    id: "c1111111-2222-3333-4444-555555555504",
    user_id: TARGET_USER_ID,
    name: "David Chen",
    email: "dchen@starlightmedia.com",
    company: "Starlight Media Works",
    billing_address: {
      address_line_1: "6801 Hollywood Blvd",
      city: "Los Angeles",
      state: "CA",
      postal_code: "90028",
      country_code: "US"
    },
    notes: "High-throughput cloud video rendering pipeline and creative automation.",
    created_at: new Date(Date.now() - 45 * 86400000),
    updated_at: new Date(Date.now() - 45 * 86400000),
    is_active: true
  },
  {
    id: "c1111111-2222-3333-4444-555555555505",
    user_id: TARGET_USER_ID,
    name: "Dr. Aris Thorne",
    email: "procurement@quantumlabs.ai",
    company: "Quantum AI Labs",
    billing_address: {
      address_line_1: "500 W 2nd St, Suite 1900",
      city: "Austin",
      state: "TX",
      postal_code: "78701",
      country_code: "US"
    },
    notes: "Generative agent tool-calling architecture and latency optimization contract.",
    created_at: new Date(Date.now() - 30 * 86400000),
    updated_at: new Date(Date.now() - 30 * 86400000),
    is_active: true
  },
  {
    id: "c1111111-2222-3333-4444-555555555506",
    user_id: TARGET_USER_ID,
    name: "Freja Lindqvist",
    email: "freja@nordicenergy.se",
    company: "Nordic Clean Energy",
    billing_address: {
      address_line_1: "Hamngatan 15",
      city: "Stockholm",
      state: "Stockholm",
      postal_code: "111 47",
      country_code: "SE"
    },
    notes: "Renewable energy smart grid distribution dashboard.",
    created_at: new Date(Date.now() - 20 * 86400000),
    updated_at: new Date(Date.now() - 20 * 86400000),
    is_active: true
  }
]);

// 2. Invoices
print("Inserting Invoices...");
db.invoices.insertMany([
  {
    internal_id: "inv-001-sep-apex-paid",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555501",
    invoice_number: "INV-2026-0001",
    items: [
      {
        name: "Quiet-Luxury Design System & Token Architecture",
        description: "Foundational typography, spacing variables, and high-contrast palette contract",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("2400.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("2400.00")
      },
      {
        name: "Frontend Component Prototype Sprints",
        description: "5 interactive wireframes and design review sessions",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("800.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("800.00")
      }
    ],
    subtotal: NumberDecimal("3200.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("3200.00"),
    currency: "USD",
    issue_date: "2026-09-01",
    due_date: "2026-09-15",
    status: "paid",
    paypal_invoice_id: "INV2-APEX-9011-8842",
    paypal_invoice_url: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-APEX-9011-8842",
    sent_at: new Date("2026-09-01T10:00:00Z"),
    paid_at: new Date("2026-09-14T15:22:00Z"),
    created_at: new Date("2026-09-01T09:30:00Z"),
    updated_at: new Date("2026-09-14T15:22:00Z"),
    notes: "Settled promptly via PayPal Sandbox checkout."
  },
  {
    internal_id: "inv-002-oct-hyperion-paid",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555502",
    invoice_number: "INV-2026-0002",
    items: [
      {
        name: "Real-Time Fleet Telemetry Microservices",
        description: "FastAPI async broker for GPS pings and container status aggregation",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("4800.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("4800.00")
      }
    ],
    subtotal: NumberDecimal("4800.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("4800.00"),
    currency: "USD",
    issue_date: "2026-10-01",
    due_date: "2026-10-15",
    status: "paid",
    paypal_invoice_id: "INV2-HYPR-1024-9913",
    paypal_invoice_url: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-HYPR-1024-9913",
    sent_at: new Date("2026-10-01T11:15:00Z"),
    paid_at: new Date("2026-10-12T11:45:00Z"),
    created_at: new Date("2026-10-01T10:00:00Z"),
    updated_at: new Date("2026-10-12T11:45:00Z"),
    notes: "Verified through automated PayPal webhook reconciliation."
  },
  {
    internal_id: "inv-003-nov-vanguard-paid",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555503",
    invoice_number: "INV-2026-0003",
    items: [
      {
        name: "Executive Cashflow Models & Predictive Receivables",
        description: "Monte Carlo aging simulator and liquidity projection dashboard",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("5500.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("5500.00")
      }
    ],
    subtotal: NumberDecimal("5500.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("5500.00"),
    currency: "USD",
    issue_date: "2026-10-20",
    due_date: "2026-11-03",
    status: "paid",
    paypal_invoice_id: "INV2-VANG-1102-4421",
    paypal_invoice_url: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-VANG-1102-4421",
    sent_at: new Date("2026-10-20T14:00:00Z"),
    paid_at: new Date("2026-11-02T16:10:00Z"),
    created_at: new Date("2026-10-20T13:00:00Z"),
    updated_at: new Date("2026-11-02T16:10:00Z"),
    notes: "Reconciled with PayPal RSASSA-PKCS1 webhook signature."
  },
  {
    internal_id: "inv-004-nov-starlight-sent",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555504",
    invoice_number: "INV-2026-0004",
    items: [
      {
        name: "Automated Cloud Transcoding Cluster",
        description: "Kubernetes worker autoscaling for 4K video transcoding",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("2750.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("2750.00")
      }
    ],
    subtotal: NumberDecimal("2750.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("2750.00"),
    currency: "USD",
    issue_date: "2026-11-05",
    due_date: "2026-11-19",
    status: "sent",
    paypal_invoice_id: "INV2-STAR-1105-3312",
    paypal_invoice_url: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-STAR-1105-3312",
    sent_at: new Date("2026-11-05T09:30:00Z"),
    created_at: new Date("2026-11-04T12:00:00Z"),
    updated_at: new Date("2026-11-05T09:30:00Z"),
    notes: "Delivered to customer inbox via official PayPal Invoicing v2 dispatch."
  },
  {
    internal_id: "inv-005-nov-quantum-sent",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555505",
    invoice_number: "INV-2026-0005",
    items: [
      {
        name: "Agentic Tool Calling & Injection Firewall Harness",
        description: "Multi-agent evaluation harness with 5-tool security boundary",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("3600.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("3600.00")
      }
    ],
    subtotal: NumberDecimal("3600.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("3600.00"),
    currency: "USD",
    issue_date: "2026-11-08",
    due_date: "2026-11-22",
    status: "sent",
    paypal_invoice_id: "INV2-QNTM-1108-7744",
    paypal_invoice_url: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-QNTM-1108-7744",
    sent_at: new Date("2026-11-08T14:15:00Z"),
    created_at: new Date("2026-11-07T10:00:00Z"),
    updated_at: new Date("2026-11-08T14:15:00Z"),
    notes: "Active outstanding receivable."
  },
  {
    internal_id: "inv-006-nov-apex-overdue",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555501",
    invoice_number: "INV-2026-0006",
    items: [
      {
        name: "Design Token Migration & Production Accessibility QA",
        description: "WCAG 2.1 AA audit and automated regression suite",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("1950.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("1950.00")
      }
    ],
    subtotal: NumberDecimal("1950.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("1950.00"),
    currency: "USD",
    issue_date: "2026-10-21",
    due_date: "2026-11-04",
    status: "overdue",
    paypal_invoice_id: "INV2-APEX-1021-5582",
    paypal_invoice_url: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-APEX-1021-5582",
    sent_at: new Date("2026-10-21T10:00:00Z"),
    created_at: new Date("2026-10-20T16:00:00Z"),
    updated_at: new Date("2026-11-04T00:00:00Z"),
    notes: "Stage 2 follow-up reminder prepared in Approval Center."
  },
  {
    internal_id: "inv-007-nov-hyperion-overdue",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555502",
    invoice_number: "INV-2026-0007",
    items: [
      {
        name: "EDI 214 Shipment Status Webhook Infrastructure",
        description: "High-throughput webhook dispatch with HMAC verification",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("4200.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("4200.00")
      }
    ],
    subtotal: NumberDecimal("4200.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("4200.00"),
    currency: "USD",
    issue_date: "2026-10-14",
    due_date: "2026-10-28",
    status: "overdue",
    paypal_invoice_id: "INV2-HYPR-1014-6631",
    paypal_invoice_url: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-HYPR-1014-6631",
    sent_at: new Date("2026-10-14T11:20:00Z"),
    created_at: new Date("2026-10-13T10:00:00Z"),
    updated_at: new Date("2026-10-28T00:00:00Z"),
    notes: "Awaiting finance department approval round."
  },
  {
    internal_id: "inv-008-nov-vanguard-pending",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555503",
    invoice_number: "INV-2026-0008",
    items: [
      {
        name: "Q4 Enterprise Accounts Receivable Architecture Retainer",
        description: "End-to-end integration architecture and PayPal Invoicing sandbox validation",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("6800.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("6800.00")
      }
    ],
    subtotal: NumberDecimal("6800.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("6800.00"),
    currency: "USD",
    issue_date: "2026-11-10",
    due_date: "2026-11-24",
    status: "pending_approval",
    created_at: new Date(Date.now() - 18 * 3600000),
    updated_at: new Date(Date.now() - 18 * 3600000),
    notes: "Submitted for human approval before PayPal Sandbox creation."
  },
  {
    internal_id: "inv-009-nov-nordic-draft",
    user_id: TARGET_USER_ID,
    customer_id: "c1111111-2222-3333-4444-555555555506",
    invoice_number: "INV-2026-0009",
    items: [
      {
        name: "Microgrid Energy Analytics Sprint 1",
        description: "Smart meter time-series data aggregation and billing schema definition",
        quantity: NumberDecimal("1.00"),
        unit_price: NumberDecimal("1400.00"),
        tax: NumberDecimal("0.00"),
        total: NumberDecimal("1400.00")
      }
    ],
    subtotal: NumberDecimal("1400.00"),
    tax: NumberDecimal("0.00"),
    total: NumberDecimal("1400.00"),
    currency: "USD",
    issue_date: "2026-11-11",
    due_date: "2026-11-25",
    status: "draft",
    created_at: new Date(Date.now() - 4 * 3600000),
    updated_at: new Date(Date.now() - 4 * 3600000),
    notes: "Draft prepared via natural language prompt in AI Assistant."
  }
]);

// 3. Approvals
print("Inserting Approvals...");
db.approvals.insertMany([
  {
    id: "appr-001-pending-inv-008",
    user_id: TARGET_USER_ID,
    action_type: "create_paypal_invoice",
    resource_type: "invoice",
    resource_id: "inv-008-nov-vanguard-pending",
    payload_snapshot: {
      invoice_id: "inv-008-nov-vanguard-pending",
      invoice_number: "INV-2026-0008",
      customer_id: "c1111111-2222-3333-4444-555555555503",
      amount: "6800.00",
      currency: "USD",
      due_date: "2026-11-24"
    },
    payload_hash: "a4c281df69e9a4f6bb8f01f30b9104fa282b0f4c34a179e8d3568858273611a2",
    status: "pending",
    created_at: new Date(Date.now() - 18 * 3600000)
  },
  {
    id: "appr-002-pending-rem-006",
    user_id: TARGET_USER_ID,
    action_type: "send_payment_reminder",
    resource_type: "reminder",
    resource_id: "rem-001-apex-overdue",
    payload_snapshot: {
      invoice_id: "inv-006-nov-apex-overdue",
      invoice_number: "INV-2026-0006",
      customer_name: "Elena Rostova",
      customer_email: "elena@apexdigital.io",
      stage: "overdue_1_3",
      channel: "zapier"
    },
    payload_hash: "7f92021c356e35561a86847bc05500e5e01b7ccaa1ec650125860d5b7fe72db8",
    status: "pending",
    created_at: new Date(Date.now() - 8 * 3600000)
  },
  {
    id: "appr-003-approved-inv-003",
    user_id: TARGET_USER_ID,
    action_type: "send_paypal_invoice",
    resource_type: "invoice",
    resource_id: "inv-003-nov-vanguard-paid",
    payload_snapshot: {
      invoice_id: "inv-003-nov-vanguard-paid",
      invoice_number: "INV-2026-0003",
      amount: "5500.00",
      currency: "USD"
    },
    payload_hash: "1d81fa73e6cf5e3056094b8e0b656cf5a939f4d7b29a67e85c2c9ee5c9a9d201",
    status: "approved",
    created_at: new Date("2026-10-20T13:30:00Z"),
    approved_at: new Date("2026-10-20T13:55:00Z"),
    execution_result_ref: "INV2-VANG-1102-4421"
  }
]);

// 4. Reminders
print("Inserting Reminders...");
db.reminders.insertMany([
  {
    id: "rem-001-apex-overdue",
    user_id: TARGET_USER_ID,
    invoice_id: "inv-006-nov-apex-overdue",
    invoice_number: "INV-2026-0006",
    customer_id: "c1111111-2222-3333-4444-555555555501",
    customer_name: "Elena Rostova",
    customer_email: "elena@apexdigital.io",
    stage: "overdue_1_3",
    status: "ready_for_approval",
    subject: "PAYFLOW AI // Friendly Reminder: Invoice INV-2026-0006 for Apex Digital Studio",
    message_body: "Hi Elena,\n\nWe hope all is well at Apex Digital Studio. This is a gentle follow-up regarding invoice INV-2026-0006 for $1,950.00 USD (Design Token Migration & Production Accessibility QA), which was due on November 4, 2026.\n\nYou can review and settle this invoice directly via the secure PayPal link below.\n\nThank you for your partnership,\nXYPHX Accounts Receivable",
    payment_link: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-APEX-1021-5582",
    channel: "zapier",
    approval_id: "appr-002-pending-rem-006",
    created_at: new Date(Date.now() - 8 * 3600000),
    updated_at: new Date(Date.now() - 8 * 3600000)
  },
  {
    id: "rem-002-hyperion-sent",
    user_id: TARGET_USER_ID,
    invoice_id: "inv-007-nov-hyperion-overdue",
    invoice_number: "INV-2026-0007",
    customer_id: "c1111111-2222-3333-4444-555555555502",
    customer_name: "Marcus Vance",
    customer_email: "m.vance@hyperionlogistics.com",
    stage: "overdue_8_14",
    status: "sent",
    subject: "PAYFLOW AI // Outstanding Invoice Notice: INV-2026-0007 for Hyperion Logistics",
    message_body: "Dear Marcus,\n\nOur records indicate invoice INV-2026-0007 for $4,200.00 USD is currently 14 days overdue. Please verify settlement or reach out if there are any purchase order adjustments required.\n\nWarm regards,\nXYPHX Billing Team",
    payment_link: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-HYPR-1014-6631",
    channel: "zapier",
    created_at: new Date(Date.now() - 3 * 86400000),
    updated_at: new Date(Date.now() - 2 * 86400000),
    approved_at: new Date(Date.now() - 2 * 86400000),
    sent_at: new Date(Date.now() - 2 * 86400000)
  },
  {
    id: "rem-003-starlight-draft",
    user_id: TARGET_USER_ID,
    invoice_id: "inv-004-nov-starlight-sent",
    invoice_number: "INV-2026-0004",
    customer_id: "c1111111-2222-3333-4444-555555555504",
    customer_name: "David Chen",
    customer_email: "dchen@starlightmedia.com",
    stage: "upcoming",
    status: "draft",
    subject: "Upcoming Invoice Reminder: INV-2026-0004 ($2,750.00 USD)",
    message_body: "Hi David,\n\nJust a courteous heads-up that invoice INV-2026-0004 for Starlight Media Works will be due in 8 days.\n\nBest,\nXYPHX",
    payment_link: "https://www.sandbox.paypal.com/invoice/s/pay/INV2-STAR-1105-3312",
    channel: "manual",
    created_at: new Date(Date.now() - 2 * 3600000),
    updated_at: new Date(Date.now() - 2 * 3600000)
  }
]);

// 5. Transactions
print("Inserting Transactions...");
db.transactions.insertMany([
  {
    id: "tx-001-sep-apex",
    user_id: TARGET_USER_ID,
    invoice_id: "inv-001-sep-apex-paid",
    invoice_number: "INV-2026-0001",
    customer_id: "c1111111-2222-3333-4444-555555555501",
    paypal_capture_id: "CAPTURE-9011-8842-SETTLED",
    amount: NumberDecimal("3200.00"),
    fee_amount: NumberDecimal("93.10"),
    net_amount: NumberDecimal("3106.90"),
    currency: "USD",
    status: "completed",
    payer_email: "elena@apexdigital.io",
    created_at: new Date("2026-09-14T15:22:00Z")
  },
  {
    id: "tx-002-oct-hyperion",
    user_id: TARGET_USER_ID,
    invoice_id: "inv-002-oct-hyperion-paid",
    invoice_number: "INV-2026-0002",
    customer_id: "c1111111-2222-3333-4444-555555555502",
    paypal_capture_id: "CAPTURE-1024-9913-SETTLED",
    amount: NumberDecimal("4800.00"),
    fee_amount: NumberDecimal("139.50"),
    net_amount: NumberDecimal("4660.50"),
    currency: "USD",
    status: "completed",
    payer_email: "m.vance@hyperionlogistics.com",
    created_at: new Date("2026-10-12T11:45:00Z")
  },
  {
    id: "tx-003-nov-vanguard",
    user_id: TARGET_USER_ID,
    invoice_id: "inv-003-nov-vanguard-paid",
    invoice_number: "INV-2026-0003",
    customer_id: "c1111111-2222-3333-4444-555555555503",
    paypal_capture_id: "CAPTURE-1102-4421-SETTLED",
    amount: NumberDecimal("5500.00"),
    fee_amount: NumberDecimal("159.80"),
    net_amount: NumberDecimal("5340.20"),
    currency: "USD",
    status: "completed",
    payer_email: "claire@vanguardadvisory.com",
    created_at: new Date("2026-11-02T16:10:00Z")
  }
]);

// 6. Audit Logs
print("Inserting Audit Logs...");
db.audit_logs.insertMany([
  {
    id: "aud-001",
    user_id: TARGET_USER_ID,
    actor: "user",
    action: "invoice.created",
    resource_type: "invoice",
    resource_id: "inv-008-nov-vanguard-pending",
    result: "success",
    correlation_id: "corr-001",
    metadata: { invoice_number: "INV-2026-0008", amount: "6800.00", currency: "USD" },
    created_at: new Date(Date.now() - 18 * 3600000)
  },
  {
    id: "aud-002",
    user_id: TARGET_USER_ID,
    actor: "user",
    action: "invoice.submitted_approval",
    resource_type: "approval",
    resource_id: "appr-001-pending-inv-008",
    result: "success",
    correlation_id: "corr-002",
    metadata: { invoice_number: "INV-2026-0008", status: "pending_approval" },
    created_at: new Date(Date.now() - 18 * 3600000)
  },
  {
    id: "aud-003",
    user_id: TARGET_USER_ID,
    actor: "ai_assistant",
    action: "reminder.scheduled",
    resource_type: "reminder",
    resource_id: "rem-001-apex-overdue",
    result: "success",
    correlation_id: "corr-003",
    metadata: { stage: "overdue_1_3", customer: "Apex Digital Studio" },
    created_at: new Date(Date.now() - 8 * 3600000)
  },
  {
    id: "aud-004",
    user_id: TARGET_USER_ID,
    actor: "paypal_webhook",
    action: "invoice.paid",
    resource_type: "invoice",
    resource_id: "inv-003-nov-vanguard-paid",
    result: "success",
    correlation_id: "corr-004",
    metadata: { gross_amount: "5500.00", currency: "USD", signature_verified: true },
    created_at: new Date("2026-11-02T16:10:00Z")
  }
]);

print("=================================================");
print("PAYFLOW AI: Demo dataset successfully seeded!");
print("=================================================");

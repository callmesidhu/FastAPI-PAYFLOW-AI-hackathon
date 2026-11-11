import { useState, type FC } from 'react';
import { Link } from 'react-router-dom';
import { WaveDecoration } from '../../components/WaveDecoration';
import { useAuth } from '../../lib/auth-context';

export const LandingPage: FC = () => {
  const { isAuthenticated } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const toggleFaq = (index: number) => {
    setOpenFaq(openFaq === index ? null : index);
  };

  const navLinks = [
    { label: 'Product', href: '#product' },
    { label: 'Features', href: '#features' },
    { label: 'How It Works', href: '#how-it-works' },
    { label: 'Who It\'s For', href: '#who-its-for' },
    { label: 'FAQ', href: '#faq' },
  ];

  const faqs = [
    {
      q: 'What is PAYFLOW AI?',
      a: 'PAYFLOW AI is an intelligent, approval-gated accounts receivable assistant built specifically for freelancers, consultants, and independent creative studios. It turns unstructured conversational requests into structured invoice drafts, automates PayPal Sandbox operations, and tracks collections in one unified workspace.',
    },
    {
      q: 'How does the AI work?',
      a: 'The AI interprets natural-language billing instructions and uses controlled, server-side tools to extract customer names, amounts, currencies, line items, and payment terms. It strictly prepares proposal drafts (is_suggestion=True) and can never mutate financial data or dispatch payments without your explicit review.',
    },
    {
      q: 'Does PAYFLOW AI integrate with PayPal?',
      a: 'Yes. PAYFLOW AI integrates directly with the official PayPal REST Invoicing API v2. It creates official PayPal invoice drafts, obtains secure payer URLs, and verifies webhook payment notifications cryptographically before reconciling records.',
    },
    {
      q: 'Can AI send invoices without my approval?',
      a: 'Never. PAYFLOW AI enforces a strict human-in-the-loop cryptographic barrier. Draft invoices require merchant confirmation, which generates a SHA-256 approval hash lock. PayPal operations execute only after you explicitly click approve.',
    },
    {
      q: 'Does PAYFLOW AI process real payments?',
      a: 'The current hackathon version targets the PayPal Developer Sandbox environment (api-m.sandbox.paypal.com) for safe end-to-end evaluation, testing, and judge demonstrations without moving live commercial capital.',
    },
    {
      q: 'Who can use PAYFLOW AI?',
      a: 'PAYFLOW AI is purpose-built for independent professionals: solo freelancers, boutique creative agencies, consultancies, and small service studios who want enterprise-grade receivables management without accounting bloat.',
    },
    {
      q: 'How do I get started?',
      a: 'Click "Get Started" to register your studio account in under 30 seconds. You can start issuing natural-language invoices, exploring the AG Grid ledger, or connecting your PayPal Developer Sandbox immediately.',
    },
  ];

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: 'var(--color-bg)',
        color: 'var(--color-ink)',
        fontFamily: 'var(--font-sans)',
        overflowX: 'hidden',
      }}
    >
      {/* =========================================================================
          1. STICKY TOP NAVIGATION BAR
          ========================================================================= */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          backgroundColor: 'rgba(250, 247, 242, 0.95)',
          backdropFilter: 'blur(8px)',
          borderBottom: '1px solid var(--color-hairline)',
        }}
      >
        <div
          style={{
            maxWidth: '1280px',
            margin: '0 auto',
            padding: '12px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          {/* Brand Logo & Wordmark */}
          <Link
            to="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            <img
              src="/logo.png"
              alt="PAYFLOW AI"
              style={{
                height: '38px',
                width: 'auto',
                objectFit: 'contain',
                border: '1px solid var(--color-hairline)',
                borderRadius: 'var(--radius-sm)',
                boxShadow: '0 1px 3px rgba(11, 11, 11, 0.04)',
              }}
            />
          </Link>

          {/* Desktop Center Links */}
          <nav
            aria-label="Main Navigation"
            style={{
              display: 'none',
              gap: '28px',
              alignItems: 'center',
            }}
            className="landing-desktop-nav"
          >
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                style={{
                  fontSize: '0.75rem',
                  letterSpacing: 'var(--tracking-wide)',
                  textTransform: 'uppercase',
                  fontWeight: 600,
                  color: 'var(--color-muted)',
                  textDecoration: 'none',
                  transition: 'color var(--transition-fast)',
                }}
                className="landing-nav-link"
              >
                {link.label}
              </a>
            ))}
          </nav>

          {/* Right Action CTAs */}
          <div
            style={{
              display: 'none',
              alignItems: 'center',
              gap: '12px',
            }}
            className="landing-desktop-actions"
          >
            {isAuthenticated ? (
              <Link
                to="/dashboard"
                style={{
                  backgroundColor: 'var(--color-ink)',
                  color: '#FAF7F2',
                  border: '1px solid var(--color-ink)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '9px 18px',
                  fontSize: '0.75rem',
                  letterSpacing: 'var(--tracking-wide)',
                  textTransform: 'uppercase',
                  fontWeight: 600,
                  textDecoration: 'none',
                  boxShadow: '0 2px 4px rgba(11, 11, 11, 0.12)',
                }}
              >
                Open Dashboard →
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  style={{
                    backgroundColor: 'transparent',
                    color: 'var(--color-ink)',
                    padding: '8px 16px',
                    fontSize: '0.75rem',
                    letterSpacing: 'var(--tracking-wide)',
                    textTransform: 'uppercase',
                    fontWeight: 600,
                    textDecoration: 'none',
                  }}
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  style={{
                    backgroundColor: 'var(--color-ink)',
                    color: '#FAF7F2',
                    border: '1px solid var(--color-ink)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '9px 18px',
                    fontSize: '0.75rem',
                    letterSpacing: 'var(--tracking-wide)',
                    textTransform: 'uppercase',
                    fontWeight: 600,
                    textDecoration: 'none',
                    boxShadow: '0 2px 4px rgba(11, 11, 11, 0.12)',
                  }}
                >
                  Get Started →
                </Link>
              </>
            )}
          </div>

          {/* Mobile Hamburger Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            style={{
              display: 'block',
              background: 'none',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '6px 12px',
              fontSize: '0.7rem',
              fontWeight: 600,
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              color: 'var(--color-ink)',
              cursor: 'pointer',
            }}
            className="landing-mobile-toggle"
          >
            {mobileMenuOpen ? 'Close' : 'Menu'}
          </button>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div
            style={{
              padding: '16px 24px 20px',
              backgroundColor: 'var(--color-sand)',
              borderBottom: '1px solid var(--color-hairline)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
            }}
          >
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                style={{
                  fontSize: '0.8rem',
                  letterSpacing: 'var(--tracking-wide)',
                  textTransform: 'uppercase',
                  fontWeight: 600,
                  color: 'var(--color-ink)',
                  textDecoration: 'none',
                  padding: '6px 0',
                }}
              >
                {link.label}
              </a>
            ))}
            <div
              style={{
                marginTop: '8px',
                paddingTop: '12px',
                borderTop: '1px solid rgba(58, 52, 44, 0.2)',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              {isAuthenticated ? (
                <Link
                  to="/dashboard"
                  style={{
                    backgroundColor: 'var(--color-ink)',
                    color: '#FAF7F2',
                    padding: '10px',
                    textAlign: 'center',
                    textTransform: 'uppercase',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    textDecoration: 'none',
                  }}
                >
                  Open Dashboard →
                </Link>
              ) : (
                <>
                  <Link
                    to="/login"
                    style={{
                      border: '1px solid var(--color-hairline)',
                      backgroundColor: '#FFFFFF',
                      color: 'var(--color-ink)',
                      padding: '10px',
                      textAlign: 'center',
                      textTransform: 'uppercase',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      textDecoration: 'none',
                    }}
                  >
                    Sign In
                  </Link>
                  <Link
                    to="/register"
                    style={{
                      backgroundColor: 'var(--color-ink)',
                      color: '#FAF7F2',
                      padding: '10px',
                      textAlign: 'center',
                      textTransform: 'uppercase',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      textDecoration: 'none',
                    }}
                  >
                    Get Started →
                  </Link>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      {/* =========================================================================
          2. HERO SECTION
          ========================================================================= */}
      <section
        style={{
          position: 'relative',
          padding: '60px 24px 60px',
          maxWidth: '1280px',
          margin: '0 auto',
          textAlign: 'center',
        }}
      >
        <WaveDecoration position="top-right" width={220} height={110} opacity={0.15} />

        {/* Big Centered Hero Logo */}
        <div style={{ marginBottom: '36px', display: 'flex', justifyContent: 'center' }}>
          <img
            src="/logo.png"
            alt="PAYFLOW AI — Intelligent Receivables"
            style={{
              width: '100%',
              maxWidth: '380px',
              height: 'auto',
              objectFit: 'contain',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
              boxShadow: '0 4px 16px rgba(42, 34, 25, 0.08)',
              backgroundColor: '#FFFFFF',
              display: 'block',
            }}
          />
        </div>

        <div
          style={{
            display: 'inline-block',
            fontSize: '0.675rem',
            letterSpacing: 'var(--tracking-widest)',
            textTransform: 'uppercase',
            fontWeight: 700,
            color: 'var(--color-muted)',
            marginBottom: '16px',
            borderBottom: '1px solid var(--color-hairline)',
            paddingBottom: '4px',
          }}
        >
          THE INTELLIGENT FUTURE OF BUSINESS PAYMENTS
        </div>

        <h1
          style={{
            fontFamily: 'var(--font-serif)',
            fontSize: 'clamp(2.4rem, 5vw, 4.2rem)',
            fontWeight: 700,
            lineHeight: 1.08,
            letterSpacing: 'var(--tracking-tight)',
            textTransform: 'uppercase',
            color: 'var(--color-ink)',
            maxWidth: '960px',
            margin: '0 auto 24px',
          }}
        >
          GET PAID SMARTER.
          <br />
          RUN YOUR BUSINESS BETTER.
        </h1>

        <p
          style={{
            fontSize: 'clamp(1rem, 1.8vw, 1.15rem)',
            lineHeight: 1.6,
            color: 'var(--color-muted)',
            maxWidth: '720px',
            margin: '0 auto 36px',
          }}
        >
          Meet <strong>PAYFLOW AI</strong> — your intelligent accounts receivable assistant.
          Create invoices with natural language, manage payment workflows with PayPal, and stay ahead of outstanding receivables, all from one intelligent workspace.
        </p>

        {/* Hero CTAs */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            gap: '16px',
            marginBottom: '20px',
          }}
        >
          <Link
            to="/register"
            style={{
              backgroundColor: 'var(--color-ink)',
              color: '#FAF7F2',
              border: '1px solid var(--color-ink)',
              borderRadius: 'var(--radius-sm)',
              padding: '14px 32px',
              fontSize: '0.825rem',
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              fontWeight: 600,
              textDecoration: 'none',
              boxShadow: '0 4px 12px rgba(11, 11, 11, 0.15)',
              transition: 'transform var(--transition-fast)',
            }}
          >
            GET STARTED →
          </Link>

          <a
            href="#how-it-works"
            style={{
              backgroundColor: '#FFFFFF',
              color: 'var(--color-ink)',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '14px 28px',
              fontSize: '0.825rem',
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              fontWeight: 600,
              textDecoration: 'none',
              boxShadow: '0 1px 3px rgba(11, 11, 11, 0.04)',
            }}
          >
            EXPLORE HOW IT WORKS
          </a>
        </div>

        <div
          style={{
            fontSize: '0.725rem',
            letterSpacing: '0.04em',
            color: 'var(--color-muted)',
            marginBottom: '56px',
          }}
        >
          AI-powered workflows • PayPal-powered invoice operations • Human-controlled execution
        </div>

        {/* Real Product Hero Showcase Frame */}
        <div
          id="product"
          style={{
            maxWidth: '1120px',
            margin: '0 auto',
            backgroundColor: '#FFFFFF',
            border: '1px solid var(--color-hairline)',
            borderRadius: 'var(--radius-md)',
            padding: '14px',
            boxShadow: '0 20px 40px -10px rgba(42, 34, 25, 0.12), 0 8px 16px -4px rgba(42, 34, 25, 0.04)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              borderBottom: '1px solid var(--color-hairline)',
              backgroundColor: 'var(--color-sand)',
              marginBottom: '12px',
            }}
          >
            <div style={{ display: 'flex', gap: '6px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#D97706' }} />
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#059669' }} />
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#4A4036' }} />
            </div>
            <span
              style={{
                fontSize: '0.65rem',
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                fontWeight: 600,
                color: 'var(--color-muted)',
              }}
            >
              PAYFLOW AI // RECEIVABLES DASHBOARD PREVIEW
            </span>
            <div style={{ width: '32px' }} />
          </div>

          <img
            src="/screenshots/03_dashboard_receivables_desktop.png"
            alt="PAYFLOW AI Receivables Dashboard"
            style={{
              width: '100%',
              height: 'auto',
              display: 'block',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
            }}
          />
        </div>
      </section>

      {/* =========================================================================
          3. THE PROBLEM SECTION
          ========================================================================= */}
      <section
        style={{
          backgroundColor: 'var(--color-cream)',
          borderTop: '1px solid var(--color-hairline)',
          borderBottom: '1px solid var(--color-hairline)',
          padding: '90px 24px',
        }}
      >
        <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '60px' }}>
            <div
              style={{
                fontSize: '0.675rem',
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-muted)',
                marginBottom: '12px',
              }}
            >
              THE CHALLENGE
            </div>
            <h2
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: 'clamp(1.8rem, 3.5vw, 2.8rem)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wide)',
                textTransform: 'uppercase',
                maxWidth: '840px',
                margin: '0 auto 20px',
                lineHeight: 1.15,
              }}
            >
              YOUR BUSINESS SHOULDN'T SPEND ITS TIME CHASING PAYMENTS.
            </h2>
            <p
              style={{
                fontSize: '1rem',
                color: 'var(--color-muted)',
                maxWidth: '680px',
                margin: '0 auto',
                lineHeight: 1.6,
              }}
            >
              Managing invoices shouldn't mean spending hours creating documents, checking payment statuses, and reminding customers. As your business grows, keeping track of every outstanding payment becomes harder.
            </p>
          </div>

          {/* 3 Editorial Feature Blocks */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '24px',
            }}
          >
            {[
              {
                num: '01',
                title: 'MANUAL INVOICING',
                desc: 'Repeated invoice creation takes time away from real business work. Calculating decimals, formatting line items, and mapping merchant fields manually drains valuable studio hours.',
              },
              {
                num: '02',
                title: 'SCATTERED TRACKING',
                desc: 'Unpaid invoices and customer balances become difficult to monitor across email threads, spreadsheets, and banking portals with no single authoritative point of truth.',
              },
              {
                num: '03',
                title: 'REPEATED FOLLOW-UPS',
                desc: 'Remembering when and how to follow up can become repetitive, awkward, or aggressive. Without automated contextual reminders, client relationships are easily strained.',
              },
            ].map((block) => (
              <div
                key={block.num}
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--color-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '36px 28px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.85rem',
                      fontWeight: 700,
                      color: 'var(--color-pending)',
                      marginBottom: '16px',
                      letterSpacing: '0.1em',
                    }}
                  >
                    // PROBLEM {block.num}
                  </div>
                  <h3
                    style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: '1.25rem',
                      fontWeight: 700,
                      letterSpacing: 'var(--tracking-wide)',
                      marginBottom: '14px',
                    }}
                  >
                    {block.title}
                  </h3>
                  <p
                    style={{
                      fontSize: '0.9rem',
                      lineHeight: 1.65,
                      color: 'var(--color-muted)',
                      margin: 0,
                    }}
                  >
                    {block.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* =========================================================================
          4. THE SOLUTION SECTION
          ========================================================================= */}
      <section
        style={{
          padding: '100px 24px',
          maxWidth: '1280px',
          margin: '0 auto',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '64px' }}>
          <div
            style={{
              fontSize: '0.675rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              fontWeight: 700,
              color: 'var(--color-muted)',
              marginBottom: '12px',
            }}
          >
            THE ARCHITECTURE
          </div>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(2rem, 3.8vw, 3rem)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              maxWidth: '880px',
              margin: '0 auto 20px',
              lineHeight: 1.15,
            }}
          >
            ONE INTELLIGENT WORKSPACE.
            <br />
            A BETTER WAY TO MANAGE RECEIVABLES.
          </h2>
          <p
            style={{
              fontSize: '1.05rem',
              lineHeight: 1.6,
              color: 'var(--color-muted)',
              maxWidth: '720px',
              margin: '0 auto',
            }}
          >
            PAYFLOW AI brings AI-assisted invoice creation, payment operations, approval workflows, and receivables intelligence together.
          </p>
        </div>

        {/* 3 Pillars in Alternating Composition */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '32px',
            marginBottom: '72px',
          }}
        >
          <div
            style={{
              backgroundColor: 'var(--color-sand)',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '36px 30px',
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.8rem',
                fontWeight: 700,
                color: 'var(--color-ink)',
                marginBottom: '12px',
              }}
            >
              01
            </div>
            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.25rem',
                letterSpacing: 'var(--tracking-wide)',
                fontWeight: 700,
                marginBottom: '12px',
              }}
            >
              AI UNDERSTANDS INSTRUCTIONS
            </h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.65, color: 'var(--color-muted)', margin: 0 }}>
              Speak naturally about your client work. The AI extracts customer entities, amounts, payment terms, and currencies, turning raw sentences into validated proposal drafts.
            </p>
          </div>

          <div
            style={{
              backgroundColor: 'var(--color-cream)',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '36px 30px',
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.8rem',
                fontWeight: 700,
                color: 'var(--color-ink)',
                marginBottom: '12px',
              }}
            >
              02
            </div>
            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.25rem',
                letterSpacing: 'var(--tracking-wide)',
                fontWeight: 700,
                marginBottom: '12px',
              }}
            >
              PAYPAL POWERS OPERATIONS
            </h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.65, color: 'var(--color-muted)', margin: 0 }}>
              Official PayPal REST Invoicing API v2 integration handles invoice creation, client payer views, and webhook signature verification with cryptographic idempotency keys.
            </p>
          </div>

          <div
            style={{
              backgroundColor: 'var(--color-sand)',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '36px 30px',
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.8rem',
                fontWeight: 700,
                color: 'var(--color-ink)',
                marginBottom: '12px',
              }}
            >
              03
            </div>
            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.25rem',
                letterSpacing: 'var(--tracking-wide)',
                fontWeight: 700,
                marginBottom: '12px',
              }}
            >
              YOU STAY IN FULL CONTROL
            </h3>
            <p style={{ fontSize: '0.9rem', lineHeight: 1.65, color: 'var(--color-muted)', margin: 0 }}>
              The AI cannot issue payments or modify ledger balances on its own. Every action is gated behind a SHA-256 hash locked Human Approval Center for your explicit authorization.
            </p>
          </div>
        </div>

        {/* Real Invoices Explorer Screenshot Preview */}
        <div
          style={{
            backgroundColor: '#FFFFFF',
            border: '1px solid var(--color-hairline)',
            borderRadius: 'var(--radius-md)',
            padding: '16px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div
            style={{
              fontSize: '0.65rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              fontWeight: 700,
              color: 'var(--color-muted)',
              marginBottom: '12px',
            }}
          >
            // REAL INVOICE OPERATIONS WITH AG GRID COMMUNITY LEDGER
          </div>
          <img
            src="/screenshots/04_ag_grid_invoices_desktop.png"
            alt="PAYFLOW AI AG Grid Invoices Ledger"
            style={{
              width: '100%',
              height: 'auto',
              display: 'block',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
            }}
          />
        </div>
      </section>

      {/* =========================================================================
          5. FEATURES SECTION (6 Core Capabilities)
          ========================================================================= */}
      <section
        id="features"
        style={{
          backgroundColor: 'var(--color-cream)',
          borderTop: '1px solid var(--color-hairline)',
          borderBottom: '1px solid var(--color-hairline)',
          padding: '100px 24px',
        }}
      >
        <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '70px' }}>
            <div
              style={{
                fontSize: '0.675rem',
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-muted)',
                marginBottom: '12px',
              }}
            >
              CORE CAPABILITIES
            </div>
            <h2
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: 'clamp(2rem, 3.8vw, 3rem)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wide)',
                textTransform: 'uppercase',
              }}
            >
              EVERYTHING YOUR RECEIVABLES WORKFLOW NEEDS.
            </h2>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
              gap: '28px',
            }}
          >
            {[
              {
                tag: 'FEATURE 01',
                title: 'AI INVOICE ASSISTANT',
                desc: 'Describe an invoice in everyday language. The AI extracts customer name, currency, items, and due dates, preparing a structured editable draft for your review.',
                img: '/screenshots/07_ai_assistant_desktop.png',
              },
              {
                tag: 'FEATURE 02',
                title: 'INTELLIGENT INVOICE MANAGEMENT',
                desc: 'Manage customer invoices, statuses, due dates, and line items in one workspace with multi-column sorting, column filters, and CSV export powered by AG Grid.',
                img: '/screenshots/04_ag_grid_invoices_desktop.png',
              },
              {
                tag: 'FEATURE 03',
                title: 'HUMAN APPROVAL LAYER',
                desc: 'Review sensitive financial operations before execution. Extracted drafts remain proposals until the business owner signs off with cryptographic hash validation.',
                img: '/screenshots/06_approvals_center_desktop.png',
              },
              {
                tag: 'FEATURE 04',
                title: 'PAYPAL INTEGRATION (SANDBOX)',
                desc: 'Official REST Invoicing API v2 integration sends invoices, verifies webhooks cryptographically, and stores official client payment settlement links.',
                img: '/screenshots/10_settings_paypal_diagnostics_desktop.png',
              },
              {
                tag: 'FEATURE 05',
                title: 'CONTEXTUAL PAYMENT REMINDERS',
                desc: 'Generate polite, customer-specific follow-up messages across 6 deterministic aging tiers. Edit and approve reminder drafts before dispatching.',
                img: '/screenshots/05_invoice_detail_timeline_desktop.png',
              },
              {
                tag: 'FEATURE 06',
                title: 'RECEIVABLES INTELLIGENCE',
                desc: 'Understand cash flow at a glance with aging buckets (0–7, 8–30, 31–60, 60+ days), customer balance aggregates, and chronological audit histories.',
                img: '/screenshots/09_analytics_aging_aggrid_desktop.png',
              },
            ].map((feat) => (
              <div
                key={feat.tag}
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--color-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  overflow: 'hidden',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                <div style={{ padding: '28px 24px 20px', flex: 1 }}>
                  <div
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.725rem',
                      fontWeight: 700,
                      color: 'var(--color-pending)',
                      letterSpacing: '0.12em',
                      marginBottom: '10px',
                    }}
                  >
                    // {feat.tag}
                  </div>
                  <h3
                    style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: '1.2rem',
                      fontWeight: 700,
                      letterSpacing: 'var(--tracking-wide)',
                      marginBottom: '10px',
                    }}
                  >
                    {feat.title}
                  </h3>
                  <p
                    style={{
                      fontSize: '0.875rem',
                      lineHeight: 1.6,
                      color: 'var(--color-muted)',
                      margin: 0,
                    }}
                  >
                    {feat.desc}
                  </p>
                </div>
                <div
                  style={{
                    borderTop: '1px solid var(--color-hairline)',
                    backgroundColor: 'var(--color-bg)',
                    padding: '8px',
                  }}
                >
                  <img
                    src={feat.img}
                    alt={feat.title}
                    style={{
                      width: '100%',
                      height: '200px',
                      objectFit: 'cover',
                      objectPosition: 'top',
                      display: 'block',
                      border: '1px solid var(--color-hairline)',
                    }}
                    loading="lazy"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* =========================================================================
          6. HOW IT WORKS SECTION
          ========================================================================= */}
      <section
        id="how-it-works"
        style={{
          padding: '100px 24px',
          maxWidth: '1280px',
          margin: '0 auto',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '64px' }}>
          <div
            style={{
              fontSize: '0.675rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              fontWeight: 700,
              color: 'var(--color-muted)',
              marginBottom: '12px',
            }}
          >
            END-TO-END WORKFLOW
          </div>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(2rem, 3.8vw, 3rem)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
            }}
          >
            FROM A SIMPLE INSTRUCTION TO A STRUCTURED PAYMENT WORKFLOW.
          </h2>
        </div>

        {/* 4 Connected Process Steps */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '24px',
          }}
        >
          {[
            {
              step: 'STEP 01',
              title: 'TELL AI WHAT YOU NEED',
              desc: 'Provide an instruction in natural language: "Create an invoice for Alex Morgan for $500 for website development, due in seven days."',
            },
            {
              step: 'STEP 02',
              title: 'AI PREPARES THE INVOICE',
              desc: 'The assistant extracts the client, computes decimal line items server-side, validates fields, and generates a structured draft preview.',
            },
            {
              step: 'STEP 03',
              title: 'REVIEW AND APPROVE',
              desc: 'The business owner verifies items, amounts, and dates in the Human Approval Center, explicitly authorizing the intended operation.',
            },
            {
              step: 'STEP 04',
              title: 'EXECUTE THROUGH PAYPAL',
              desc: 'The backend dispatches the payload to the PayPal REST Invoicing v2 Sandbox, records the response, and generates client settlement URLs.',
            },
          ].map((s) => (
            <div
              key={s.step}
              style={{
                backgroundColor: '#FFFFFF',
                border: '1px solid var(--color-hairline)',
                borderRadius: 'var(--radius-sm)',
                padding: '32px 24px',
                position: 'relative',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  color: 'var(--color-ink)',
                  backgroundColor: 'var(--color-sand)',
                  display: 'inline-block',
                  padding: '4px 8px',
                  marginBottom: '16px',
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                {s.step}
              </div>
              <h3
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.15rem',
                  fontWeight: 700,
                  letterSpacing: 'var(--tracking-wide)',
                  marginBottom: '12px',
                }}
              >
                {s.title}
              </h3>
              <p
                style={{
                  fontSize: '0.875rem',
                  lineHeight: 1.6,
                  color: 'var(--color-muted)',
                  margin: 0,
                }}
              >
                {s.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* =========================================================================
          7. PRODUCT SHOWCASE (Actual screens)
          ========================================================================= */}
      <section
        style={{
          backgroundColor: 'var(--color-cream)',
          borderTop: '1px solid var(--color-hairline)',
          borderBottom: '1px solid var(--color-hairline)',
          padding: '100px 24px',
        }}
      >
        <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '64px' }}>
            <div
              style={{
                fontSize: '0.675rem',
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-muted)',
                marginBottom: '12px',
              }}
            >
              PRODUCT WALKTHROUGH
            </div>
            <h2
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: 'clamp(2rem, 3.8vw, 3rem)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wide)',
                textTransform: 'uppercase',
              }}
            >
              DESIGNED FOR CLARITY. BUILT FOR CONTROL.
            </h2>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
              gap: '32px',
            }}
          >
            {[
              {
                title: 'INVOICE DETAIL & TIMELINE',
                caption: 'Chronological activity stream tracking proposals, approvals, PayPal transmissions, and payment reconcile events.',
                img: '/screenshots/05_invoice_detail_timeline_desktop.png',
              },
              {
                title: 'HUMAN APPROVAL CENTER',
                caption: 'Cryptographic hash locking ensures no AI draft reaches PayPal without explicit merchant sign-off.',
                img: '/screenshots/06_approvals_center_desktop.png',
              },
              {
                title: 'RECEIVABLES AGING ANALYTICS',
                caption: 'Deterministic bucket breakdown (0–7, 8–30, 31–60, 60+ days) and AG Grid customer balance explorer.',
                img: '/screenshots/09_analytics_aging_aggrid_desktop.png',
              },
              {
                title: 'PAYPAL SANDBOX DIAGNOSTICS',
                caption: 'Live connectivity telemetry, OAuth token expiry caching, and cryptographic webhook health.',
                img: '/screenshots/10_settings_paypal_diagnostics_desktop.png',
              },
            ].map((item) => (
              <div
                key={item.title}
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--color-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '16px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <img
                  src={item.img}
                  alt={item.title}
                  style={{
                    width: '100%',
                    height: '240px',
                    objectFit: 'cover',
                    objectPosition: 'top',
                    display: 'block',
                    border: '1px solid var(--color-hairline)',
                    marginBottom: '16px',
                  }}
                  loading="lazy"
                />
                <h3
                  style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: '1.1rem',
                    fontWeight: 700,
                    letterSpacing: 'var(--tracking-wide)',
                    marginBottom: '8px',
                  }}
                >
                  {item.title}
                </h3>
                <p style={{ fontSize: '0.85rem', lineHeight: 1.55, color: 'var(--color-muted)', margin: 0 }}>
                  {item.caption}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* =========================================================================
          8. AI INTELLIGENCE SECTION
          ========================================================================= */}
      <section
        style={{
          padding: '100px 24px',
          maxWidth: '1280px',
          margin: '0 auto',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '60px' }}>
          <div
            style={{
              fontSize: '0.675rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              fontWeight: 700,
              color: 'var(--color-muted)',
              marginBottom: '12px',
            }}
          >
            ARCHITECTURE & INTELLIGENCE
          </div>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(2rem, 3.8vw, 3rem)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              maxWidth: '840px',
              margin: '0 auto 20px',
            }}
          >
            NOT JUST ANOTHER CHATBOT.
            <br />
            AN ASSISTANT THAT UNDERSTANDS YOUR WORKFLOW.
          </h2>
          <p
            style={{
              fontSize: '1rem',
              lineHeight: 1.6,
              color: 'var(--color-muted)',
              maxWidth: '700px',
              margin: '0 auto',
            }}
          >
            PAYFLOW AI combines natural-language understanding with structured business operations. Users can ask questions about receivables, prepare invoices, explore overdue payments, and generate contextual follow-up drafts.
          </p>
        </div>

        {/* Split Screen AI Interface */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '32px',
            alignItems: 'center',
            backgroundColor: '#FFFFFF',
            border: '1px solid var(--color-hairline)',
            borderRadius: 'var(--radius-md)',
            padding: '36px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div>
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.725rem',
                fontWeight: 700,
                color: 'var(--color-pending)',
                letterSpacing: '0.12em',
                marginBottom: '12px',
              }}
            >
              // CONSTRAINED ORCHESTRATION PIPELINE
            </div>
            <h3
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.4rem',
                fontWeight: 700,
                marginBottom: '16px',
              }}
            >
              STRUCTURED TOOL CALLING & SERVER VALIDATION
            </h3>
            <ul
              style={{
                listStyle: 'none',
                padding: 0,
                margin: '0 0 24px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                fontSize: '0.9rem',
                lineHeight: 1.6,
                color: 'var(--color-muted)',
              }}
            >
              <li>• <strong>Natural-Language Understanding:</strong> Google Gemini parses unstructured customer prompts without conversational drift.</li>
              <li>• <strong>5 Allowlisted Tools:</strong> Read-only retrieval and draft proposal tools enforce least-privilege principles.</li>
              <li>• <strong>Authoritative Decimal Calculation:</strong> Monetary numbers are calculated strictly on the backend with Python Decimal, not by the LLM.</li>
              <li>• <strong>Human-in-the-Loop Barrier:</strong> Proposal previews always require merchant confirmation before database write.</li>
            </ul>

            <Link
              to="/register"
              style={{
                display: 'inline-block',
                backgroundColor: 'var(--color-ink)',
                color: '#FAF7F2',
                borderRadius: 'var(--radius-sm)',
                padding: '11px 22px',
                fontSize: '0.75rem',
                letterSpacing: 'var(--tracking-wide)',
                textTransform: 'uppercase',
                fontWeight: 600,
                textDecoration: 'none',
              }}
            >
              TRY AI ASSISTANT IN SANDBOX →
            </Link>
          </div>

          <div
            style={{
              backgroundColor: 'var(--color-bg)',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
              padding: '12px',
            }}
          >
            <img
              src="/screenshots/07_ai_assistant_desktop.png"
              alt="PAYFLOW AI Conversational Interface"
              style={{
                width: '100%',
                height: 'auto',
                display: 'block',
                border: '1px solid var(--color-hairline)',
              }}
              loading="lazy"
            />
          </div>
        </div>
      </section>

      {/* =========================================================================
          9. TRUST AND CONTROL SECTION
          ========================================================================= */}
      <section
        style={{
          backgroundColor: 'var(--color-sand)',
          borderTop: '1px solid var(--color-hairline)',
          borderBottom: '1px solid var(--color-hairline)',
          padding: '90px 24px',
        }}
      >
        <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '60px' }}>
            <div
              style={{
                fontSize: '0.675rem',
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-muted)',
                marginBottom: '12px',
              }}
            >
              SAFETY INVARIANTS
            </div>
            <h2
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: 'clamp(2rem, 3.8vw, 3rem)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wide)',
                textTransform: 'uppercase',
              }}
            >
              INTELLIGENCE SHOULD NEVER MEAN LOSING CONTROL.
            </h2>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
              gap: '24px',
            }}
          >
            {[
              {
                title: 'HUMAN APPROVAL',
                desc: 'Sensitive financial operations require explicit business-owner authorization. The AI prepares proposals; the business owner executes payments.',
              },
              {
                title: 'VERIFIED PAYMENT STATUS',
                desc: 'Payment status changes require verified PayPal responses or cryptographically authenticated webhook signatures. No optimistic ledger mutation.',
              },
              {
                title: 'TRACEABLE ACTIVITY',
                desc: 'Maintain an immutable append-only activity history for invoice operations, approval sign-offs, and payment reconciliation events.',
              },
            ].map((item) => (
              <div
                key={item.title}
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--color-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '36px 28px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <h3
                  style={{
                    fontFamily: 'var(--font-serif)',
                    fontSize: '1.25rem',
                    fontWeight: 700,
                    letterSpacing: 'var(--tracking-wide)',
                    marginBottom: '14px',
                  }}
                >
                  {item.title}
                </h3>
                <p style={{ fontSize: '0.9rem', lineHeight: 1.65, color: 'var(--color-muted)', margin: 0 }}>
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* =========================================================================
          10. WHO IT IS FOR SECTION
          ========================================================================= */}
      <section
        id="who-its-for"
        style={{
          padding: '100px 24px',
          maxWidth: '1280px',
          margin: '0 auto',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: '64px' }}>
          <div
            style={{
              fontSize: '0.675rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              fontWeight: 700,
              color: 'var(--color-muted)',
              marginBottom: '12px',
            }}
          >
            AUDIENCE & USE CASES
          </div>
          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(2rem, 3.8vw, 3rem)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
            }}
          >
            BUILT FOR BUSINESSES THAT VALUE THEIR TIME.
          </h2>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '24px',
          }}
        >
          {[
            {
              role: 'FREELANCERS',
              desc: 'Simplify invoice preparation and customer follow-ups. Turn project notes into professional PayPal invoices in seconds without accounting friction.',
            },
            {
              role: 'CREATIVE AGENCIES',
              desc: 'Organize customer invoices and outstanding balances across multiple clients and retainers with clean AG Grid ledger views.',
            },
            {
              role: 'CONSULTANTS',
              desc: 'Spend less time on repetitive invoice administration. Let the AI draft respectful payment reminders aligned with client terms.',
            },
            {
              role: 'SMALL BUSINESSES',
              desc: 'Understand receivables and payment activity more clearly with deterministic aging buckets and multi-currency tracking.',
            },
          ].map((card) => (
            <div
              key={card.role}
              style={{
                backgroundColor: 'var(--color-cream)',
                border: '1px solid var(--color-hairline)',
                borderRadius: 'var(--radius-sm)',
                padding: '32px 24px',
              }}
            >
              <h3
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.2rem',
                  fontWeight: 700,
                  letterSpacing: 'var(--tracking-wide)',
                  marginBottom: '12px',
                }}
              >
                {card.role}
              </h3>
              <p style={{ fontSize: '0.875rem', lineHeight: 1.6, color: 'var(--color-muted)', margin: 0 }}>
                {card.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* =========================================================================
          11. FAQ ACCORDION SECTION
          ========================================================================= */}
      <section
        id="faq"
        style={{
          backgroundColor: 'var(--color-sand)',
          borderTop: '1px solid var(--color-hairline)',
          borderBottom: '1px solid var(--color-hairline)',
          padding: '100px 24px',
        }}
      >
        <div style={{ maxWidth: '840px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '56px' }}>
            <div
              style={{
                fontSize: '0.675rem',
                letterSpacing: 'var(--tracking-widest)',
                textTransform: 'uppercase',
                fontWeight: 700,
                color: 'var(--color-muted)',
                marginBottom: '12px',
              }}
            >
              FREQUENTLY ASKED QUESTIONS
            </div>
            <h2
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: 'clamp(2rem, 3.5vw, 2.8rem)',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wide)',
                textTransform: 'uppercase',
              }}
            >
              CLEAR ANSWERS. COMPLETE TRANSPARENCY.
            </h2>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {faqs.map((faq, idx) => {
              const isOpen = openFaq === idx;
              return (
                <div
                  key={faq.q}
                  style={{
                    backgroundColor: '#FFFFFF',
                    border: '1px solid var(--color-hairline)',
                    borderRadius: 'var(--radius-sm)',
                    overflow: 'hidden',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => toggleFaq(idx)}
                    aria-expanded={isOpen}
                    style={{
                      width: '100%',
                      padding: '20px 24px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      background: 'none',
                      border: 'none',
                      textAlign: 'left',
                      fontFamily: 'var(--font-serif)',
                      fontSize: '1.05rem',
                      fontWeight: 700,
                      color: 'var(--color-ink)',
                      letterSpacing: 'var(--tracking-wide)',
                      cursor: 'pointer',
                    }}
                  >
                    <span>{faq.q}</span>
                    <span style={{ fontSize: '1.2rem', fontWeight: 400, marginLeft: '12px' }}>
                      {isOpen ? '−' : '+'}
                    </span>
                  </button>
                  {isOpen && (
                    <div
                      style={{
                        padding: '0 24px 20px',
                        fontSize: '0.9rem',
                        lineHeight: 1.65,
                        color: 'var(--color-muted)',
                        borderTop: '1px solid rgba(58, 52, 44, 0.1)',
                        paddingTop: '14px',
                      }}
                    >
                      {faq.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* =========================================================================
          12. FINAL FULL-WIDTH CTA SECTION
          ========================================================================= */}
      <section
        style={{
          backgroundColor: 'var(--color-ink)',
          color: '#FAF7F2',
          padding: '100px 24px',
          textAlign: 'center',
        }}
      >
        <div style={{ maxWidth: '840px', margin: '0 auto' }}>
          <div
            style={{
              fontSize: '0.675rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--color-sand)',
              marginBottom: '16px',
            }}
          >
            GET STARTED TODAY
          </div>

          <h2
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: 'clamp(2.2rem, 4.5vw, 3.6rem)',
              fontWeight: 700,
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              color: '#FFFFFF',
              marginBottom: '20px',
              lineHeight: 1.15,
            }}
          >
            MAKE EVERY PAYMENT WORKFLOW SMARTER.
          </h2>

          <p
            style={{
              fontSize: '1.05rem',
              lineHeight: 1.6,
              color: 'rgba(250, 247, 242, 0.8)',
              maxWidth: '620px',
              margin: '0 auto 36px',
            }}
          >
            Bring AI-powered intelligence and human-controlled payment operations into your business workflow.
          </p>

          <Link
            to="/register"
            style={{
              display: 'inline-block',
              backgroundColor: '#FAF7F2',
              color: 'var(--color-ink)',
              border: '1px solid #FAF7F2',
              borderRadius: 'var(--radius-sm)',
              padding: '15px 36px',
              fontSize: '0.85rem',
              letterSpacing: 'var(--tracking-wider)',
              textTransform: 'uppercase',
              fontWeight: 700,
              textDecoration: 'none',
              boxShadow: '0 4px 14px rgba(0, 0, 0, 0.4)',
              transition: 'transform var(--transition-fast)',
            }}
          >
            EXPLORE PAYFLOW AI →
          </Link>

          <div
            style={{
              marginTop: '40px',
              fontSize: '0.7rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'rgba(250, 247, 242, 0.5)',
            }}
          >
            PAYFLOW AI — BUILT BY TEAM XYPHX
          </div>
        </div>
      </section>

      {/* =========================================================================
          13. MINIMALIST FOOTER
          ========================================================================= */}
      <footer
        style={{
          backgroundColor: '#050505',
          color: '#FAF7F2',
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          padding: '60px 24px 40px',
        }}
      >
        <div
          style={{
            maxWidth: '1280px',
            margin: '0 auto',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '32px',
            marginBottom: '40px',
          }}
        >
          <div>
            <div
              style={{
                fontFamily: 'var(--font-serif)',
                fontSize: '1.3rem',
                fontWeight: 700,
                letterSpacing: 'var(--tracking-wide)',
                marginBottom: '4px',
              }}
            >
              PAYFLOW AI
            </div>
            <div style={{ fontSize: '0.75rem', color: 'rgba(250, 247, 242, 0.6)' }}>
              Intelligent Receivables. Human-Controlled Payments.
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '24px',
              fontSize: '0.75rem',
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
            }}
          >
            {navLinks.map((l) => (
              <a
                key={l.href}
                href={l.href}
                style={{
                  color: 'rgba(250, 247, 242, 0.75)',
                  textDecoration: 'none',
                }}
              >
                {l.label}
              </a>
            ))}
            <Link
              to="/login"
              style={{
                color: 'rgba(250, 247, 242, 0.75)',
                textDecoration: 'none',
              }}
            >
              Sign In
            </Link>
            <Link
              to="/register"
              style={{
                color: '#FFFFFF',
                textDecoration: 'none',
                fontWeight: 600,
              }}
            >
              Get Started
            </Link>
          </div>
        </div>

        <div
          style={{
            maxWidth: '1280px',
            margin: '0 auto',
            paddingTop: '24px',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: '16px',
            fontSize: '0.7rem',
            color: 'rgba(250, 247, 242, 0.45)',
          }}
        >
          <div>© 2026 XyphX. Built for the PayPal AI Hackathon. All rights reserved.</div>
          <div style={{ display: 'flex', gap: '20px' }}>
            <span>PayPal Sandbox Integration</span>
            <span>Google Gemini AI</span>
            <span>AG Grid Community</span>
          </div>
        </div>
      </footer>

      <style>{`
        @media (min-width: 860px) {
          .landing-desktop-nav {
            display: flex !important;
          }
          .landing-desktop-actions {
            display: flex !important;
          }
          .landing-mobile-toggle {
            display: none !important;
          }
        }
        .landing-nav-link:hover {
          color: var(--color-ink) !important;
        }
      `}</style>
    </div>
  );
};

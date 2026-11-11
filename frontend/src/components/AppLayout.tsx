import { useState, type FC, type ReactNode } from 'react';
import { WaveDecoration } from './WaveDecoration';

export interface NavItem {
  id: string;
  label: string;
  badge?: number | string;
  icon?: ReactNode;
}

export interface AppLayoutProps {
  children: ReactNode;
  activeNavId: string;
  onNavigate: (id: string) => void;
  userEmail?: string;
  onLogout?: () => void;
  brandSubtitle?: string;
}

export const NAV_ITEMS: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'assistant', label: 'AI Assistant' },
  { id: 'invoices', label: 'Invoices' },
  { id: 'customers', label: 'Customers' },
  { id: 'approvals', label: 'Approval Center' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'settings', label: 'Settings' },
];

export const AppLayout: FC<AppLayoutProps> = ({
  children,
  activeNavId,
  onNavigate,
  userEmail,
  onLogout,
  brandSubtitle = 'ACCOUNTS RECEIVABLE AGENT',
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleNavClick = (id: string) => {
    onNavigate(id);
    setMobileMenuOpen(false);
  };

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        backgroundColor: 'var(--color-bg)',
      }}
    >
      {/* =========================================================================
          DESKTOP LEFT SIDEBAR
          ========================================================================= */}
      <aside
        style={{
          width: '260px',
          flexShrink: 0,
          backgroundColor: 'var(--color-sand)',
          borderRight: 'var(--border-hairline)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          height: '100vh',
        }}
        className="payflow-desktop-sidebar"
      >
        <div>
          {/* Brand Wordmark Header */}
          <div
            style={{
              padding: '28px 24px 20px',
              borderBottom: 'var(--border-hairline)',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <img
              src="/logo.png"
              alt="PAYFLOW Logo"
              style={{ width: '32px', height: '32px', objectFit: 'contain' }}
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
            <div>
              <div
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.2rem',
                  letterSpacing: 'var(--tracking-wide)',
                  fontWeight: 700,
                  color: 'var(--color-ink)',
                  lineHeight: 1.1,
                }}
              >
                PAYFLOW AI
              </div>
              <div
                style={{
                  fontSize: '0.625rem',
                  letterSpacing: 'var(--tracking-widest)',
                  textTransform: 'uppercase',
                  color: 'var(--color-muted)',
                  marginTop: '2px',
                }}
              >
                {brandSubtitle}
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav
            aria-label="Sidebar Navigation"
            style={{ padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: '4px' }}
          >
            {NAV_ITEMS.map((item) => {
              const isActive = activeNavId === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNavClick(item.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-sm)',
                    border: isActive ? '1px solid var(--color-ink)' : '1px solid transparent',
                    backgroundColor: isActive ? 'var(--color-ink)' : 'transparent',
                    color: isActive ? 'var(--color-bg)' : 'var(--color-ink)',
                    fontFamily: 'var(--font-sans)',
                    fontSize: '0.75rem',
                    letterSpacing: 'var(--tracking-wide)',
                    textTransform: 'uppercase',
                    fontWeight: 600,
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                  className={`nav-item ${isActive ? 'nav-item-active' : ''}`}
                >
                  <span>{item.label}</span>
                  {item.badge !== undefined && (
                    <span
                      style={{
                        fontSize: '0.65rem',
                        padding: '2px 6px',
                        backgroundColor: isActive ? 'var(--color-sand)' : 'var(--color-cream)',
                        color: 'var(--color-ink)',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* User Identity & Logout Band */}
        <div
          style={{
            padding: '20px 24px',
            borderTop: 'var(--border-hairline)',
            backgroundColor: 'rgba(58, 52, 44, 0.05)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          {userEmail && (
            <div
              style={{
                fontSize: '0.725rem',
                color: 'var(--color-muted)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {userEmail}
            </div>
          )}
          {onLogout && (
            <button
              onClick={onLogout}
              className="sign-out-btn"
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-ink)',
                fontSize: '0.675rem',
                letterSpacing: 'var(--tracking-wider)',
                textTransform: 'uppercase',
                fontWeight: 600,
                textAlign: 'left',
                padding: 0,
                cursor: 'pointer',
              }}
            >
              Sign Out →
            </button>
          )}
        </div>
      </aside>

      {/* =========================================================================
          MAIN APPLICATION CANVAS
          ========================================================================= */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Mobile Top Header (Hidden on Desktop via CSS) */}
        <header
          style={{
            borderBottom: 'var(--border-hairline)',
            backgroundColor: 'var(--color-sand)',
            padding: '12px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
          className="payflow-mobile-header"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <img
              src="/logo.png"
              alt="Logo"
              style={{ width: '22px', height: '22px', objectFit: 'contain' }}
              onError={(e) => {
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
            <span
              style={{
                fontFamily: 'var(--font-serif)',
                fontWeight: 700,
                fontSize: '1rem',
                letterSpacing: 'var(--tracking-wide)',
              }}
            >
              PAYFLOW AI
            </span>
          </div>

          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle navigation menu"
            style={{
              padding: '6px 10px',
              backgroundColor: 'var(--color-ink)',
              color: 'var(--color-bg)',
              border: 'none',
              fontSize: '0.7rem',
              letterSpacing: 'var(--tracking-wider)',
            }}
          >
            {mobileMenuOpen ? 'CLOSE' : 'MENU'}
          </button>
        </header>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <nav
            aria-label="Mobile Navigation"
            style={{
              backgroundColor: 'var(--color-sand)',
              borderBottom: 'var(--border-hairline)',
              padding: '16px 20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
            className="payflow-mobile-nav"
          >
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => handleNavClick(item.id)}
                style={{
                  padding: '10px 14px',
                  backgroundColor: activeNavId === item.id ? 'var(--color-ink)' : 'transparent',
                  color: activeNavId === item.id ? 'var(--color-bg)' : 'var(--color-ink)',
                  border: 'var(--border-hairline)',
                  textAlign: 'left',
                  textTransform: 'uppercase',
                  fontSize: '0.75rem',
                  letterSpacing: 'var(--tracking-wide)',
                  fontWeight: 600,
                }}
              >
                {item.label}
              </button>
            ))}
          </nav>
        )}

        {/* Main Content Area with subtle wave line art in quiet corner */}
        <main
          style={{
            flex: 1,
            padding: '40px 48px',
            maxWidth: '1280px',
            width: '100%',
            margin: '0 auto',
            position: 'relative',
          }}
          className="payflow-main-content"
        >
          <WaveDecoration position="top-right" width={180} height={90} opacity={0.12} />
          {children}
        </main>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .payflow-desktop-sidebar {
            display: none !important;
          }
          .payflow-mobile-header {
            display: flex !important;
          }
          .payflow-main-content {
            padding: 24px 16px !important;
          }
        }
        @media (min-width: 769px) {
          .payflow-mobile-header {
            display: none !important;
          }
          .payflow-mobile-nav {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
};

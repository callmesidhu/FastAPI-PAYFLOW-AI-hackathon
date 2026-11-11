import { useState, type FC, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Alert, Button, TextInput } from '../../components';
import { useAuth } from '../../lib/auth-context';

export const LoginView: FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const destination = (location.state as { from?: { pathname: string } })?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please provide both email and password.');
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      navigate(destination, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Invalid email or password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFillDemo = () => {
    setEmail('demo@payflowai.com');
    setPassword('DemoPassword2026!');
    setError(null);
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'radial-gradient(ellipse at top, #F1F5F9 0%, #E2E8F0 100%)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        fontFamily: 'var(--font-sans)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '440px',
          backgroundColor: '#FFFFFF',
          border: '1px solid #E2E8F0',
          borderRadius: '16px',
          padding: '44px 36px',
          boxShadow: '0 20px 25px -5px rgba(15, 23, 42, 0.08), 0 8px 10px -6px rgba(15, 23, 42, 0.04)',
        }}
      >
        {/* Wordmark Header */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              margin: '0 auto 16px auto',
              backgroundColor: '#0F172A',
              borderRadius: '14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(15, 23, 42, 0.15)',
            }}
          >
            <span style={{ color: '#FFFFFF', fontSize: '1.4rem', fontWeight: 700, fontFamily: 'var(--font-sans)' }}>
              P
            </span>
          </div>
          <h1
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '1.75rem',
              letterSpacing: '-0.025em',
              fontWeight: 800,
              color: '#0F172A',
              margin: 0,
            }}
          >
            PAYFLOW AI
          </h1>
          <div
            style={{
              fontSize: '0.75rem',
              fontWeight: 500,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              color: '#64748B',
              marginTop: '6px',
            }}
          >
            Autonomous Accounts Receivable Agent
          </div>
        </div>

        {error && (
          <div style={{ marginBottom: '20px' }}>
            <Alert type="error" message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <TextInput
            label="Business Email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="owner@yourstudio.com"
          />

          <TextInput
            label="Password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••••••"
          />

          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isSubmitting}
            style={{
              width: '100%',
              marginTop: '12px',
              padding: '12px',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '0.85rem',
              letterSpacing: '0.02em',
              backgroundColor: '#0F172A',
            }}
          >
            Sign In to Dashboard →
          </Button>
        </form>

        {/* Demo Fast-fill Band */}
        <div
          style={{
            marginTop: '28px',
            paddingTop: '20px',
            borderTop: '1px solid #E2E8F0',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
          }}
        >
          <button
            type="button"
            onClick={handleFillDemo}
            style={{
              backgroundColor: '#F8FAFC',
              border: '1px solid #CBD5E1',
              borderRadius: '8px',
              padding: '10px 14px',
              color: '#334155',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              textAlign: 'center',
              transition: 'all 0.15s ease',
            }}
          >
            ⚡ Auto-Fill Demo Credentials
          </button>
          <span style={{ fontSize: '0.7rem', color: '#94A3B8', textAlign: 'center', lineHeight: 1.4 }}>
            Pre-configured with sample receivables data & audit trail
          </span>
        </div>

        {/* Registration Link */}
        <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '0.85rem', color: '#64748B' }}>
          Don't have an account?{' '}
          <Link
            to="/register"
            style={{
              fontWeight: 600,
              color: '#0F172A',
              textDecoration: 'none',
            }}
          >
            Create an Account
          </Link>
        </div>
      </div>
    </div>
  );
};

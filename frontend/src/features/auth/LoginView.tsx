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
        backgroundColor: 'var(--color-bg)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '440px',
          backgroundColor: 'var(--color-cream)',
          border: 'var(--border-hairline)',
          borderRadius: 'var(--radius-sm)',
          padding: '48px 36px 40px',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        {/* Wordmark Header */}
        <div style={{ textAlign: 'center', marginBottom: '36px' }}>
          <img
            src="/logo.png"
            alt="PAYFLOW Logo Mark"
            style={{ width: '52px', height: '52px', objectFit: 'contain', marginBottom: '20px' }}
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
          <h1
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.75rem',
              letterSpacing: 'var(--tracking-wide)',
              fontWeight: 700,
              color: 'var(--color-ink)',
              margin: 0,
            }}
          >
            PAYFLOW AI
          </h1>
          <div
            style={{
              fontSize: '0.65rem',
              letterSpacing: 'var(--tracking-widest)',
              textTransform: 'uppercase',
              color: 'var(--color-muted)',
              marginTop: '6px',
            }}
          >
            ACCOUNTS RECEIVABLE AGENT • SIGN IN
          </div>
        </div>

        {error && (
          <div style={{ marginBottom: '20px' }}>
            <Alert type="error" message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
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
            size="lg"
            isLoading={isSubmitting}
            style={{ width: '100%', marginTop: '4px' }}
          >
            AUTHENTICATE →
          </Button>
        </form>

        {/* Demo Fast-fill Band */}
        <div
          style={{
            marginTop: '28px',
            paddingTop: '20px',
            borderTop: 'var(--border-subtle)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <button
            type="button"
            onClick={handleFillDemo}
            className="demo-fill-btn"
            style={{
              background: 'none',
              border: 'var(--border-subtle)',
              borderRadius: 'var(--radius-sm)',
              padding: '10px 20px',
              color: 'var(--color-muted)',
              fontSize: '0.7rem',
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all var(--transition-fast)',
            }}
          >
            ⚡ Fill Demo Credentials
          </button>
          <span style={{ fontSize: '0.65rem', color: 'var(--color-muted)', textAlign: 'center', lineHeight: 1.4 }}>
            Demo credentials are separate from PayPal Sandbox accounts.
          </span>
        </div>

        {/* Registration Link */}
        <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--color-muted)' }}>
          Don't have an account?{' '}
          <Link
            to="/register"
            className="auth-link"
            style={{
              fontWeight: 600,
              color: 'var(--color-ink)',
              textDecoration: 'none',
              letterSpacing: '0.02em',
            }}
          >
            Register Business
          </Link>
        </div>
      </div>
    </div>
  );
};

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
          padding: '40px 32px',
          boxShadow: 'var(--shadow-subtle)',
        }}
      >
        {/* Wordmark Header */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <img
            src="/logo.png"
            alt="PAYFLOW Logo"
            style={{ width: '36px', height: '36px', objectFit: 'contain', marginBottom: '12px' }}
            onError={(e) => {
              (e.target as HTMLElement).style.display = 'none';
            }}
          />
          <h1
            style={{
              fontFamily: 'var(--font-serif)',
              fontSize: '1.6rem',
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
              marginTop: '4px',
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
            style={{ width: '100%', marginTop: '8px' }}
          >
            AUTHENTICATE →
          </Button>
        </form>

        {/* Demo Fast-fill Band */}
        <div
          style={{
            marginTop: '24px',
            paddingTop: '16px',
            borderTop: '1px solid rgba(58, 52, 44, 0.2)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <button
            type="button"
            onClick={handleFillDemo}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--color-muted)',
              fontSize: '0.7rem',
              letterSpacing: 'var(--tracking-wide)',
              textTransform: 'uppercase',
              fontWeight: 600,
              cursor: 'pointer',
              textAlign: 'center',
            }}
          >
            [ Fill Local Demo Credentials ]
          </button>
          <span style={{ fontSize: '0.65rem', color: 'var(--color-muted)', textAlign: 'center', lineHeight: 1.4 }}>
            Demo credentials are separate from PayPal Sandbox accounts.
          </span>
        </div>

        {/* Registration Link */}
        <div style={{ marginTop: '20px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--color-muted)' }}>
          Don't have an account?{' '}
          <Link
            to="/register"
            style={{
              fontWeight: 600,
              color: 'var(--color-ink)',
              textDecoration: 'underline',
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

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
          backgroundColor: '#FFFFFF',
          border: '1px solid var(--color-hairline)',
          borderRadius: 'var(--radius-md)',
          padding: '44px 36px 36px',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        {/* Brand Hero Logo with Full Lockup */}
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <img
            src="/logo.png"
            alt="PAYFLOW AI — Your AI Accounts Receivable Agent"
            style={{
              width: '100%',
              maxWidth: '320px',
              height: 'auto',
              objectFit: 'contain',
              display: 'block',
              margin: '0 auto',
              border: '1px solid var(--color-hairline)',
              borderRadius: 'var(--radius-sm)',
              boxShadow: '0 1px 3px rgba(11, 11, 11, 0.04)',
            }}
          />
        </div>

        {error && (
          <div style={{ marginBottom: '20px' }}>
            <Alert type="error" message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
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
            style={{ width: '100%', marginTop: '6px' }}
          >
            Authenticate →
          </Button>
        </form>

        {/* Registration Link */}
        <div style={{ marginTop: '22px', textAlign: 'center', fontSize: '0.825rem', color: 'var(--color-muted)' }}>
          Don't have an account?{' '}
          <Link
            to="/register"
            className="auth-link"
            style={{
              fontWeight: 600,
              color: 'var(--color-ink)',
              textDecoration: 'underline',
              textUnderlineOffset: '3px',
            }}
          >
            Register Business
          </Link>
        </div>
      </div>
    </div>
  );
};

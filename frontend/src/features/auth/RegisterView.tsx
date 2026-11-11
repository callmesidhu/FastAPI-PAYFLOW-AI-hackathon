import { useState, type FC, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Alert, Button, TextInput } from '../../components';
import { useAuth } from '../../lib/auth-context';

export const RegisterView: FC = () => {
  const navigate = useNavigate();
  const { register } = useAuth();

  const [name, setName] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name || !email || !password) {
      setError('Please fill in all required fields.');
      return;
    }
    if (password.length < 8) {
      setError('Password must contain at least 8 characters.');
      return;
    }

    setError(null);
    setIsSubmitting(true);
    try {
      await register(email, password, name, businessName);
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed. Please try again.');
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
          maxWidth: '480px',
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
            CREATE BUSINESS OWNER ACCOUNT
          </div>
        </div>

        {error && (
          <div style={{ marginBottom: '20px' }}>
            <Alert type="error" message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <TextInput
            label="Your Full Name"
            type="text"
            required
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Alex Vance"
          />

          <TextInput
            label="Business / Studio Name (Optional)"
            type="text"
            autoComplete="organization"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
            placeholder="Vance Creative Studio"
          />

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
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters with number/symbol"
            helperText="Requires at least 8 characters with numbers or symbols."
          />

          <Button
            type="submit"
            variant="primary"
            size="lg"
            isLoading={isSubmitting}
            style={{ width: '100%', marginTop: '4px' }}
          >
            REGISTER ACCOUNT →
          </Button>
        </form>

        <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '0.8rem', color: 'var(--color-muted)' }}>
          Already have an account?{' '}
          <Link
            to="/login"
            className="auth-link"
            style={{
              fontWeight: 600,
              color: 'var(--color-ink)',
              textDecoration: 'none',
              letterSpacing: '0.02em',
            }}
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};

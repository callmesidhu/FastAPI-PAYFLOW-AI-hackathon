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
          maxWidth: '480px',
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
            Create Business Owner Account
          </div>
        </div>

        {error && (
          <div style={{ marginBottom: '20px' }}>
            <Alert type="error" message={error} onDismiss={() => setError(null)} />
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
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
            Create Account & Get Started →
          </Button>
        </form>

        <div style={{ marginTop: '24px', textAlign: 'center', fontSize: '0.85rem', color: '#64748B' }}>
          Already have an account?{' '}
          <Link
            to="/login"
            style={{
              fontWeight: 600,
              color: '#0F172A',
              textDecoration: 'none',
            }}
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};

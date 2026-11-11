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
            style={{ width: '100%', marginTop: '6px' }}
          >
            Create Account & Get Started →
          </Button>
        </form>

        <div style={{ marginTop: '22px', textAlign: 'center', fontSize: '0.825rem', color: 'var(--color-muted)' }}>
          Already have an account?{' '}
          <Link
            to="/login"
            className="auth-link"
            style={{
              fontWeight: 600,
              color: 'var(--color-ink)',
              textDecoration: 'underline',
              textUnderlineOffset: '3px',
            }}
          >
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};

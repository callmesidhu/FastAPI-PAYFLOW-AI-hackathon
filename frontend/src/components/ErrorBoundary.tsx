import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public override state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public override componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('PAYFLOW AI caught UI boundary error:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public override render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'var(--color-bg, #FAF7F2)',
            padding: '24px',
          }}
        >
          <div
            style={{
              maxWidth: '480px',
              width: '100%',
              backgroundColor: 'var(--color-cream, #EDE6D6)',
              border: '1px solid var(--color-hairline, #3A342C)',
              borderRadius: '2px',
              padding: '32px',
            }}
          >
            <div
              style={{
                fontFamily: 'var(--font-serif, serif)',
                fontSize: '1.25rem',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
                marginBottom: '12px',
                color: 'var(--color-ink, #0B0B0B)',
              }}
            >
              System Notice
            </div>
            <p
              style={{
                color: 'var(--color-muted, #4A4036)',
                fontSize: '0.875rem',
                marginBottom: '20px',
                lineHeight: 1.6,
              }}
            >
              An unexpected interface disruption occurred. Data integrity has been maintained.
            </p>
            {this.state.error?.message && (
              <pre
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid rgba(58, 52, 44, 0.2)',
                  borderRadius: '2px',
                  padding: '12px',
                  fontSize: '0.75rem',
                  color: 'var(--color-overdue, #8C4A3F)',
                  overflowX: 'auto',
                  marginBottom: '24px',
                }}
              >
                {this.state.error.message}
              </pre>
            )}
            <button
              onClick={this.handleReset}
              style={{
                backgroundColor: 'var(--color-ink, #0B0B0B)',
                color: '#FAF7F2',
                padding: '10px 18px',
                border: 'none',
              }}
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

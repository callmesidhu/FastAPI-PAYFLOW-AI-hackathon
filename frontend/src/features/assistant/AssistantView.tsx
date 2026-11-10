import { useState, type FC, type FormEvent } from 'react';
import { Button, PageHeader, TextArea } from '../../components';

export const AssistantView: FC = () => {
  const [prompt, setPrompt] = useState('');
  const [conversation, setConversation] = useState<Array<{ role: 'user' | 'assistant'; content: string }>>([]);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;

    const userText = prompt.trim();
    setConversation((prev) => [...prev, { role: 'user', content: userText }]);
    setPrompt('');

    // Responsive assistant shell response
    setTimeout(() => {
      setConversation((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            "I'm your AI accounts receivable assistant. Once the AI tool-calling pipeline is connected in Milestone 4, I will parse your command, extract line items, match customers, and prepare a structured draft for your review.",
        },
      ]);
    }, 400);
  };

  return (
    <div>
      <PageHeader
        eyebrow="CONVERSATIONAL AR ASSISTANT"
        title="AI Assistant"
        subtitle="Issue natural-language billing instructions. The assistant prepares drafts but requires your authorization to send."
      />

      <div
        style={{
          backgroundColor: 'var(--color-cream)',
          border: 'var(--border-hairline)',
          borderRadius: 'var(--radius-sm)',
          padding: '24px',
          minHeight: '380px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          marginBottom: '20px',
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', overflowY: 'auto' }}>
          {conversation.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--color-muted)' }}>
              <div
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.25rem',
                  letterSpacing: 'var(--tracking-wide)',
                  color: 'var(--color-ink)',
                  marginBottom: '8px',
                }}
              >
                How may I assist your accounts receivable?
              </div>
              <p style={{ fontSize: '0.85rem', maxWidth: '480px', margin: '0 auto', lineHeight: 1.6 }}>
                Try: <em>"Create a $500 invoice for John Smith for website development, due in seven days."</em>
              </p>
            </div>
          ) : (
            conversation.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '80%',
                  padding: '14px 18px',
                  backgroundColor: msg.role === 'user' ? 'var(--color-ink)' : 'var(--color-bg)',
                  color: msg.role === 'user' ? 'var(--color-bg)' : 'var(--color-ink)',
                  border: msg.role === 'user' ? 'none' : 'var(--border-hairline)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.85rem',
                  lineHeight: 1.5,
                }}
              >
                {msg.content}
              </div>
            ))
          )}
        </div>

        <form onSubmit={handleSubmit} style={{ marginTop: '20px', display: 'flex', gap: '12px' }}>
          <div style={{ flex: 1 }}>
            <TextArea
              rows={2}
              placeholder="Give a natural language command (e.g. 'Draft an invoice for Acme Corp...')"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end' }}>
            <Button type="submit" variant="primary" size="md">
              SEND →
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

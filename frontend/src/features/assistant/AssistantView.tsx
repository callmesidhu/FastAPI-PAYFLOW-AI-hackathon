import { useState, useRef, useEffect, type FC, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../lib/api-client';
import { Button, FormattedMarkdown, PageHeader, StatusLabel, TextArea } from '../../components';

interface ToolCallRecord {
  name: string;
  arguments?: Record<string, unknown>;
  result?: Record<string, unknown>;
}

interface PreviewData {
  invoice_id?: string;
  invoice_number?: string;
  customer_name?: string;
  subtotal?: string;
  tax?: string;
  total?: string;
  currency?: string;
  due_date?: string;
  status?: string;
  message?: string;
  // Reminder fields
  days_overdue?: number;
  tone?: string;
  subject?: string;
  body?: string;
  preview_note?: string;
  // Summary fields
  by_currency?: Array<{
    currency: string;
    total_outstanding: string;
    total_overdue: string;
    collected_this_month: string;
    open_invoices_count: number;
    overdue_invoices_count: number;
  }>;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  clarification_needed?: boolean;
  tool_calls?: ToolCallRecord[];
  preview_data?: PreviewData | null;
}

interface AIChatResponse {
  conversation_id: string;
  message: string;
  tool_calls: ToolCallRecord[];
  clarification_needed: boolean;
  preview_data?: PreviewData | null;
}

const PROMPT_SUGGESTIONS = [
  'Draft an invoice for Acme Global for $1,500 USD for workshop due in 14 days',
  'Show me all overdue invoices',
  'What is my current receivables summary?',
  'Draft a polite reminder for invoice INV-2026-0001',
];

export const AssistantView: FC = () => {
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const chatMessagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messages.length === 0 && !loading) return;
    const container = chatMessagesRef.current;
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }
  }, [messages, loading]);

  const sendMessage = async (textToSend: string) => {
    const trimmed = textToSend.trim();
    if (!trimmed || loading) return;

    setError(null);
    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setPrompt('');
    setLoading(true);

    try {
      const response = await apiClient<AIChatResponse>('/api/ai/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: trimmed,
          conversation_id: conversationId,
        }),
      });

      setConversationId(response.conversation_id);

      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        clarification_needed: response.clarification_needed,
        tool_calls: response.tool_calls,
        preview_data: response.preview_data,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to reach AI assistant. Please try again.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendMessage(prompt);
  };

  const handleReset = () => {
    setConversationId(null);
    setMessages([]);
    setError(null);
  };

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto' }}>
      <PageHeader
        eyebrow="CONVERSATIONAL AR AGENT"
        title="AI Assistant"
        subtitle="Issue natural-language billing instructions. Authoritative calculations are made server-side, and no action sends without your approval."
        actions={
          messages.length > 0 ? (
            <Button variant="outline" size="sm" onClick={handleReset}>
              RESET THREAD
            </Button>
          ) : undefined
        }
      />

      {error && (
        <div
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--color-overdue-bg)',
            border: '1px solid var(--color-overdue)',
            color: 'var(--color-overdue)',
            fontSize: '0.85rem',
            marginBottom: '16px',
            borderRadius: 'var(--radius-sm)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '8px',
          }}
        >
          <span>{error}</span>
          <Button variant="outline" size="sm" onClick={() => setError(null)}>
            DISMISS
          </Button>
        </div>
      )}

      {/* Main Conversation Canvas */}
      <div
        className="payflow-chat-shell"
        style={{
          backgroundColor: 'var(--color-cream)',
          border: 'var(--border-hairline)',
          borderRadius: 'var(--radius-sm)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: '480px',
          maxHeight: '680px',
          marginBottom: '20px',
          overflow: 'hidden',
        }}
      >
        {/* Messages Body */}
        <div
          ref={chatMessagesRef}
          className="payflow-chat-messages"
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '24px',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {messages.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '48px 16px', color: 'var(--color-muted)' }}>
              <div
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: '1.35rem',
                  letterSpacing: 'var(--tracking-wide)',
                  color: 'var(--color-ink)',
                  marginBottom: '10px',
                  textTransform: 'uppercase',
                }}
              >
                Accounts Receivable Orchestrator
              </div>
              <p
                style={{
                  fontSize: '0.875rem',
                  maxWidth: '520px',
                  margin: '0 auto 24px auto',
                  lineHeight: 1.6,
                }}
              >
                Draft authoritative invoices, query outstanding balances, or draft payment reminders through natural language.
                Every write action prepares a draft and enforces user ownership.
              </p>

              <div style={{ maxWidth: '640px', margin: '0 auto', textAlign: 'left' }}>
                <div
                  style={{
                    fontSize: '0.7rem',
                    textTransform: 'uppercase',
                    letterSpacing: 'var(--tracking-widest)',
                    color: 'var(--color-muted)',
                    marginBottom: '10px',
                    fontWeight: 600,
                  }}
                >
                  Suggested Prompts
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {PROMPT_SUGGESTIONS.map((suggestion, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => sendMessage(suggestion)}
                      style={{
                        padding: '10px 14px',
                        backgroundColor: 'var(--color-bg)',
                        border: 'var(--border-hairline)',
                        borderRadius: 'var(--radius-sm)',
                        textAlign: 'left',
                        cursor: 'pointer',
                        fontSize: '0.825rem',
                        color: 'var(--color-ink)',
                        fontFamily: 'var(--font-sans)',
                        transition: 'background-color 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--color-sand)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--color-bg)';
                      }}
                    >
                      → {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                className="payflow-chat-bubble"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: msg.role === 'user' ? '75%' : '88%',
                }}
              >
                {/* Role and Timestamp Metadata */}
                <div
                  style={{
                    fontSize: '0.65rem',
                    letterSpacing: 'var(--tracking-wider)',
                    textTransform: 'uppercase',
                    color: 'var(--color-muted)',
                    marginBottom: '4px',
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    display: 'flex',
                    gap: '8px',
                  }}
                >
                  <span>{msg.role === 'user' ? 'YOU' : 'AR ASSISTANT'}</span>
                  <span>•</span>
                  <span>{msg.timestamp}</span>
                </div>

                {/* Message Bubble */}
                <div
                  style={{
                    padding: '16px 20px',
                    backgroundColor: msg.role === 'user' ? 'var(--color-ink)' : 'var(--color-bg)',
                    color: msg.role === 'user' ? 'var(--color-bg)' : 'var(--color-ink)',
                    border: msg.role === 'user' ? '1px solid var(--color-ink)' : 'var(--border-hairline)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.875rem',
                    lineHeight: 1.6,
                    whiteSpace: msg.role === 'user' ? 'pre-wrap' : undefined,
                  }}
                >
                  {msg.role === 'user' ? (
                    msg.content
                  ) : (
                    <FormattedMarkdown content={msg.content} />
                  )}

                  {/* Clarification Notice */}
                  {msg.clarification_needed && (
                    <div
                      style={{
                        marginTop: '12px',
                        padding: '10px 14px',
                        backgroundColor: 'var(--color-sand)',
                        borderLeft: '3px solid var(--color-pending)',
                        fontSize: '0.8rem',
                        color: 'var(--color-ink)',
                      }}
                    >
                      <strong style={{ textTransform: 'uppercase', letterSpacing: 'var(--tracking-wide)' }}>
                        Clarification Required:
                      </strong>{' '}
                      Please specify the missing parameters to proceed safely without assumptions.
                    </div>
                  )}

                  {/* Structured Invoice Draft Preview */}
                  {msg.preview_data && (msg.preview_data.invoice_number || msg.preview_data.total) && (
                    <div
                      style={{
                        marginTop: '16px',
                        padding: '16px',
                        backgroundColor: 'var(--color-cream)',
                        border: 'var(--border-hairline)',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: '12px',
                          borderBottom: 'var(--border-hairline)',
                          paddingBottom: '8px',
                        }}
                      >
                        <div>
                          <div
                            style={{
                              fontSize: '0.65rem',
                              letterSpacing: 'var(--tracking-widest)',
                              textTransform: 'uppercase',
                              color: msg.preview_data.invoice_id ? 'var(--color-muted)' : 'var(--color-pending)',
                              fontWeight: 600,
                            }}
                          >
                            {msg.preview_data.invoice_id ? 'AUTHORITATIVE SAVED DRAFT' : '✦ AI SUGGESTION (UNCONFIRMED)'}
                          </div>
                          <div
                            style={{
                              fontFamily: 'var(--font-serif)',
                              fontSize: '1.1rem',
                              color: 'var(--color-ink)',
                            }}
                          >
                            {msg.preview_data.invoice_number || 'Draft Preview'}
                          </div>
                        </div>
                        <StatusLabel
                          status={msg.preview_data.invoice_id ? (msg.preview_data.status || 'draft') : 'draft'}
                          label={msg.preview_data.invoice_id ? undefined : 'AI SUGGESTION'}
                          size="sm"
                        />
                      </div>

                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                          gap: '12px',
                          fontSize: '0.8rem',
                          marginBottom: '16px',
                        }}
                      >
                        <div>
                          <div style={{ color: 'var(--color-muted)', fontSize: '0.7rem' }}>CUSTOMER</div>
                          <div style={{ fontWeight: 600 }}>{msg.preview_data.customer_name || 'Client'}</div>
                        </div>
                        <div>
                          <div style={{ color: 'var(--color-muted)', fontSize: '0.7rem' }}>TOTAL AMOUNT</div>
                          <div style={{ fontWeight: 700, fontFamily: 'var(--font-serif)' }}>
                            ${msg.preview_data.total} {msg.preview_data.currency || 'USD'}
                          </div>
                        </div>
                        <div>
                          <div style={{ color: 'var(--color-muted)', fontSize: '0.7rem' }}>DUE DATE</div>
                          <div>{msg.preview_data.due_date || 'In 14 days'}</div>
                        </div>
                      </div>

                      <div
                        style={{
                          padding: '10px 14px',
                          backgroundColor: 'var(--color-sand)',
                          borderLeft: '3px solid var(--color-ink)',
                          fontSize: '0.75rem',
                          color: 'var(--color-ink)',
                          marginBottom: '16px',
                          lineHeight: 1.5,
                        }}
                      >
                        <span style={{ fontWeight: 700, letterSpacing: 'var(--tracking-wide)', textTransform: 'uppercase' }}>
                          MANDATORY NOTICE:
                        </span>{' '}
                        This will create and send invoice {msg.preview_data.invoice_number || ''} through PayPal Sandbox after approval.
                        No funds or live invoices are moved without your explicit authorization.
                      </div>

                      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                        {msg.preview_data.invoice_id ? (
                          <>
                            <Button
                              variant="primary"
                              size="sm"
                              onClick={() => navigate(`/invoices/${msg.preview_data?.invoice_id}`)}
                            >
                              EDIT & SUBMIT FOR APPROVAL →
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => navigate('/invoices')}
                            >
                              ALL INVOICES
                            </Button>
                          </>
                        ) : (
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => navigate('/invoices/new')}
                          >
                            EDIT & CONFIRM INVOICE DRAFT →
                          </Button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Structured Reminder Draft Preview */}
                  {msg.preview_data && msg.preview_data.subject && (
                    <div
                      style={{
                        marginTop: '16px',
                        padding: '16px',
                        backgroundColor: 'var(--color-cream)',
                        border: 'var(--border-hairline)',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      <div
                        style={{
                          fontSize: '0.65rem',
                          letterSpacing: 'var(--tracking-widest)',
                          textTransform: 'uppercase',
                          color: 'var(--color-muted)',
                          marginBottom: '6px',
                        }}
                      >
                        REMINDER DRAFT (NOT SENT)
                      </div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '8px' }}>
                        Subject: {msg.preview_data.subject}
                      </div>
                      <div
                        style={{
                          padding: '10px',
                          backgroundColor: 'var(--color-bg)',
                          border: 'var(--border-hairline)',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '0.8rem',
                          fontFamily: 'monospace',
                          whiteSpace: 'pre-wrap',
                          marginBottom: '10px',
                        }}
                      >
                        {msg.preview_data.body}
                      </div>
                      <div
                        style={{
                          fontSize: '0.725rem',
                          color: 'var(--color-pending)',
                          letterSpacing: 'var(--tracking-wide)',
                          textTransform: 'uppercase',
                          fontWeight: 600,
                        }}
                      >
                        ⚠ {msg.preview_data.preview_note || 'Human authorization required before dispatch.'}
                      </div>
                    </div>
                  )}

                  {/* Structured Receivables Summary Breakdown */}
                  {msg.preview_data && msg.preview_data.by_currency && msg.preview_data.by_currency.length > 0 && (
                    <div
                      style={{
                        marginTop: '16px',
                        padding: '16px',
                        backgroundColor: 'var(--color-cream)',
                        border: 'var(--border-hairline)',
                        borderRadius: 'var(--radius-sm)',
                      }}
                    >
                      <div
                        style={{
                          fontSize: '0.65rem',
                          letterSpacing: 'var(--tracking-widest)',
                          textTransform: 'uppercase',
                          color: 'var(--color-muted)',
                          marginBottom: '10px',
                        }}
                      >
                        RECEIVABLES PORTFOLIO BREAKDOWN
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {msg.preview_data.by_currency.map((curr, cIdx) => (
                          <div
                            key={cIdx}
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              flexWrap: 'wrap',
                              gap: '8px',
                              padding: '8px 12px',
                              backgroundColor: 'var(--color-bg)',
                              border: 'var(--border-hairline)',
                              borderRadius: 'var(--radius-sm)',
                              fontSize: '0.8rem',
                            }}
                          >
                            <span style={{ fontWeight: 700 }}>{curr.currency}</span>
                            <span>Outstanding: <strong>${curr.total_outstanding}</strong></span>
                            <span>Overdue: <strong style={{ color: 'var(--color-overdue)' }}>${curr.total_overdue}</strong></span>
                            <span>Invoices: <strong>{curr.open_invoices_count}</strong></span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}

          {loading && (
            <div
              style={{
                alignSelf: 'flex-start',
                padding: '14px 20px',
                backgroundColor: 'var(--color-bg)',
                border: 'var(--border-hairline)',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.825rem',
                color: 'var(--color-muted)',
                fontStyle: 'italic',
                letterSpacing: 'var(--tracking-wide)',
              }}
            >
              Consulting authoritative accounts receivable ledger...
            </div>
          )}
        </div>

        {/* Input Form */}
        <form
          onSubmit={handleSubmit}
          className="payflow-chat-form"
          style={{
            padding: '16px 20px',
            backgroundColor: 'var(--color-bg)',
            borderTop: 'var(--border-hairline)',
            display: 'flex',
            gap: '12px',
            alignItems: 'flex-end',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ flex: '1 1 220px', minWidth: 0 }}>
            <TextArea
              rows={2}
              placeholder="Enter a billing instruction (e.g. 'Draft an invoice for Acme Global for $1,200 USD due in 14 days')"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage(prompt);
                }
              }}
            />
          </div>
          <div>
            <Button
              type="submit"
              variant="primary"
              size="md"
              disabled={loading || !prompt.trim()}
            >
              {loading ? 'THINKING...' : 'DISPATCH →'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

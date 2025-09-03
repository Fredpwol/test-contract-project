import React from 'react'

export function ChatInput({
  input,
  isSending,
  error,
  onChange,
  onSend,
  onAbort,
  canAbort,
}: {
  input: string
  isSending: boolean
  error: string | null
  onChange: (v: string) => void
  onSend: (e?: React.FormEvent) => void
  onAbort: () => void
  canAbort: boolean
}) {
  return (
    <form className="chat-input" onSubmit={onSend}>
      <textarea
        className="textarea"
        rows={2}
        value={input}
        onChange={(e) => onChange(e.target.value)}
        placeholder="What do you want to generate or change?"
        disabled={isSending}
      />
      <div className="row">
        <button type="submit" className="button primary" disabled={isSending || !input.trim()}>
          {isSending ? 'Sending…' : 'Send'}
        </button>
        <button type="button" className="button" disabled={!canAbort} onClick={onAbort}>Abort</button>
      </div>
      {error && <div className="error">{error}</div>}
    </form>
  )
}



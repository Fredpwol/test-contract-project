import React, { useEffect, useRef } from 'react'

export type ChatMsg = { id: string; role: 'user' | 'assistant'; content: string }

export function ChatMessages({ messages }: { messages: ChatMsg[] }) {
  const listRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    if (!listRef.current) return
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages])
  return (
    <div className="chat-messages" ref={listRef}>
      {messages.length === 0 && (
        <div className="placeholder">Ask for Terms of Service. For example: “Draft ToS for a New York cloud cybersecurity SaaS.”</div>
      )}
      {messages.map((m) => (
        <div key={m.id} className={`message ${m.role}`}>
          {m.role === 'assistant' ? (
            <div className="assistant-placeholder">Document updated — see preview →</div>
          ) : (
            <div className="bubble">{m.content}</div>
          )}
        </div>
      ))}
    </div>
  )
}



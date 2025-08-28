import { useCallback, useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import './App.css'

type ChatMsg = { id: string; role: 'user' | 'assistant'; content: string }
type SessionItem = { session_id: string; created_at?: string; document_title?: string; document_html?: string }

function App() {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('Draft terms of service for a cloud cyber SaaS company based in New York')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const listRef = useRef<HTMLDivElement | null>(null)
  const previewRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!listRef.current) return
    listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages])

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true)
    try {
      const resp = await fetch('/api/session/list')
      if (!resp.ok) return
      const data = await resp.json()
      const items: SessionItem[] = Array.isArray(data?.sessions) ? data.sessions : []
      setSessions(items)
    } finally {
      setIsLoadingSessions(false)
    }
  }, [])

  useEffect(() => {
    loadSessions().catch(() => {})
  }, [loadSessions])

  const ensureSession = useCallback(async (): Promise<string> => {
    if (sessionId) return sessionId
    const resp = await fetch('/api/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!resp.ok) {
      const t = await resp.text().catch(() => '')
      throw new Error(t || `Failed to start session (${resp.status})`)
    }
    const data: any = await resp.json().catch(() => ({}))
    const sid: string | undefined = data?.session_id
    if (!sid) throw new Error('Server did not return session_id')
    setSessionId(sid)
    loadSessions().catch(() => {})
    return sid
  }, [sessionId, loadSessions])

  const lastAssistantHtml = useCallback(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant' && messages[i].content) return messages[i].content
    }
    return ''
  }, [messages])

  const unescapeJsonString = useCallback((s: string): string => {
    try {
      const quoted = '"' + s.replace(/\\/g, '\\\\').replace(/\"/g, '\\"') + '"'
      return JSON.parse(quoted)
    } catch {
      return s
        .replace(/\\\"/g, '"')
        .replace(/\\\\/g, '\\')
        .replace(/\\n/g, '\n')
    }
  }, [])

  const onAbort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const onNewSession = useCallback(async () => {
    setSessionId(null)
    setMessages([])
    try {
      const sid = await ensureSession()
      setSessionId(sid)
    } catch {}
  }, [ensureSession])

  const onSelectSession = useCallback((sid: string) => {
    setSessionId(sid)
    const item = sessions.find(s => s.session_id === sid)
    const md = item?.document_html || ''
    if (md) {
      setMessages([{ id: crypto.randomUUID(), role: 'assistant', content: md }])
    } else {
      setMessages([])
    }
  }, [sessions])

  const onSend = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault()
    const text = input.trim()
    if (!text) return
    setError(null)
    setIsSending(true)
    const userMsg: ChatMsg = { id: crypto.randomUUID(), role: 'user', content: text }
    const assistantMsg: ChatMsg = { id: crypto.randomUUID(), role: 'assistant', content: '' }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')

    const controller = new AbortController()
    abortRef.current = controller
    try {
      const sid = await ensureSession()
      if (!sid) throw new Error('No session available')
      const base = lastAssistantHtml()
      if (base) {
        await fetch(`/api/session/${sid}/document`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ html: base }),
        })
      }

      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid, message: { role: 'user', content: text } }),
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) {
        const t = await resp.text().catch(() => '')
        throw new Error(t || `Request failed with ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buf = ''
      let started = false
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        buf += chunk
        if (!started) {
          const idx = buf.indexOf('\"data\":\"')
          if (idx >= 0) {
            buf = buf.slice(idx + 8)
            started = true
          } else {
            continue
          }
        }
        const display = buf.replace(/\"\}\s*$/, '')
        const unescaped = unescapeJsonString(display)
        setMessages((prev) => {
          const next = [...prev]
          for (let i = next.length - 1; i >= 0; i--) {
            if (next[i].role === 'assistant') { next[i] = { ...next[i], content: unescaped }; break }
          }
          return next
        })
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        setError('Request aborted')
      } else {
        setError(err?.message || 'Unexpected error')
      }
    } finally {
      setIsSending(false)
      abortRef.current = null
    }
  }, [input, ensureSession, unescapeJsonString, lastAssistantHtml])

  const copyHtml = useCallback(async (md: string) => {
    try { await navigator.clipboard.writeText(md) } catch {}
  }, [])

  const downloadHtml = useCallback((md: string) => {
    const blob = new Blob([md], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'terms-of-service.md'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }, [])

  const latestMd = lastAssistantHtml()
  const latestRendered = latestMd ? marked.parse(latestMd) as string : ''

  useEffect(() => {
    if (!previewRef.current) return
    previewRef.current.scrollTop = previewRef.current.scrollHeight
  }, [latestRendered])

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>AI Contract Generator</h1>
      </header>
      <main className="chat-main three-col">
        <aside className="sessions">
          <div className="sessions-header">
            <div className="title">Sessions</div>
            <div className="row">
              <button className="button" onClick={() => loadSessions()} disabled={isLoadingSessions}>Refresh</button>
              <button className="button primary" onClick={onNewSession}>New</button>
            </div>
          </div>
          <div className="sessions-list">
            {sessions.length === 0 && <div className="placeholder">No sessions yet.</div>}
            {sessions.map((s) => (
              <div
                key={s.session_id}
                className={`session-item${sessionId === s.session_id ? ' active' : ''}`}
                onClick={() => onSelectSession(s.session_id)}
              >
                <div className="session-title">{s.document_title || 'Untitled'}</div>
                <div className="session-sub">{(s.created_at || '').replace('T', ' ').replace('Z','')}</div>
              </div>
            ))}
          </div>
        </aside>
        <div className="chat-panel">
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
          <form className="chat-input" onSubmit={onSend}>
            <textarea
              className="textarea"
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="What do you want to generate or change?"
              disabled={isSending}
            />
            <div className="row">
              <button type="submit" className="button primary" disabled={isSending || !input.trim()}>
                {isSending ? 'Sending…' : 'Send'}
              </button>
              <button type="button" className="button" disabled={!abortRef.current} onClick={onAbort}>Abort</button>
            </div>
            {error && <div className="error">{error}</div>}
          </form>
        </div>
        <section className="viewer" ref={previewRef}>
          {latestMd ? (
            <>
              <div className="row" style={{ padding: '10px' }}>
                <button className="button" onClick={() => copyHtml(latestMd)}>Copy .md</button>
                <button className="button" onClick={() => downloadHtml(latestMd)}>Download .md</button>
              </div>
              <div className="doc" dangerouslySetInnerHTML={{ __html: latestRendered }} />
            </>
          ) : (
            <div className="placeholder">Document preview will appear here.</div>
          )}
        </section>
      </main>
      <footer className="app-footer">
        <span>For demonstration only. Not legal advice.</span>
      </footer>
    </div>
  )
}

export default App

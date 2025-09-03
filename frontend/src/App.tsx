import { useCallback, useEffect, useRef, useState } from 'react'
import { marked } from 'marked'
import './App.css'
import { SessionsList, type SessionItem } from './components/SessionsList'
import { ChatMessages, type ChatMsg } from './components/ChatMessages'
import { ChatInput } from './components/ChatInput'
import { Viewer, extractTitleFromMarkdown } from './components/Viewer'

function App() {
  const API_BASE = (import.meta as any)?.env?.VITE_API_BASE_URL?.replace(/\/$/, '') || ''
  const api = useCallback((path: string) => `${API_BASE}${path}` as string, [API_BASE])
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('Draft terms of service for a cloud cyber SaaS company based in New York')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [isLoadingSessions, setIsLoadingSessions] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  // kept for backward compatibility; Viewer now manages its own scrolling
  // const previewRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    // keep document title in sync with latest doc
    const latest = lastAssistantHtml()
    const title = extractTitleFromMarkdown(latest) || 'AI Contract Generator'
    if (document.title !== title) document.title = title
  }, [messages])

  const loadSessions = useCallback(async () => {
    setIsLoadingSessions(true)
    try {
      const resp = await fetch(api('/api/session/list'))
      if (!resp.ok) return
      const data = await resp.json()
      const items: SessionItem[] = Array.isArray(data?.sessions) ? data.sessions : []
      setSessions(items)
    } finally {
      setIsLoadingSessions(false)
    }
  }, [api])

  useEffect(() => {
    loadSessions().catch(() => {})
  }, [loadSessions])

  const ensureSession = useCallback(async (forceNew: boolean = false): Promise<string> => {
    if (!forceNew && sessionId) return sessionId
    const resp = await fetch(api('/api/session/start'), {
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
  }, [sessionId, loadSessions, api])

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
      const sid = await ensureSession(true)
      setSessionId(sid)
    } catch {}
  }, [ensureSession])

  const onSelectSession = useCallback(async (sid: string) => {
    setSessionId(sid)
    try {
      const resp = await fetch(api(`/api/session/${sid}/history`))
      if (resp.ok) {
        const data: any = await resp.json().catch(() => ({}))
        const normalizeRole = (r: string): 'user' | 'assistant' => (r === 'human' || r === 'user') ? 'user' : 'assistant'
        const msgs = Array.isArray(data?.messages) ? data.messages : []
        const mapped = msgs.map((m: any) => ({ id: crypto.randomUUID(), role: normalizeRole(m?.role || ''), content: String(m?.content || '') }))
        if (mapped.length > 0) {
          setMessages(mapped)
          return
        }
        const md = data?.meta?.document_html || sessions.find(s => s.session_id === sid)?.document_html || ''
        if (md) {
          setMessages([{ id: crypto.randomUUID(), role: 'assistant', content: md }])
          return
        }
      }
    } catch {}
    const item = sessions.find(s => s.session_id === sid)
    const md = item?.document_html || ''
    if (md) {
      setMessages([{ id: crypto.randomUUID(), role: 'assistant', content: md }])
    } else {
      setMessages([])
    }
  }, [sessions, api])

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
        await fetch(api(`/api/session/${sid}/document`), {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ html: base }),
        })
      }

      const resp = await fetch(api('/api/chat'), {
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

  const downloadAsHtml = useCallback((md: string) => {
    const htmlBody = (marked.parse(md) as string) || ''
    const full = `<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><title>Terms of Service</title><style>body{font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; color:#0b1020; line-height:1.5; padding:24px;} a{color:#0ea5e9;} table{border-collapse:collapse;width:100%;} table,th,td{border:1px solid #cbd5e1;} th,td{padding:8px;} h1,h2,h3{margin-top:1.2em;}</style></head><body>${htmlBody}</body></html>`
    const blob = new Blob([full], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'terms-of-service.html'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }, [])

  const latestMd = lastAssistantHtml()
  const latestRendered = latestMd ? marked.parse(latestMd) as string : ''

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>AI Contract Generator</h1>
      </header>
      <main className="chat-main three-col">
        <SessionsList
          sessions={sessions}
          activeSessionId={sessionId}
          isLoading={isLoadingSessions}
          onRefresh={() => loadSessions()}
          onNew={onNewSession}
          onSelect={onSelectSession}
          onRename={async (sid, title) => {
            try {
              await fetch(api(`/api/session/${sid}/title`), {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title }),
              })
              await loadSessions()
            } catch {}
          }}
        />
        <div className="chat-panel">
          <ChatMessages messages={messages} />
          <ChatInput
            input={input}
            isSending={isSending}
            error={error}
            onChange={setInput}
            onSend={onSend}
            onAbort={onAbort}
            canAbort={!!abortRef.current}
          />
        </div>
        <Viewer
          markdown={latestMd}
          renderedHtml={latestRendered}
          onCopy={copyHtml}
          onDownloadMd={downloadHtml}
          onDownloadHtml={downloadAsHtml}
          documentTitle={sessions.find(s => s.session_id === sessionId)?.document_title}
        />
      </main>
      <footer className="app-footer">
        <span>For demonstration only. Not legal advice.</span>
      </footer>
    </div>
  )
}

export default App

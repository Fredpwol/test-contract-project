import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

type GenerateBody = {
  prompt: string
  company_name?: string
  jurisdiction?: string
  tone?: string
}

function App() {
  const [prompt, setPrompt] = useState('Draft terms of service for a cloud cyber SaaS company based in New York')
  const [companyName, setCompanyName] = useState('')
  const [jurisdiction, setJurisdiction] = useState('New York, USA')
  const [tone, setTone] = useState('Formal, clear, conservative risk posture')
  const [html, setHtml] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const viewerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!viewerRef.current) return
    viewerRef.current.scrollTop = viewerRef.current.scrollHeight
  }, [html])

  const onAbort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const buildBody = useCallback((): GenerateBody => {
    const body: GenerateBody = { prompt: prompt.trim() }
    if (companyName.trim()) body.company_name = companyName.trim()
    if (jurisdiction.trim()) body.jurisdiction = jurisdiction.trim()
    if (tone.trim()) body.tone = tone.trim()
    return body
  }, [prompt, companyName, jurisdiction, tone])

  const onSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setHtml('')
    setIsLoading(true)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const resp = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildBody()),
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) {
        const text = await resp.text().catch(() => '')
        throw new Error(text || `Request failed with ${resp.status}`)
      }

      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        setHtml((prev) => prev + chunk)
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        setError('Generation aborted')
      } else {
        setError(err?.message || 'Unexpected error')
      }
    } finally {
      setIsLoading(false)
      abortRef.current = null
    }
  }, [buildBody])

  const onCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(html)
    } catch {}
  }, [html])

  const onDownload = useCallback(() => {
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'terms-of-service.html'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }, [html])

  const isAbortable = useMemo(() => isLoading && !!abortRef.current, [isLoading])

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>AI Contract Generator</h1>
      </header>
      <main className="app-main">
        <aside className="sidebar">
          <form onSubmit={onSubmit} className="form">
            <label className="label">Business context and request</label>
            <textarea
              className="textarea"
              rows={6}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe your business and request (e.g., Draft terms of service for a cloud cyber SaaS company based in New York)"
              required
            />
            <label className="label">Company name (optional)</label>
            <input className="input" value={companyName} onChange={(e) => setCompanyName(e.target.value)} placeholder="Acme Security, Inc." />
            <label className="label">Jurisdiction (optional)</label>
            <input className="input" value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)} placeholder="New York, USA" />
            <label className="label">Tone (optional)</label>
            <input className="input" value={tone} onChange={(e) => setTone(e.target.value)} placeholder="Formal, clear, conservative risk posture" />
            <div className="row">
              <button type="submit" className="button primary" disabled={isLoading}>
                {isLoading ? 'Generating…' : 'Generate Terms'}
              </button>
              <button type="button" className="button" disabled={!isAbortable} onClick={onAbort}>
                Abort
              </button>
            </div>
            {error && <div className="error">{error}</div>}
            <div className="row">
              <button type="button" className="button" onClick={onCopy} disabled={!html}>
                Copy HTML
              </button>
              <button type="button" className="button" onClick={onDownload} disabled={!html}>
                Download .html
              </button>
            </div>
          </form>
        </aside>
        <section className="viewer" ref={viewerRef}>
          {html ? (
            <div className="doc" dangerouslySetInnerHTML={{ __html: html }} />
          ) : (
            <div className="placeholder">The generated Terms of Service will appear here.</div>
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

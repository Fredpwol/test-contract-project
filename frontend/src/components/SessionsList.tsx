import { useEffect, useRef, useState } from 'react'

export type SessionItem = { session_id: string; created_at?: string; document_title?: string; document_html?: string }

export function formatDateTime(value?: string): string {
  if (!value) return ''
  try {
    const d = new Date(value)
    if (isNaN(d.getTime())) return value.replace('T', ' ').replace('Z', '')
    return new Intl.DateTimeFormat(undefined, {
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    }).format(d)
  } catch {
    return value
  }
}

export function SessionsList({
  sessions,
  activeSessionId,
  isLoading,
  onRefresh,
  onNew,
  onSelect,
  onRename,
}: {
  sessions: SessionItem[]
  activeSessionId: string | null
  isLoading: boolean
  onRefresh: () => void
  onNew: () => void
  onSelect: (sid: string) => void
  onRename: (sid: string, title: string) => void
}) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState<string>("")
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [editingId])

  const startEdit = (sid: string, current: string) => {
    setEditingId(sid)
    setEditValue(current || "")
  }

  const commitEdit = async (sid: string) => {
    const title = editValue.trim()
    setEditingId(null)
    if (!title) return
    try {
      await onRename(sid, title)
    } catch {}
  }

  const cancelEdit = () => {
    setEditingId(null)
  }

  return (
    <aside className="sessions">
      <div className="sessions-header">
        <div className="title">Sessions</div>
        <div className="row">
          <button className="button" onClick={onRefresh} disabled={isLoading}>Refresh</button>
          <button className="button primary" onClick={onNew}>New</button>
        </div>
      </div>
      <div className="sessions-list">
        {sessions.length === 0 && <div className="placeholder">No sessions yet.</div>}
        {sessions.map((s) => (
          <div
            key={s.session_id}
            className={`session-item${activeSessionId === s.session_id ? ' active' : ''}`}
            onClick={() => onSelect(s.session_id)}
          >
            <div className="session-title" onClick={(e) => e.stopPropagation()}>
              {editingId === s.session_id ? (
                <input
                  ref={inputRef}
                  className="input"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={() => commitEdit(s.session_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') commitEdit(s.session_id)
                    if (e.key === 'Escape') cancelEdit()
                  }}
                />
              ) : (
                <span style={{ cursor: 'text' }} onClick={() => startEdit(s.session_id, s.document_title || 'Untitled')}>
                  {s.document_title || 'Untitled'}
                </span>
              )}
            </div>
            <div className="session-sub">{formatDateTime(s.created_at)}</div>
          </div>
        ))}
      </div>
    </aside>
  )
}



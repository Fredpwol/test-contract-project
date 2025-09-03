import  { useEffect, useRef } from 'react'

export function extractTitleFromMarkdown(md: string): string | null {
  const m = md.match(/^#\s+(.+)$/m)
  return m ? m[1].trim() : null
}

export function Viewer({
  markdown,
  renderedHtml,
  onCopy,
  onDownloadMd,
  onDownloadHtml,
  documentTitle,
}: {
  markdown: string
  renderedHtml: string
  onCopy: (md: string) => void
  onDownloadMd: (md: string) => void
  onDownloadHtml: (md: string) => void
  documentTitle?: string | null
}) {
  const previewRef = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (!previewRef.current) return
    previewRef.current.scrollTop = previewRef.current.scrollHeight
  }, [renderedHtml])

  useEffect(() => {
    const nextTitle = documentTitle || extractTitleFromMarkdown(markdown) || 'AI Contract Generator'
    if (document.title !== nextTitle) document.title = nextTitle
  }, [markdown, documentTitle])

  return (
    <section className="viewer" ref={previewRef as any}>
      {markdown ? (
        <>
          <div className="row" style={{ padding: '10px' }}>
            <button className="button" onClick={() => onCopy(markdown)}>Copy .md</button>
            <button className="button" onClick={() => onDownloadMd(markdown)}>Download .md</button>
            <button className="button" onClick={() => onDownloadHtml(markdown)}>Download .html</button>
          </div>
          <div className="doc" dangerouslySetInnerHTML={{ __html: renderedHtml }} />
        </>
      ) : (
        <div className="placeholder">Document preview will appear here.</div>
      )}
    </section>
  )
}



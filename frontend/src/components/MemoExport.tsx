/**
 * MemoExport — PDF, Markdown, and shareable link export for investment memos.
 * Uses jsPDF for client-side PDF generation (no server dependency).
 */
import { useState } from 'react'
import { Download, FileText, Copy } from 'lucide-react'
import jsPDF from 'jspdf'

interface MemoExportProps {
  memoContent: string   // Markdown text
  companyName: string
  memoId?: string
}

export default function MemoExport({ memoContent, companyName, memoId }: MemoExportProps) {
  const [copied, setCopied] = useState(false)

  const handleDownloadPDF = () => {
    const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
    const pageWidth = doc.internal.pageSize.getWidth()
    const margin = 20
    const maxWidth = pageWidth - margin * 2
    let y = margin

    // Strip markdown formatting for plain PDF text
    const lines = memoContent
      .replace(/^#{1,3} /gm, '')   // headings
      .replace(/\*\*(.*?)\*\*/g, '$1')  // bold
      .replace(/\*(.*?)\*/g, '$1')  // italic
      .replace(/^---$/gm, '')  // horizontal rules
      .split('\n')

    doc.setFontSize(10)

    for (const rawLine of lines) {
      const line = rawLine.trim()
      if (!line) {
        y += 4
        continue
      }

      const wrapped = doc.splitTextToSize(line, maxWidth)
      for (const segment of wrapped) {
        if (y > doc.internal.pageSize.getHeight() - margin) {
          doc.addPage()
          y = margin
        }
        doc.text(segment, margin, y)
        y += 6
      }
    }

    const filename = `${companyName.replace(/\s+/g, '-').toLowerCase()}-investment-memo.pdf`
    doc.save(filename)
  }

  const handleDownloadMarkdown = () => {
    const blob = new Blob([memoContent], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${companyName.replace(/\s+/g, '-').toLowerCase()}-memo.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleCopyLink = () => {
    const link = memoId
      ? `${window.location.origin}/memo/${memoId}`
      : window.location.href
    navigator.clipboard.writeText(link).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={handleDownloadPDF}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-accent/10 hover:bg-accent/20 text-accent border border-accent/30 rounded transition-colors"
        title="Download as PDF"
      >
        <FileText size={12} />
        PDF
      </button>
      <button
        onClick={handleDownloadMarkdown}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-600 rounded transition-colors"
        title="Download as Markdown"
      >
        <Download size={12} />
        .md
      </button>
      <button
        onClick={handleCopyLink}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-600 rounded transition-colors"
        title="Copy shareable link"
      >
        <Copy size={12} />
        {copied ? 'Copied!' : 'Link'}
      </button>
    </div>
  )
}

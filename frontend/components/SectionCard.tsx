"use client"
import { Section, Narrative } from "@/types/blog"
import { RefreshCw, ChevronDown, ChevronUp, ImageIcon } from "lucide-react"
import { useState } from "react"

interface Props {
  section: Section
  index: number
  topic: string
  audience: string
  narrative: Narrative
  references: { id: number; url: string; title: string }[]
  onRegenerate: (index: number, newSection: Section) => void
}

export default function SectionCard({ section, index, topic, audience, narrative, references, onRegenerate }: Props) {
  const [expanded, setExpanded] = useState(true)
  const [regenerating, setRegenerating] = useState(false)

  async function handleRegenerate() {
    setRegenerating(true)
    try {
      const res = await fetch("http://localhost:8000/regenerate-section", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, audience, sectionTitle: section.sectionTitle, narrative }),
      })
      const newSection = await res.json()
      onRegenerate(index, newSection)
    } finally {
      setRegenerating(false)
    }
  }

  const scoreColor = section.humanScore >= 0.7 ? "text-green-400" : section.humanScore >= 0.4 ? "text-yellow-400" : "text-red-400"

  return (
    <div className="border border-gray-800 rounded-xl overflow-hidden bg-gray-950">
      <div className="flex items-center justify-between px-5 py-3 bg-gray-900 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-center gap-3">
          <span className="text-gray-500 text-xs font-mono">#{index + 1}</span>
          <h3 className="text-white font-semibold text-sm">{section.sectionTitle}</h3>
          <span className={`text-xs font-mono ${scoreColor}`}>
            {Math.round(section.humanScore * 100)}% human
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); handleRegenerate() }}
            disabled={regenerating}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-orange-400 transition-colors px-2 py-1 rounded border border-gray-700 hover:border-orange-500"
          >
            <RefreshCw className={`w-3 h-3 ${regenerating ? "animate-spin" : ""}`} />
            {regenerating ? "Regenerating..." : "Regenerate"}
          </button>
          {expanded ? <ChevronUp className="w-4 h-4 text-gray-500" /> : <ChevronDown className="w-4 h-4 text-gray-500" />}
        </div>
      </div>

      {expanded && (
        <div className="px-5 py-4 space-y-4">
          <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">{section.content}</p>

          {section.image?.required && (
            <div className="flex items-start gap-3 bg-gray-900 rounded-lg p-3 border border-gray-800">
              <ImageIcon className="w-4 h-4 text-orange-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-gray-500 mb-1">Image Suggestion</p>
                <p className="text-sm text-gray-300">{section.image.prompt}</p>
                <p className="text-xs text-gray-500 mt-1 italic">{section.image.caption}</p>
              </div>
            </div>
          )}

          {references.length > 0 && (
            <div className="border-t border-gray-800 pt-3">
              <p className="text-xs text-gray-500 mb-2 uppercase tracking-widest">References</p>
              <ul className="space-y-1">
                {references.map((ref) => (
                  <li key={ref.id} className="flex items-start gap-2">
                    <span className="text-gray-600 text-xs font-mono mt-0.5">[{ref.id}]</span>
                    <a href={ref.url} target="_blank" rel="noreferrer" className="text-xs text-orange-400 hover:underline break-all">
                      {ref.title || ref.url}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

"use client"
import { Section, Narrative } from "@/types/blog"
import { RefreshCw, ChevronDown, ChevronUp, ImageIcon } from "lucide-react"
import React, { useState } from "react"

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

function renderMarkdown(content: string) {
  const linkRegex = /\[\[LINK:(\d+):(.*?)\]\]/g
  
  function parseInline(text: string): React.ReactNode[] {
    let linkParts: (string | React.ReactElement)[] = []
    let lastIdx = 0
    let match
    while ((match = linkRegex.exec(text)) !== null) {
      if (match.index > lastIdx) {
        linkParts.push(text.substring(lastIdx, match.index))
      }
      const targetIdx = match[1]
      const keyword = match[2]
      linkParts.push(
        <a
          key={`link-${match.index}`}
          href={`#section-${targetIdx}`}
          className="text-orange-400 hover:underline font-bold border-b border-orange-500/20"
        >
          {keyword}
        </a>
      )
      lastIdx = linkRegex.lastIndex
    }
    if (lastIdx < text.length) {
      linkParts.push(text.substring(lastIdx))
    }

    let finalParts: React.ReactNode[] = []
    for (const part of linkParts) {
      if (typeof part !== "string") {
        finalParts.push(part)
        continue
      }
      const boldRegex = /\*\*(.*?)\*\*/g
      let lastB = 0
      let mB
      while ((mB = boldRegex.exec(part)) !== null) {
        if (mB.index > lastB) {
          finalParts.push(part.substring(lastB, mB.index))
        }
        finalParts.push(
          <strong key={`bold-${mB.index}`} className="font-bold text-white">
            {mB[1]}
          </strong>
        )
        lastB = boldRegex.lastIndex
      }
      if (lastB < part.length) {
        finalParts.push(part.substring(lastB))
      }
    }
    return finalParts
  }

  const lines = content.split("\n")
  const elements: React.ReactElement[] = []
  let currentList: { type: "ul" | "ol"; items: string[] } | null = null

  function flushList(key: number) {
    if (!currentList) return
    const items = currentList.items.map((item, idx) => (
      <li key={idx} className="mb-1">
        {parseInline(item)}
      </li>
    ))
    if (currentList.type === "ul") {
      elements.push(
        <ul key={`list-${key}`} className="list-disc pl-5 space-y-1 my-3 text-gray-300">
          {items}
        </ul>
      )
    } else {
      elements.push(
        <ol key={`list-${key}`} className="list-decimal pl-5 space-y-1 my-3 text-gray-300">
          {items}
        </ol>
      )
    }
    currentList = null
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) {
      flushList(i)
      continue
    }

    if (trimmed.startsWith("### ")) {
      flushList(i)
      elements.push(
        <h4 key={i} className="text-md font-bold text-white mt-4 mb-2">
          {parseInline(trimmed.substring(4))}
        </h4>
      )
      continue
    }

    if (trimmed.startsWith("## ")) {
      flushList(i)
      elements.push(
        <h3 key={i} className="text-lg font-bold text-white mt-5 mb-3">
          {parseInline(trimmed.substring(3))}
        </h3>
      )
      continue
    }

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("• ")) {
      const itemText = trimmed.substring(2)
      if (currentList && currentList.type === "ul") {
        currentList.items.push(itemText)
      } else {
        flushList(i)
        currentList = { type: "ul", items: [itemText] }
      }
      continue
    }

    const olMatch = trimmed.match(/^(\d+)\.\s+(.*)/)
    if (olMatch) {
      const itemText = olMatch[2]
      if (currentList && currentList.type === "ol") {
        currentList.items.push(itemText)
      } else {
        flushList(i)
        currentList = { type: "ol", items: [itemText] }
      }
      continue
    }

    flushList(i)
    elements.push(
      <p key={i} className="mb-4 text-gray-300 leading-relaxed">
        {parseInline(trimmed)}
      </p>
    )
  }

  flushList(lines.length)
  return elements
}


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
      const res = await fetch(`${API}/regenerate-section`, {
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
          <div className="text-gray-300 text-sm leading-relaxed space-y-3">
            {renderMarkdown(section.content)}
          </div>

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

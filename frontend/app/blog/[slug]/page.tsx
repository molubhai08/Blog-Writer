"use client"
import React, { useEffect, useRef, useState } from "react"
import { useParams } from "next/navigation"
import { Blog, Section } from "@/types/blog"
import MCQQuiz from "@/components/MCQQuiz"
import { Clock, Tag, BookOpen, ArrowLeft, Upload, X, List, GraduationCap } from "lucide-react"
import Link from "next/link"
import Image from "next/image"
import { fetchBlogBySlug } from "@/lib/api"


// ── Section Image Upload ─────────────────────────────────────────────────────

function SectionImage({ caption, prompt }: { caption: string; prompt: string }) {
  const [src, setSrc] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setSrc(reader.result as string)
    reader.readAsDataURL(file)
  }

  if (src) {
    return (
      <figure className="space-y-2">
        <div className="relative rounded-xl overflow-hidden border border-gray-700 group">
          <Image src={src} alt={caption} width={800} height={450} className="w-full object-cover" />
          <button
            onClick={() => setSrc(null)}
            className="absolute top-2 right-2 bg-gray-900/80 hover:bg-red-500/80 text-white p-1.5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
        <figcaption className="text-xs text-gray-500 italic text-center">{caption}</figcaption>
      </figure>
    )
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      className="border-2 border-dashed border-gray-700 hover:border-orange-500 rounded-xl p-6 cursor-pointer transition-colors group"
    >
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />
      <div className="flex flex-col items-center gap-2 text-center">
        <Upload className="w-5 h-5 text-gray-600 group-hover:text-orange-400 transition-colors" />
        <p className="text-xs text-gray-500 group-hover:text-gray-400 transition-colors">
          Click to upload image
        </p>
        <p className="text-xs text-gray-600 italic max-w-xs">Suggested: {prompt}</p>
        <p className="text-xs text-gray-500 mt-1">{caption}</p>
      </div>
    </div>
  )
}

// Parses [[LINK:target_idx:keyword]] markers into clickable anchor tags
function renderContentWithLinks(content: string) {
  const regex = /\[\[LINK:(\d+):(.*?)\]\]/g
  const parts: (string | React.ReactElement)[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push(content.substring(lastIndex, match.index))
    }
    const targetIdx = match[1]
    const keyword = match[2]
    parts.push(
      <a
        key={match.index}
        href={`#section-${targetIdx}`}
        className="text-orange-400 hover:underline font-medium border-b border-orange-500/20"
      >
        {keyword}
      </a>
    )
    lastIndex = regex.lastIndex
  }

  if (lastIndex < content.length) {
    parts.push(content.substring(lastIndex))
  }

  return parts.length > 0 ? parts : [content]
}

// ── Blog Page ────────────────────────────────────────────────────────────────

export default function BlogPage() {
  const { slug } = useParams()
  const [blog, setBlog] = useState<Blog | null>(null)

  useEffect(() => {
    async function load() {
      if (!slug) return
      // Try fetching from Supabase via backend API first
      try {
        const apiData = await fetchBlogBySlug(slug as string)
        if (apiData && apiData.metadata) {
          setBlog(apiData)
          return
        }
      } catch (_) {}
      // Fall back to localStorage for backward compatibility
      const stored = localStorage.getItem(`blog_${slug}`)
      if (stored) setBlog(JSON.parse(stored))
    }
    load()
  }, [slug])

  if (!blog) return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <div className="text-center space-y-3">
        <div className="w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-gray-500 text-sm">Loading blog...</p>
      </div>
    </div>
  )

  const { metadata, narrative, sections, references, mcqs, upscCallout } = blog

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-gray-400 hover:text-white text-sm transition-colors">
            <ArrowLeft className="w-4 h-4" /> Back to Generator
          </Link>
          <span className="text-orange-500 font-bold text-lg">Aspire IAS</span>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12 space-y-10">
        {/* Header */}
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {narrative.gsPaper && (
              <span className="bg-orange-500/10 text-orange-400 px-3 py-1 rounded-full border border-orange-500/30 text-xs font-medium">
                {narrative.gsPaper}
              </span>
            )}
            <span className="text-gray-500 text-xs">{narrative.subject}</span>
          </div>

          <h1 className="text-4xl font-bold leading-tight">{metadata.title}</h1>
          <p className="text-gray-400 text-lg">{metadata.metaDescription}</p>

          <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500 pt-2">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" /> {metadata.readingTime} min read
            </span>
            <span className="flex items-center gap-1">
              <BookOpen className="w-3.5 h-3.5" /> {narrative.audience}
            </span>
          </div>

          <div className="flex flex-wrap gap-2 pt-1">
            {metadata.tags.map((tag) => (
              <span key={tag} className="flex items-center gap-1 text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded-full">
                <Tag className="w-3 h-3" /> {tag}
              </span>
            ))}
          </div>
        </div>

        {/* Table of Contents */}
        {sections.length > 0 && (
          <nav className="bg-gray-950 border-l-4 border-orange-500 rounded-r-xl px-5 py-4 space-y-2">
            <div className="flex items-center gap-2 text-orange-400 text-xs font-semibold uppercase tracking-widest mb-3">
              <List className="w-3.5 h-3.5" />
              Table of Contents
            </div>
            <ol className="space-y-1.5 list-none">
              {sections.map((section, i) => (
                <li key={i}>
                  <a
                    href={`#section-${i}`}
                    className="flex items-start gap-2 text-sm text-gray-400 hover:text-orange-400 transition-colors group"
                  >
                    <span className="font-mono text-orange-500/60 text-xs mt-0.5 shrink-0">{i + 1}.</span>
                    <span className="group-hover:underline underline-offset-2">{section.sectionTitle}</span>
                  </a>
                </li>
              ))}
            </ol>
          </nav>
        )}

        {/* Sections */}
        <div className="space-y-10">
          {sections.map((section, i) => (
            <div key={i} id={`section-${i}`} className="space-y-4 scroll-mt-6">
              <h2 className="text-2xl font-bold text-white">{section.sectionTitle}</h2>
              {section.image?.required && (
                <SectionImage
                  prompt={section.image.prompt}
                  caption={section.image.caption}
                />
              )}
              <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                {renderContentWithLinks(section.content)}
              </p>
            </div>
          ))}
        </div>

        {/* UPSC Mains Callout */}
        {upscCallout && upscCallout.mainsQuestion && (
          <div className="border border-orange-500/30 bg-orange-500/5 rounded-xl p-6 space-y-4">
            <div className="flex items-center gap-2 text-orange-400 font-semibold text-sm">
              <GraduationCap className="w-4 h-4" />
              UPSC Mains Practice Question ({narrative.gsPaper})
            </div>
            <p className="text-gray-200 text-sm leading-relaxed font-medium">{upscCallout.mainsQuestion}</p>
            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-widest">Approach</p>
              <p className="text-gray-400 text-sm italic">{upscCallout.approach}</p>
            </div>
            {upscCallout.keywordsToWrite.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-gray-500 uppercase tracking-widest">Keywords to Include</p>
                <div className="flex flex-wrap gap-2">
                  {upscCallout.keywordsToWrite.map((kw) => (
                    <span key={kw} className="text-xs bg-orange-500/10 text-orange-400 border border-orange-500/20 px-2 py-1 rounded-full">
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* References */}
        {references.length > 0 && (
          <div className="border-t border-gray-800 pt-8 space-y-3">
            <h3 className="text-gray-400 text-xs uppercase tracking-widest">References</h3>
            <ul className="space-y-2">
              {references.map((ref) => (
                <li key={ref.id} className="flex items-start gap-2 text-sm">
                  <span className="text-gray-600 font-mono">[{ref.id}]</span>
                  <a href={ref.url} target="_blank" rel="noreferrer" className="text-orange-400 hover:underline break-all">
                    {ref.title || ref.url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* MCQ Quiz */}
        {mcqs.length > 0 && (
          <div className="border-t border-gray-800 pt-8">
            <MCQQuiz mcqs={mcqs} />
          </div>
        )}
      </main>
    </div>
  )
}

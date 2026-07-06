"use client"
import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { Blog } from "@/types/blog"
import MCQQuiz from "@/components/MCQQuiz"
import { Clock, Tag, BookOpen, ArrowLeft } from "lucide-react"
import Link from "next/link"

export default function BlogPage() {
  const { slug } = useParams()
  const [blog, setBlog] = useState<Blog | null>(null)

  useEffect(() => {
    const stored = localStorage.getItem(`blog_${slug}`)
    if (stored) setBlog(JSON.parse(stored))
  }, [slug])

  if (!blog) return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center text-gray-500">
      Blog not found.
    </div>
  )

  const { metadata, narrative, sections, references, mcqs } = blog

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

        <div className="space-y-10">
          {sections.map((section, i) => (
            <div key={i} className="space-y-3">
              <h2 className="text-2xl font-bold text-white">{section.sectionTitle}</h2>
              <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">{section.content}</p>
              {section.image?.required && (
                <div className="bg-gray-800 rounded-xl p-4 border border-gray-700 text-sm text-gray-400 italic">
                  📷 {section.image.caption}
                </div>
              )}
            </div>
          ))}
        </div>

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

        {mcqs.length > 0 && (
          <div className="border-t border-gray-800 pt-8">
            <MCQQuiz mcqs={mcqs} />
          </div>
        )}
      </main>
    </div>
  )
}

"use client"
import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { generateBlog, fetchBlogs, deleteBlog, publishBlog, suggestTopics } from "@/lib/api"
import { Blog, Section, StatusEvent, Audience } from "@/types/blog"
import WorkflowProgress from "@/components/WorkflowProgress"
import BlogView from "@/components/BlogView"
import Link from "next/link"
import { Sparkles, BookOpen, Clock, AlertTriangle, Trash2, BookOpenCheck, ChevronDown, ChevronUp, Lightbulb } from "lucide-react"

function getAgentName(step: string): string {
  if (step === "validator") return "Topic Validator"
  if (step === "researcher") return "Web Researcher"
  if (step === "narrative") return "Narrative Finder"
  if (step.startsWith("section_")) return "Content Writer"
  if (step === "references") return "Reference Manager"
  if (step === "metadata") return "SEO Specialist"
  if (step === "mcqs") return "MCQ Generator"
  if (step === "upsc_callout") return "Mains Specialist"
  return "System"
}

interface BlogSummary {
  slug: string
  topic: string
  audience: string
  title?: string
  created_at?: string
}

interface ConflictState {
  slug: string
  title: string
}

export default function Home() {
  const router = useRouter()
  const [topic, setTopic] = useState("")
  const [audience, setAudience] = useState<Audience>("UPSC")
  const [loading, setLoading] = useState(false)
  const [statuses, setStatuses] = useState<Record<string, StatusEvent>>({})
  const [outline, setOutline] = useState<string[]>([])
  const [blog, setBlog] = useState<Blog | null>(null)
  const [error, setError] = useState("")
  const [conflict, setConflict] = useState<ConflictState | null>(null)
  const [history, setHistory] = useState<BlogSummary[]>([])
  const [historyOpen, setHistoryOpen] = useState(false)
  const [deletingSlug, setDeletingSlug] = useState<string | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [loadingSuggestions, setLoadingSuggestions] = useState(false)

  // Load blog history on mount
  useEffect(() => {
    fetchBlogs()
      .then((data) => setHistory(Array.isArray(data) ? data : []))
      .catch(() => setHistory([]))
  }, [blog]) // Refresh when a new blog is published

  function startGeneration(topicOverride?: string) {
    const t = topicOverride || topic
    if (!t.trim()) return
    setLoading(true)
    setBlog(null)
    setStatuses({})
    setOutline([])
    setError("")
    setConflict(null)
    setLogs([])

    generateBlog(
      t,
      audience,
      (status) => {
        setStatuses((prev) => ({ ...prev, [status.step]: status }))
        if (status.step === "narrative" && status.done && status.data?.outline) {
          setOutline(status.data.outline as string[])
        }

        const agentName = getAgentName(status.step)
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        const logMsg = `[${timeStr}] [${agentName}] ${status.message}`
        setLogs((prev) => [...prev, logMsg])
      },
      (index, section) => {
        setBlog((prev) => {
          if (!prev) return prev
          const sections = [...prev.sections]
          sections[index] = section as Section
          return { ...prev, sections }
        })
      },
      (completeBlog) => {
        setBlog(completeBlog as Blog)
        setLoading(false)
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        setLogs((prev) => [...prev, `[${timeStr}] [System] Blog generation complete! ready to preview and publish.`])
      },
      (err) => {
        setError(err)
        setLoading(false)
        setStatuses({})
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        setLogs((prev) => [...prev, `[${timeStr}] [System] Error occurred: ${err}`])
      },
      (conflictSlug, conflictTitle) => {
        setConflict({ slug: conflictSlug, title: conflictTitle })
        setLoading(false)
        setStatuses({})
        const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
        setLogs((prev) => [...prev, `[${timeStr}] [System] Conflict detected: Similar blog already exists titled "${conflictTitle}".`])
      }
    )
  }

  async function handleDeleteAndRegenerate() {
    if (!conflict) return
    setDeletingSlug(conflict.slug)
    await deleteBlog(conflict.slug)
    setDeletingSlug(null)
    setConflict(null)
    startGeneration()
  }

  function handleSectionUpdate(index: number, newSection: Section) {
    setBlog((prev) => {
      if (!prev) return prev
      const sections = [...prev.sections]
      sections[index] = newSection
      return { ...prev, sections }
    })
  }

  async function handlePublish() {
    if (!blog) return
    const slug = blog.metadata.slug
    // Save to localStorage as backup
    localStorage.setItem(`blog_${slug}`, JSON.stringify(blog))
    // Save to Supabase (only triggered on explicit Publish click)
    await publishBlog(topic, audience, blog)
    router.push(`/blog/${slug}`)
  }

  const isGenerating = loading
  const showProgress = isGenerating || Object.keys(statuses).length > 0

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-orange-500" />
            <span className="text-xl font-bold">Aspire IAS</span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setHistoryOpen(!historyOpen)}
              disabled={history.length === 0}
              className={`flex items-center gap-2 text-sm px-4 py-2 rounded-xl transition-all duration-350 ${
                historyOpen
                  ? "bg-orange-500 text-white shadow-lg shadow-orange-500/20"
                  : "bg-orange-500/10 text-orange-400 border border-orange-500/30 hover:bg-orange-500/20 hover:border-orange-500/50"
              } disabled:opacity-30 disabled:cursor-not-allowed font-medium`}
            >
              <Clock className="w-4 h-4" />
              <span>Published Library</span>
              <span className={`inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold rounded-full ${
                historyOpen ? "bg-white text-orange-600" : "bg-orange-500 text-white"
              }`}>
                {history.length}
              </span>
              {historyOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            <span className="text-xs text-gray-500 font-mono">AI Blog Machine</span>
          </div>
        </div>

        {/* History Dropdown */}
        {historyOpen && history.length > 0 && (
          <div className="max-w-6xl mx-auto mt-3 bg-gray-950 border border-gray-800 rounded-xl overflow-hidden">
            <div className="p-3 border-b border-gray-800">
              <p className="text-xs text-gray-500 uppercase tracking-widest">Published Blogs</p>
            </div>
            <div className="max-h-60 overflow-y-auto divide-y divide-gray-800">
              {history.map((h) => (
                <div
                  key={h.slug}
                  onClick={() => router.push(`/blog/${h.slug}`)}
                  className="flex items-center justify-between px-4 py-3 hover:bg-gray-900 group transition-colors cursor-pointer"
                >
                  <div>
                    <p className="text-sm text-white font-medium group-hover:text-orange-400 transition-colors">{h.topic}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-orange-400">{h.audience}</span>
                      <span className="text-xs text-gray-600">{h.slug}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={async (e) => {
                        e.stopPropagation()
                        if (confirm(`Are you sure you want to delete "${h.topic}"?`)) {
                          await deleteBlog(h.slug)
                          const data = await fetchBlogs()
                          setHistory(Array.isArray(data) ? data : [])
                        }
                      }}
                      className="text-gray-500 hover:text-red-400 p-1.5 rounded transition-colors"
                      title="Delete blog"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <BookOpenCheck className="w-4 h-4 text-gray-600 group-hover:text-orange-400 transition-colors shrink-0" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </header>

      <main className="max-w-6xl mx-auto px-6 py-10">
        {!blog && (
          <div className="max-w-2xl mx-auto space-y-8">
            <div className="text-center space-y-3">
              <h1 className="text-4xl font-bold">
                Generate a <span className="text-orange-500">Human-Like</span> Blog
              </h1>
              <p className="text-gray-400">
                AI-powered multi-agent blog writer. SEO-optimized, audience-aware, UPSC-ready.
              </p>
            </div>

            <div className="bg-gray-950 border border-gray-800 rounded-2xl p-6 space-y-4">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="text-sm text-gray-400">Topic</label>
                  <button
                    onClick={async () => {
                      setLoadingSuggestions(true)
                      setSuggestions([])
                      const results = await suggestTopics(audience)
                      setSuggestions(results)
                      setLoadingSuggestions(false)
                    }}
                    disabled={loadingSuggestions}
                    className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-orange-500/30 text-orange-400 hover:bg-orange-500/10 hover:border-orange-500/60 disabled:opacity-50 transition-all"
                  >
                    <Lightbulb className={`w-3.5 h-3.5 ${loadingSuggestions ? "animate-pulse" : ""}`} />
                    {loadingSuggestions ? "Thinking..." : "Suggest Topics"}
                  </button>
                </div>
                <input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && startGeneration()}
                  placeholder="e.g. Climate Change impact on India"
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-orange-500 transition-colors"
                />
                {suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {suggestions.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => { setTopic(s); setSuggestions([]) }}
                        className="text-xs px-3 py-1.5 rounded-full bg-gray-900 border border-gray-700 text-gray-300 hover:border-orange-500 hover:text-orange-400 transition-all text-left"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <label className="text-sm text-gray-400 mb-2 block">Audience</label>
                <div className="flex gap-2">
                  {(["UPSC", "Professional", "General"] as Audience[]).map((a) => (
                    <button
                      key={a}
                      onClick={() => setAudience(a)}
                      className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors border ${
                        audience === a
                          ? "bg-orange-500 border-orange-500 text-white"
                          : "bg-gray-900 border-gray-700 text-gray-400 hover:border-gray-500"
                      }`}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={() => startGeneration()}
                disabled={loading || !topic.trim()}
                className="w-full py-3.5 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                {loading ? "Generating..." : "Generate Blog"}
              </button>

              {error && <p className="text-red-400 text-sm text-center">{error}</p>}
            </div>

            {/* Conflict Modal */}
            {conflict && (
              <div className="bg-gray-950 border border-orange-500/40 rounded-2xl p-6 space-y-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-orange-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-white font-semibold text-sm">Similar Article Found</p>
                    <p className="text-gray-400 text-sm mt-1">
                      A blog on a highly similar topic already exists:
                    </p>
                    <p className="text-orange-400 text-sm font-medium mt-1">
                      &ldquo;{conflict.title || conflict.slug}&rdquo;
                    </p>
                  </div>
                </div>
                <div className="flex gap-3">
                  <Link
                    href={`/blog/${conflict.slug}`}
                    className="flex-1 text-center py-2.5 text-sm border border-gray-700 text-gray-300 hover:text-white hover:border-gray-500 rounded-xl transition-colors flex items-center justify-center gap-2"
                  >
                    <BookOpenCheck className="w-4 h-4" /> Read Existing
                  </Link>
                  <button
                    onClick={handleDeleteAndRegenerate}
                    disabled={!!deletingSlug}
                    className="flex-1 py-2.5 text-sm bg-red-500/10 border border-red-500/40 text-red-400 hover:bg-red-500/20 rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <Trash2 className="w-4 h-4" />
                    {deletingSlug ? "Deleting..." : "Delete & Regenerate"}
                  </button>
                </div>
              </div>
            )}

            {showProgress && (
              <div className="space-y-4">
                <WorkflowProgress statuses={statuses} outline={outline} audience={audience} />
              </div>
            )}
          </div>
        )}

        {blog && (
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
            <div className="lg:sticky lg:top-6 lg:self-start space-y-4">
              <WorkflowProgress statuses={statuses} outline={outline} audience={audience} />
              <button
                onClick={() => { setBlog(null); setStatuses({}); setOutline([]); setLogs([]) }}
                className="w-full py-2 text-sm text-gray-500 hover:text-white border border-gray-800 rounded-xl transition-colors"
              >
                ← New Blog
              </button>
            </div>
            <BlogView
              blog={blog}
              topic={topic}
              audience={audience}
              onSectionUpdate={handleSectionUpdate}
              onPublish={handlePublish}
            />
          </div>
        )}
      </main>
    </div>
  )
}

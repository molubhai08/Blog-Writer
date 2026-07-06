"use client"
import { useState } from "react"
import { generateBlog } from "@/lib/api"
import { Blog, Section, StatusEvent, Audience } from "@/types/blog"
import WorkflowProgress from "@/components/WorkflowProgress"
import BlogView from "@/components/BlogView"
import { Sparkles, BookOpen } from "lucide-react"

export default function Home() {
  const [topic, setTopic] = useState("")
  const [audience, setAudience] = useState<Audience>("UPSC")
  const [loading, setLoading] = useState(false)
  const [statuses, setStatuses] = useState<Record<string, StatusEvent>>({})
  const [outline, setOutline] = useState<string[]>([])
  const [blog, setBlog] = useState<Blog | null>(null)
  const [error, setError] = useState("")

  function handleGenerate() {
    if (!topic.trim()) return
    setLoading(true)
    setBlog(null)
    setStatuses({})
    setOutline([])
    setError("")

    generateBlog(
      topic,
      audience,
      (status) => {
        setStatuses((prev) => ({ ...prev, [status.step]: status }))
        if (status.step === "narrative" && status.done && status.data?.outline) {
          setOutline(status.data.outline as string[])
        }
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
      },
      (err) => {
        setError(err)
        setLoading(false)
        setStatuses({})
      }
    )
  }

  function handleSectionUpdate(index: number, newSection: Section) {
    setBlog((prev) => {
      if (!prev) return prev
      const sections = [...prev.sections]
      sections[index] = newSection
      return { ...prev, sections }
    })
  }

  function handlePublish() {
    if (!blog) return
    const slug = blog.metadata.slug
    localStorage.setItem(`blog_${slug}`, JSON.stringify(blog))
    window.open(`/blog/${slug}`, "_blank")
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
          <span className="text-xs text-gray-500 font-mono">AI Blog Machine</span>
        </div>
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
              <div>
                <label className="text-sm text-gray-400 mb-2 block">Topic</label>
                <input
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
                  placeholder="e.g. Climate Change impact on India"
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-600 focus:outline-none focus:border-orange-500 transition-colors"
                />
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
                onClick={handleGenerate}
                disabled={loading || !topic.trim()}
                className="w-full py-3.5 bg-orange-500 hover:bg-orange-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                <Sparkles className="w-4 h-4" />
                {loading ? "Generating..." : "Generate Blog"}
              </button>

              {error && <p className="text-red-400 text-sm text-center">{error}</p>}
            </div>

            {showProgress && (
              <WorkflowProgress statuses={statuses} outline={outline} />
            )}
          </div>
        )}

        {blog && (
          <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-6">
            <div className="lg:sticky lg:top-6 lg:self-start">
              <WorkflowProgress statuses={statuses} outline={outline} />
              <button
                onClick={() => { setBlog(null); setStatuses({}); setOutline([]) }}
                className="mt-3 w-full py-2 text-sm text-gray-500 hover:text-white border border-gray-800 rounded-xl transition-colors"
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

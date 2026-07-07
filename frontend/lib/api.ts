const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export function generateBlog(
  topic: string,
  audience: string,
  onStatus: (event: { step: string; message: string; done: boolean; data?: Record<string, unknown> }) => void,
  onSection: (index: number, section: unknown) => void,
  onComplete: (blog: unknown) => void,
  onError: (err: string) => void,
  onConflict: (conflictSlug: string, conflictTitle: string) => void
) {
  fetch(`${API}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, audience }),
  }).then(async (res) => {
    if (!res.ok) {
      const errText = await res.text().catch(() => "Unknown error")
      return onError(`HTTP ${res.status}: ${errText || res.statusText}`)
    }
    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) return onError("No response stream")

    let buffer = ""
    let completed = false

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split("\n\n")
      buffer = parts.pop() ?? ""

      for (const part of parts) {
        const eventMatch = part.match(/^event: (\w+)/)
        const dataMatch = part.match(/^data: (.+)/m)
        if (!eventMatch || !dataMatch) continue

        const event = eventMatch[1]
        const data = JSON.parse(dataMatch[1])

        if (event === "status") onStatus(data)
        else if (event === "section") onSection(data.index, data.section)
        else if (event === "complete") { completed = true; onComplete(data) }
        else if (event === "error") { completed = true; onError(data.message) }
        else if (event === "conflict") { completed = true; onConflict(data.conflictSlug, data.conflictTitle) }
      }
    }

    if (!completed) {
      onError("The server closed the connection before finishing. A backend agent may have crashed — check server logs.")
    }
  }).catch((e) => {
    console.error("Generate API failed:", e)
    onError(`Network Connection Error: Failed to reach the backend server at ${API}. Details: ${e.message}`)
  })
}

export async function regenerateSection(
  topic: string,
  audience: string,
  sectionTitle: string,
  narrative: unknown
) {
  const res = await fetch(`${API}/regenerate-section`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, audience, sectionTitle, narrative }),
  })
  return res.json()
}

export async function fetchBlogs() {
  const res = await fetch(`${API}/blogs`)
  return res.json()
}

export async function fetchBlogBySlug(slug: string) {
  const res = await fetch(`${API}/blog/${slug}`)
  return res.json()
}

export async function deleteBlog(slug: string) {
  await fetch(`${API}/blog/${slug}`, { method: "DELETE" })
}

export async function publishBlog(topic: string, audience: string, blog: unknown) {
  const res = await fetch(`${API}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic, audience, blog }),
  })
  return res.json()
}

export async function suggestTopics(audience: string): Promise<string[]> {
  const res = await fetch(`${API}/suggest-topics?audience=${encodeURIComponent(audience)}`)
  const data = await res.json()
  return Array.isArray(data.topics) ? data.topics : []
}

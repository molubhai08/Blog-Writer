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
    const reader = res.body?.getReader()
    const decoder = new TextDecoder()
    if (!reader) return onError("No response stream")

    let buffer = ""

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
        else if (event === "complete") onComplete(data)
        else if (event === "error") onError(data.message)
        else if (event === "conflict") onConflict(data.conflictSlug, data.conflictTitle)
      }
    }
  }).catch((e) => onError(e.message))
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

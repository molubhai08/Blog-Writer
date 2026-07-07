"use client"
import { Blog, Section, Narrative, UpscCallout } from "@/types/blog"
import SectionCard from "./SectionCard"
import MCQQuiz from "./MCQQuiz"
import { Clock, Tag, BookOpen, GraduationCap } from "lucide-react"

interface Props {
  blog: Blog
  topic: string
  audience: string
  onSectionUpdate: (index: number, section: Section) => void
  onPublish: () => void
}

export default function BlogView({ blog, topic, audience, onSectionUpdate, onPublish }: Props) {
  const { metadata, narrative, sections, references, mcqs, upscCallout } = blog

  return (
    <div className="space-y-8">
      <div className="bg-gray-950 border border-gray-800 rounded-xl p-6 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white">{metadata.title}</h1>
            <p className="text-gray-400 text-sm mt-1">{metadata.metaDescription}</p>
          </div>
          <button
            onClick={onPublish}
            className="shrink-0 px-5 py-2.5 bg-orange-500 hover:bg-orange-600 text-white font-semibold rounded-xl transition-colors text-sm"
          >
            Publish Blog
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" /> {metadata.readingTime} min read
          </span>
          <span className="flex items-center gap-1">
            <BookOpen className="w-3.5 h-3.5" /> {narrative.subject}
          </span>
          {narrative.gsPaper && (
            <span className="bg-orange-500/10 text-orange-400 px-2 py-0.5 rounded-full border border-orange-500/30">
              {narrative.gsPaper}
            </span>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          {metadata.tags.map((tag) => (
            <span key={tag} className="flex items-center gap-1 text-xs bg-gray-800 text-gray-400 px-2 py-1 rounded-full">
              <Tag className="w-3 h-3" /> {tag}
            </span>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="text-gray-400 text-xs uppercase tracking-widest">Sections</h2>
        {sections.map((section, i) => (
          <SectionCard
            key={i}
            section={section}
            index={i}
            topic={topic}
            audience={audience}
            narrative={narrative as unknown as Narrative}
            references={references}
            onRegenerate={onSectionUpdate}
          />
        ))}
      </div>

      {/* UPSC Mains Callout Preview — only visible for UPSC audience before publishing */}
      {audience === "UPSC" && upscCallout && upscCallout.mainsQuestion && (
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

      {mcqs.length > 0 && (
        <div className="bg-gray-950 border border-gray-800 rounded-xl p-6">
          <MCQQuiz mcqs={mcqs} />
        </div>
      )}
    </div>
  )
}

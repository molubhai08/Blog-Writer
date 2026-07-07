"use client"
import { StatusEvent } from "@/types/blog"
import { CheckCircle, Circle, Loader } from "lucide-react"

const STEPS = [
  { key: "validator", label: "Validating Topic" },
  { key: "researcher", label: "Researching Topic" },
  { key: "narrative", label: "Building Outline" },
  { key: "section_0", label: "Writing Section 1" },
  { key: "section_1", label: "Writing Section 2" },
  { key: "section_2", label: "Writing Section 3" },
  { key: "section_3", label: "Writing Section 4" },
  { key: "references", label: "Generating References" },
  { key: "metadata", label: "Generating Metadata" },
  { key: "mcqs", label: "Creating Quiz" },
  { key: "upsc_callout", label: "Generating UPSC Mains Callout" },
]

interface Props {
  statuses: Record<string, StatusEvent>
  outline: string[]
  audience?: string
}

export default function WorkflowProgress({ statuses, outline, audience }: Props) {
  const steps = STEPS.map((s) => {
    const sectionMatch = s.key.match(/^section_(\d+)$/)
    if (sectionMatch) {
      const i = parseInt(sectionMatch[1])
      return { ...s, label: outline[i] ? `Writing: ${outline[i]}` : s.label }
    }
    return s
  }).filter((s) => {
    // Only show the UPSC Mains Callout step when audience is UPSC
    if (s.key === "upsc_callout") {
      return audience === "UPSC"
    }
    const sectionMatch = s.key.match(/^section_(\d+)$/)
    if (sectionMatch) {
      const i = parseInt(sectionMatch[1])
      return outline.length === 0 || i < outline.length
    }
    return true
  })

  return (
    <div className="bg-gray-950 border border-gray-800 rounded-xl p-5 font-mono text-sm">
      <p className="text-gray-400 text-xs mb-4 uppercase tracking-widest">AI Workflow</p>
      <div className="space-y-2">
        {steps.map((step) => {
          const status = statuses[step.key]
          const isDone = status?.done
          const isActive = status && !status.done

          return (
            <div key={step.key}>
              <div className="flex items-center gap-3">
                {isDone ? (
                  <CheckCircle className="w-4 h-4 text-green-400 shrink-0" />
                ) : isActive ? (
                  <Loader className="w-4 h-4 text-orange-400 animate-spin shrink-0" />
                ) : (
                  <Circle className="w-4 h-4 text-gray-700 shrink-0" />
                )}
                <span className={isDone ? "text-green-400" : isActive ? "text-orange-300" : "text-gray-600"}>
                  {step.label}
                </span>
              </div>
              {isDone && status?.data && (
                <div className="ml-7 mt-1 text-xs text-gray-500 space-y-0.5">
                  {Object.entries(status.data).map(([k, v]) => (
                    <div key={k} className="break-all">
                      <span className="text-gray-600">{k}: </span>
                      <span>{Array.isArray(v) ? v.join(", ") : String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

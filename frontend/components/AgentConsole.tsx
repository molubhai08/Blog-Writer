"use client"
import React, { useEffect, useRef } from "react"

interface Props {
  logs: string[]
}

export default function AgentConsole({ logs }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [logs])

  if (logs.length === 0) return null

  return (
    <div className="bg-black border border-gray-800 rounded-xl p-4 font-mono text-xs text-orange-400 space-y-1.5 shadow-2xl h-60 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent">
      <div className="flex items-center justify-between border-b border-gray-800 pb-2 mb-2">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
          <span className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
          <span className="w-2.5 h-2.5 rounded-full bg-green-500" />
          <span className="text-gray-500 ml-2 text-[10px] uppercase tracking-wider font-semibold">Agent Workflow Terminal</span>
        </div>
        <span className="text-gray-600 text-[10px] font-mono">v1.0.0</span>
      </div>
      <div className="space-y-1">
        {logs.map((log, i) => {
          const match = log.match(/^\[(.*?)\]\s+\[(.*?)\]\s+(.*)$/)
          if (match) {
            const [, time, agent, msg] = match
            let agentColor = "text-orange-400"
            if (agent === "Topic Validator") agentColor = "text-yellow-400"
            else if (agent === "Web Researcher") agentColor = "text-blue-400"
            else if (agent === "Narrative Finder") agentColor = "text-purple-400"
            else if (agent === "Content Writer") agentColor = "text-green-400"
            else if (agent === "Reference Manager") agentColor = "text-pink-400"
            else if (agent === "SEO Specialist") agentColor = "text-teal-400"
            else if (agent === "MCQ Generator") agentColor = "text-indigo-400"
            else if (agent === "Mains Specialist") agentColor = "text-red-400"
            else if (agent === "System") agentColor = "text-emerald-400 font-bold"

            return (
              <div key={i} className="leading-relaxed flex items-start gap-1">
                <span className="text-gray-600 shrink-0 select-none">[{time}]</span>
                <span className={`${agentColor} font-semibold shrink-0 select-none`}>[{agent}]</span>
                <span className="text-gray-300 break-words">{msg}</span>
              </div>
            )
          }
          return (
            <div key={i} className="text-gray-300 leading-relaxed break-words">
              {log}
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

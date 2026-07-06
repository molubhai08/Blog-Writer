"use client"
import { MCQ } from "@/types/blog"
import { useState } from "react"
import { CheckCircle, XCircle } from "lucide-react"

interface Props {
  mcqs: MCQ[]
}

export default function MCQQuiz({ mcqs }: Props) {
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [submitted, setSubmitted] = useState(false)

  const score = submitted
    ? mcqs.filter((q, i) => answers[i] === q.correctAnswer).length
    : 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-white text-xl font-bold">Test Your Knowledge</h2>
        {submitted && (
          <span className="text-sm font-mono text-orange-400">
            Score: {score}/{mcqs.length}
          </span>
        )}
      </div>

      {mcqs.map((mcq, i) => (
        <div key={i} className="bg-gray-950 border border-gray-800 rounded-xl p-5">
          <p className="text-white font-medium mb-4">
            <span className="text-gray-500 font-mono mr-2">Q{i + 1}.</span>
            {mcq.question}
          </p>
          <div className="grid grid-cols-1 gap-2">
            {(Object.entries(mcq.options) as [string, string][]).map(([key, val]) => {
              const selected = answers[i] === key
              const isCorrect = mcq.correctAnswer === key
              let cls = "flex items-center gap-3 px-4 py-3 rounded-lg border text-sm cursor-pointer transition-all "

              if (!submitted) {
                cls += selected
                  ? "border-orange-500 bg-orange-500/10 text-white"
                  : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-white"
              } else {
                if (isCorrect) cls += "border-green-500 bg-green-500/10 text-green-300"
                else if (selected && !isCorrect) cls += "border-red-500 bg-red-500/10 text-red-300"
                else cls += "border-gray-800 text-gray-600"
              }

              return (
                <div
                  key={key}
                  className={cls}
                  onClick={() => !submitted && setAnswers((p) => ({ ...p, [i]: key }))}
                >
                  <span className="font-mono text-xs w-5 shrink-0">{key}.</span>
                  <span>{val}</span>
                  {submitted && isCorrect && <CheckCircle className="w-4 h-4 ml-auto text-green-400" />}
                  {submitted && selected && !isCorrect && <XCircle className="w-4 h-4 ml-auto text-red-400" />}
                </div>
              )
            })}
          </div>
          {submitted && (
            <p className="mt-3 text-xs text-gray-500 italic">{mcq.explanation}</p>
          )}
        </div>
      ))}

      {!submitted && (
        <button
          onClick={() => setSubmitted(true)}
          disabled={Object.keys(answers).length < mcqs.length}
          className="w-full py-3 rounded-xl bg-orange-500 hover:bg-orange-600 text-white font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Submit Answers
        </button>
      )}
    </div>
  )
}

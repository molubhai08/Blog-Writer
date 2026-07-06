export type Audience = "UPSC" | "Professional" | "General"

export interface Finding {
  fact: string
  url: string
  title: string
}

export interface Image {
  required: boolean
  prompt: string
  caption: string
}

export interface Section {
  sectionTitle: string
  content: string
  humanScore: number
  image: Image
}

export interface Reference {
  id: number
  url: string
  title: string
}

export interface MCQOption {
  A: string
  B: string
  C: string
  D: string
}

export interface MCQ {
  question: string
  options: MCQOption
  correctAnswer: string
  explanation: string
}

export interface Metadata {
  title: string
  metaTitle: string
  metaDescription: string
  slug: string
  tags: string[]
  primaryKeyword: string
  relatedKeywords: string[]
  readingTime: number
}

export interface Narrative {
  audience: string
  subject: string
  gsPaper: string | null
  writingInstructions: string[]
}

export interface Blog {
  metadata: Metadata
  narrative: Narrative
  sections: Section[]
  references: Reference[]
  mcqs: MCQ[]
}

export interface StatusEvent {
  step: string
  message: string
  done: boolean
  data?: Record<string, unknown>
}

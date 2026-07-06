# SEO Writing Guidelines

## Goal
Generate content that is optimized for search engines while remaining natural, informative, and enjoyable for humans to read. Never sacrifice readability for SEO.

## 1. SEO-Friendly Title

**Rules:**
- Create a descriptive and meaningful title
- Naturally include the primary keyword
- Keep the title concise (around 50–60 characters when possible)
- Avoid clickbait and exaggerated claims

**Good Example:**
Artificial Intelligence in Healthcare: Applications, Challenges & Future

**Bad Example:**
Everything You Need to Know About AI!!!

## 2. Heading Structure

Always maintain a logical hierarchy:
- **H1** → Blog Title
- **H2** → Major Sections
- **H3** → Subsections (only when necessary)

**Avoid vague headings like:**
- More Information
- Overview
- Miscellaneous

**Prefer descriptive headings such as:**
- Applications of Artificial Intelligence in Healthcare
- Challenges in AI Adoption
- Government Initiatives

## 3. Keyword Optimization

Identify one primary keyword. Use it naturally in:
- Title
- Introduction
- At least one H2
- Conclusion

Use related keywords naturally throughout the content.

**Never force keywords or repeat them unnaturally. Avoid keyword stuffing.**

**Example:**
- Primary Keyword: Artificial Intelligence in Healthcare
- Related Keywords: AI diagnostics, Machine Learning, Digital Health, Telemedicine

## 4. Readability

The content should:
- Use short to medium paragraphs
- Be easy to scan
- Use bullet points where appropriate
- Maintain logical transitions
- Avoid overly complex wording
- Avoid repetitive phrasing

## 5. Search Intent

Before writing, determine why a user would search for the topic.

**Example:**
Topic: Climate Change in India

Likely Intent:
- Understand the concept
- Learn causes
- Learn impacts
- Know government initiatives
- Prepare for UPSC

The generated content should directly answer these intents.

## 6. Introduction

The introduction should:
- Explain the topic clearly
- Include the primary keyword naturally
- Tell readers what the article will cover
- Avoid unnecessary historical background unless relevant

**Good Example:**
Climate change is one of India's most pressing environmental challenges. Rising temperatures, erratic monsoons, and increasing extreme weather events are affecting agriculture, biodiversity, and public health. This article explores its causes, impacts, and key mitigation strategies.

**Bad Example:**
Climate change has become a buzzword nowadays. It is very important. We all know about climate change.

## 7. Conclusion

The conclusion should:
- Summarize key points
- Reinforce the central message
- End with a meaningful takeaway or future outlook
- Avoid introducing completely new ideas

## 8. Internal Linking Suggestions

Whenever another relevant topic naturally appears, suggest related reading instead of forcing links.

**Example:**
Related Reading:
- Machine Learning Basics
- National Action Plan on Climate Change
- Digital India Mission

## 9. Image Suggestions

Whenever a section would benefit from a visual, generate an image suggestion object containing:
- required (true/false)
- placement
- prompt
- caption

**Example:**
```json
{
  "required": true,
  "placement": "After Section 2",
  "prompt": "Illustration showing AI-assisted medical diagnosis workflow",
  "caption": "How AI assists doctors during diagnosis"
}
```

Do not generate HTML image tags.

## 10. Metadata Generation

After the complete blog is written, generate:
- SEO Title
- Meta Title
- Meta Description
- URL Slug
- Tags
- Subject (if applicable)

Do not generate metadata while writing individual sections.

## 11. Common SEO Mistakes to Avoid

**Never:**
- Stuff keywords repeatedly
- Use duplicate headings
- Write overly long paragraphs
- Use generic or misleading titles
- Add unnecessary filler content
- Sacrifice readability for SEO

**Avoid common AI phrases such as:**
- In today's world...
- It is important to note...
- Needless to say...
- Delve into...
- The rapid advancement of...
- Without a doubt...

## Overall Principle

SEO should enhance the content, not dominate it. Prioritize writing that satisfies user intent, is easy to read, logically structured, and naturally optimized for search engines. Every SEO decision should improve both discoverability and the reader's experience.

---
name: web-research
description: "Conduct thorough web research on a topic, synthesizing multiple sources."
when_to_use: "When asked to research a topic, find documentation, or compare options."
allowed-tools:
  - web_search
  - bash
context: inline
version: "1.0.0"
---

# Web Research

Conduct thorough research. Do not stop at the first result — synthesize multiple sources.

## Process

**Step 1 — Understand the question**
Identify exactly what needs to be answered. Break compound questions into sub-questions.

**Step 2 — Search strategically**
Use multiple search queries per sub-question. Vary terminology. Use technical terms where appropriate.

**Step 3 — Evaluate sources**
Prefer: official docs, peer-reviewed content, well-known technical blogs, GitHub repos.
Avoid: single anecdotal posts, outdated content (check dates), sites with heavy SEO padding.

**Step 4 — Cross-reference**
If two sources disagree, note the disagreement and explain which is more likely correct and why.

**Step 5 — Synthesize**
Write a clear, structured summary:
- Direct answer to the question
- Key supporting evidence with sources
- Important caveats or limitations
- Related information that may be useful

## Output format
Use Markdown with clear headings. Include source URLs inline. Be direct — lead with the answer, then support it.

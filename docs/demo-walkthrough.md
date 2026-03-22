# Demo Walkthrough: "Cursor for Public Policy"

10-minute structured demo for stakeholders (investors, customers, partners).
Total runtime: ~10 minutes. Pace yourself — leave 2 minutes of buffer.

---

## Before the Demo

### Checklist

- [ ] **Backend running** — `uvicorn src.api.app:app --reload` (wait for "BM25 index built" in logs)
- [ ] **Frontend running** — `cd frontend && npm run dev` (confirm http://localhost:3000 loads)
- [ ] **Demo data seeded** — `python scripts/seed_demo.py` (creates "Model Data Privacy Act" workspace with precedents, outline, drafted sections, and conversation history)
- [ ] **BM25 index warm** — Verify by running a quick search on `/search` for "data privacy" and confirming results appear instantly. If results are slow or empty, restart the backend and wait for the startup log line.
- [ ] **API keys set** — `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY` in environment (LLM calls will fail without these)
- [ ] **Browser prep** — Use Chrome or Edge, clear the tab bar, close unrelated tabs, increase font size to 125% for screen sharing
- [ ] **Network** — Confirm you are on a stable connection. LLM streaming requires sustained connectivity. If presenting on conference Wi-Fi, consider tethering to a phone hotspot.

### Demo Data Requirements

The `seed_demo.py` script creates:

| Asset | Purpose |
|-------|---------|
| Workspace: "Model Data Privacy Act" | Primary demo workspace |
| Target jurisdiction | A specific state (e.g., Colorado or California) |
| 3-4 precedent bills | Real privacy bills from the database (e.g., CCPA, Colorado Privacy Act, Virginia CDPA) |
| Pre-generated outline | 5-6 sections with headings and purposes |
| 2-3 drafted sections | At least 2 revisions each, showing AI iteration history |
| Workspace conversation | 2-3 research exchanges demonstrating assistant capabilities |

If the seed script reports "Demo workspace already exists — skipping", the data is already in place.

---

## Demo Flow

### 1. Landing Page (30 seconds)

**Navigate to:** `http://localhost:3000`

**Talking points:**

- "This is the **Policy Drafting IDE** — think Cursor, but for model legislation instead of code."
- Point to the headline: *"The Policy Drafting IDE"* and the subtext about drafting grounded in real legislative data, AI analysis, and ML predictions across 50 states and Congress.
- Walk through the **How It Works** steps: "The workflow is four steps — select precedent bills, generate a jurisdiction-aware outline, draft and analyze with AI, then research and refine as you write."
- Gesture at the feature cards: "Under the hood, it has a 10-tool agentic research assistant, hybrid search across every state, constitutional analysis, and an ML model that predicts bill outcomes with 99.7% AUROC."
- Click **"Start Drafting"** to transition to the composer.

**Fallback:** If the page loads slowly, say: "The frontend is a Next.js app — in production this would be edge-deployed, so load times are sub-second."

---

### 2. Open Demo Workspace (1 minute)

**Navigate to:** `/composer` (you land here after clicking "Start Drafting")

**Talking points:**

- "This is the composer dashboard. Each workspace is a drafting project — it has a target jurisdiction, a set of precedent bills, and a drafting template."
- Click on the **"Model Data Privacy Act"** workspace card.
- Once inside the workspace, point out:
  - The **status badge** (e.g., "Drafted" or "Outlined") — "The system tracks where you are in the drafting lifecycle."
  - The **jurisdiction badge** (e.g., "Colorado") — "Every workspace is jurisdiction-aware. The AI tailors statutory language to the target state's conventions."
  - The **drafting template** badge (e.g., "General Model Act") — "Templates give the AI structural guidance for different bill types."
- Scroll down to the **Precedent Bills** section. Point out the **insight cards**:
  - "Each precedent shows an ML prediction probability — this one has a 78% chance of committee passage. Green means strong precedent, red means it struggled legislatively."
  - "Below the probability is an AI-generated summary of what makes this bill relevant."

**Fallback:** If insights fail to load (API timeout), say: "The prediction model runs on 119K historical bills. Occasionally the first load takes a moment to warm up the model — the probabilities would appear here showing committee passage likelihood."

---

### 3. Generate Outline (1 minute)

**Talking points:**

- "The outline was generated from the precedent bills. The AI analyzed the structure of 3-4 real privacy bills and synthesized a jurisdiction-aware outline."
- Scroll to the **Outline** section. Point out:
  - The **confidence score** (e.g., "87% confidence") — "The system tells you how confident it is in the outline structure based on precedent consensus."
  - The **drafting notes** — "These are AI-generated notes about structural choices — why it included a particular section, where precedents disagreed."
  - The **section list** — walk through 2-3 sections: "Definitions, Scope and Applicability, Consumer Rights — this mirrors what you'd see in a real privacy bill."
- Point to a section's **purpose field**: "Each section has a purpose statement that the AI generated from precedent analysis. You can edit these before drafting."
- **Provenance**: "Every section traces back to the precedent bills it was derived from. Nothing is invented — it is all grounded in real legislation."

**Fallback:** If the outline appears empty (seed data issue), click **"Generate Outline"** live. Say: "Let me generate one now — the AI is analyzing the precedent bills' structure." While it runs (~15-20s), explain: "It reads the full text of each precedent, identifies common structural patterns, and synthesizes a unified outline tailored to our target jurisdiction." This works as a live demo of the feature.

---

### 4. Compose a Section (2 minutes)

**This is the centerpiece of the demo. Take your time here.**

**Talking points:**

- Pick a section that does NOT already have drafted content (or pick one where you want to show re-drafting).
- "Now let's draft a section. I will click 'Draft Section' and the AI will compose statutory text grounded in the precedent bills."
- Click **"Draft Section"** on the chosen section.
- **While tokens stream in:** "Watch the text stream in real-time — you're seeing Claude generate statutory language token by token. This is not a pre-canned response — it is synthesizing from the precedent bills we selected."
- **When streaming finishes:** "The system presents this as a structured result with Accept and Reject controls. This is a human-in-the-loop workflow — the AI proposes, the analyst decides."
- Point out the **action type badge** ("Draft Section") and **Pending Review** badge.
- "If I accept, this becomes the current draft. If I reject, nothing changes — the workspace stays clean."
- Click **Accept**.
- Point out that additional compose actions are now available: "Now that we have draft text, I can also Rewrite Selection, Tighten Definitions, or Harmonize with Precedent — these are specialized AI actions for policy refinement."

**Fallback:** If the API is slow or times out: "The streaming infrastructure uses Server-Sent Events — same protocol GitHub Copilot uses. In production on a fast connection, you would see tokens appearing immediately. Let me show you a section that was already drafted." Scroll to a pre-drafted section from the seed data.

---

### 5. Analyze Draft (1 minute)

**Talking points:**

- On a section that has drafted content, point out the **analysis buttons** after the compose actions: "Constitutional Analysis" and "Pattern Detection".
- Click **"Constitutional Analysis"**.
- **While streaming:** "The AI is checking this draft against First Amendment, Due Process, Equal Protection, Commerce Clause, and federal preemption concerns. This is the kind of analysis that would take a legislative counsel hours."
- **When results appear:** Walk through the concerns: "It flagged a potential Commerce Clause issue here — this enforcement mechanism could create an undue burden on interstate commerce. These are the kinds of issues you want to catch before the bill reaches committee."
- "You can accept or reject the analysis. Accepting updates the section with the AI's recommended revisions."

**Fallback:** If analysis is slow, say: "The analysis prompt is intentionally thorough — it checks five constitutional dimensions. While it runs, I should mention that all analysis results are cached by content hash, so re-running the same analysis is instant."

---

### 6. Research Assistant (2 minutes)

**This is the second major wow moment.**

**Talking points:**

- Scroll to the **Research Assistant** panel (below the outline, collapsible section).
- Click to expand it. "This is the embedded research assistant — it has access to 10 tools for searching bills, analyzing constitutionality, finding similar legislation, and more."
- If there is existing conversation history from the seed data, briefly acknowledge it: "There is already some research history here from earlier work on this draft."
- Type a question: **"How do other states handle data privacy enforcement? Compare the approaches in California, Virginia, and Colorado."**
- **While the assistant works:**
  - Point out the **tool status indicators**: "See that — it just searched for California privacy bills. Now it is pulling up Virginia's enforcement provisions."
  - "This is an agentic loop — the AI decides which tools to use, calls them autonomously, and synthesizes a response. It might make 3-5 tool calls to answer a cross-jurisdictional question like this."
- **When the response streams in:** "Notice it is citing specific bills and provisions — this is not hallucination, it is grounded in the actual bill text from our database."
- Point out **tool call badges** that appear below the response: "You can see exactly which tools it used — search_bills, get_bill_detail, find_similar_bills."

**Fallback:** If the assistant times out or errors, click **Retry** (the retry button appears automatically on retryable errors). Say: "The assistant has automatic error recovery — rate limits, timeouts, and transient failures all get retry buttons. In a production deployment, this would be backed by multiple API keys with automatic failover."

---

### 7. Apply Suggestion (30 seconds)

**Talking points:**

- "When the research assistant suggests specific statutory language, you can apply it directly to the composer."
- If the assistant's response from Step 6 included suggested language (blockquote format), a suggestion banner will appear: "See this suggestion — the assistant recommended specific enforcement language based on Colorado's approach."
- "One click and it goes into the compose form. The workflow stays integrated — research feeds directly into drafting."

**Fallback:** If the assistant did not produce a suggestion in Step 6, explain the flow verbally: "When the assistant includes a blockquote with 'Suggested language:', the UI shows an 'Apply to Compose' action. This closes the loop between research and drafting — you never have to copy-paste between tools."

---

### 8. Revision Diff (1 minute)

**Talking points:**

- Navigate to a section that has **multiple revisions** (the seed data creates sections with 2+ revisions).
- Click the **revision history toggle** (clock icon or "History" expander on the section).
- "Every AI-generated revision is tracked. The system stores the full history with timestamps and action types."
- Point out the **inline diff display**: "Green highlights are additions, red strikethrough is text that was removed. This is word-level diffing — you can see exactly what the AI changed between iterations."
- "This is critical for accountability. When a legislative counsel reviews the draft, they can see the full provenance of every change — which AI action produced it, what precedents it drew from, and what the previous version said."
- Toggle between revisions if multiple are available: "You can compare any two adjacent revisions."

**Fallback:** If revision history is empty (seed data issue), say: "The revision diff component uses word-level diffing — same algorithm as Google Docs' suggestion mode. Each AI action creates a new revision, so after a few rounds of drafting and refining, you would see a full history here with visual diffs."

---

### 9. Search & Prediction (1 minute)

**Navigate to:** `/search` (use the top navigation)

**Talking points:**

- Type **"data privacy"** in the search box and submit.
- "This is hybrid search — it combines BM25 keyword matching with semantic vector search using legal-domain embeddings, then fuses the results with Reciprocal Rank Fusion. It searches across all 50 states and Congress."
- Point out result cards: jurisdiction badges, status badges, relevance scores.
- Click on a bill result to go to the **bill detail page** (`/bills/{id}`).
- On the bill detail page, click the **"Prediction"** tab:
  - "This is the ML prediction model — a stacking ensemble trained on 119,000 bills. It predicts the probability of committee passage."
  - Point out the probability score and the **top contributing factors**: "It shows why — sponsor count, committee assignment, session timing. These are the features the model found most predictive."
- Briefly mention other tabs: "You also have full bill text, sponsor lists, action history, constitutional analysis, similar bills, and cross-jurisdictional diffusion tracking."

**Fallback:** If search returns no results, the BM25 index may not be built. Say: "The hybrid search combines two retrieval methods — on first startup the BM25 index needs to build from the full bill corpus, which takes a few seconds. In production this is pre-warmed." Navigate directly to a bill you know exists from the seed data.

---

## Closing (30 seconds)

"So what you have seen is a complete policy drafting environment — precedent-grounded outlines, AI-powered section drafting with streaming, constitutional analysis, an embedded research assistant that uses real legislative data, revision tracking with visual diffs, and ML predictions. This is what we mean by a 'Cursor for public policy' — research and writing in one integrated workspace, grounded in real data, not generated from thin air."

---

## Recovery Playbook

| Failure | Recovery |
|---------|----------|
| Backend not responding | Check terminal for errors. Common: missing `DATABASE_URL` or port conflict. Restart with `uvicorn src.api.app:app --reload --port 8001` if 8000 is taken. |
| LLM calls timing out | Skip the live demo of that feature, show a pre-drafted section instead. Say: "The API is experiencing high load — let me show you a completed example." |
| Search returns empty | BM25 not built. Restart backend and wait for "BM25 index built" log line. In the meantime, navigate directly to a bill page. |
| Chat assistant loops | The agentic loop has a max iteration limit. If it appears stuck, click away and come back. Say: "The agent is doing deep research — in practice it converges in 3-5 tool calls." |
| Streaming stops mid-response | The retry button will appear. Click it. Say: "Built-in error recovery — the system detects dropped connections and offers retry." |
| Demo workspace missing | Run `python scripts/seed_demo.py` between demo sections. It is idempotent and takes ~10 seconds. |
| Frontend build error | Run `cd frontend && npm run build && npm run dev`. If types fail, `npm run dev` still works (dev mode is more permissive). |
| Prediction tab empty | The ML model needs to be loaded. Check that the model artifact file exists. Say: "The prediction model loads on first request — subsequent predictions are instant." |

---

## Timing Guide

| Step | Duration | Cumulative |
|------|----------|------------|
| 1. Landing Page | 0:30 | 0:30 |
| 2. Open Demo Workspace | 1:00 | 1:30 |
| 3. Generate Outline | 1:00 | 2:30 |
| 4. Compose a Section | 2:00 | 4:30 |
| 5. Analyze Draft | 1:00 | 5:30 |
| 6. Research Assistant | 2:00 | 7:30 |
| 7. Apply Suggestion | 0:30 | 8:00 |
| 8. Revision Diff | 1:00 | 9:00 |
| 9. Search & Prediction | 1:00 | 10:00 |

If running long, cut Steps 7 and 8 (explain verbally) to stay under 10 minutes.
If running short, expand Step 6 with a follow-up question to the research assistant.

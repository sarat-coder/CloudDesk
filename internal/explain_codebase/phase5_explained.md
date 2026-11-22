# Phase 5 — Knowledge Pipeline: Plain-English Explanation

*For the interview board — no technical background assumed.*

---

## What problem does this phase solve?

Before Phase 5, our AI support assistant could read a support ticket and talk to customers — but it
had nowhere to look up **the company's own documentation**. It was answering from scratch every time,
like a new employee who hasn't read the handbook.

Phase 5 gives the assistant a **searchable knowledge base** — 15 help articles covering topics like
MFA login, billing, API rate limits, storage quotas, and SSO. When a ticket arrives, the assistant
can now find the most relevant articles and cite them in its reply, the same way a good support agent
looks up the docs before answering.

---

## The big picture in one sentence

> Phase 5 turns a folder of Markdown help articles into a fast, searchable library that the AI can
> query in plain English and get back the most relevant passages, ranked by relevance.

---

## How it works — step by step

### Step 1 — Break articles into small pieces (Chunking)

A help article might be 2,000 words long. If the assistant reads the whole article every time, it
would be slow and expensive. Instead we **chop each article into small overlapping pieces**, about
900 characters each, with a 150-character overlap so no sentence is ever cut off mid-thought.

Each piece (called a "chunk") carries a label like:
> *"MFA Guide - Lockout: If you've been locked out after too many failed MFA attempts…"*

The label format is `"{Article Title} - {Section Heading}: {text}"`. This label is what gets stored
in the search index so the assistant can find the right piece even when the question uses different
words than the article does.

### Step 2 — Turn text into numbers (Embeddings)

Computers can't search "by meaning" directly. We convert each chunk of text into a list of 384
numbers called a **vector** or **embedding**. Similar meanings produce similar numbers. So "account
locked out" and "can't log in" end up with similar-looking number lists.

In demo mode (no internet, no paid API key), we use a simple in-house calculation that maps words
to numbers deterministically — it's not as smart as a commercial model but works perfectly for
demonstrations and tests.

### Step 3 — Store the numbers (Vector Store)

The 384-number vectors for every chunk are stored in an **in-memory index** (think of it as a very
fast lookup table). In production this would be an external database called Qdrant, but in demo mode
it lives in RAM.

When we receive a search query, we turn that query into a 384-number vector too, then find the stored
chunks whose vectors are closest — that's **semantic search** (search by meaning).

### Step 4 — Also index the words (BM25 / Keyword Search)

Semantic search is great for meaning but can miss exact technical terms. If someone types
"error 429" (an HTTP status code), a meaning-based search might not find the right article.

We also keep a **keyword index** using a classic algorithm called BM25 — the same method Google
used in its early days. It scores articles by how often the search words appear, adjusted for
article length.

### Step 5 — Combine both rankings (Hybrid Retrieval + RRF)

We run both searches (semantic + keyword), then combine the two ranked lists using a technique
called **Reciprocal Rank Fusion (RRF)**. It gives points to articles based on where they appear in
each list. An article that ranks #1 in both gets a very high combined score. An article that only
ranks well in one gets fewer points.

After combining, we apply two small boosts:
- **Category boost** — if the ticket is tagged "billing", billing articles score slightly higher.
- **Title overlap** — if the question contains words from the article title, that article scores
  higher.

Finally, we keep only **one result per article** (no duplicate sections from the same document).

### Step 6 — Serve results through an API

The assistant (and human agents) can search the knowledge base through three HTTP endpoints:

| What you call | What you get |
|---|---|
| `GET /api/v1/knowledge/articles` | A list of all 15 help articles |
| `GET /api/v1/knowledge/articles/mfa-and-account-recovery` | Full text of that article |
| `POST /api/v1/knowledge/search` | Top matching passages for a query |
| `POST /api/v1/knowledge/reindex` | Rebuild the index (admin only) |

### Step 7 — Cache results for speed

If the same question is asked twice, we don't re-run the search. Results are stored in Redis (a fast
in-memory cache) for 5 minutes. This keeps the system fast when multiple agents are working
simultaneously.

---

## A day-in-the-life example

A ticket arrives: *"I keep getting locked out after trying to reset my MFA"*

1. The system searches the knowledge base with this sentence.
2. It finds the "MFA and Account Recovery" article as the top result, specifically the section on
   lockout recovery.
3. The AI drafts a reply: *"Our MFA recovery guide explains that backup codes can be used to regain
   access — please follow the steps at [link]…"*
4. The human agent reviews the draft and sees the cited article, so they can verify the information
   is correct before sending.

---

## What was built in this phase

| Component | File(s) | What it does |
|---|---|---|
| Article loader | `rag/chunking.py` | Reads `.md` files, extracts YAML headers, splits into chunks |
| Vector store | `rag/vector_store.py` | Stores and searches 384-dim number vectors |
| Retriever | `rag/retriever.py` | Combines semantic + keyword search, applies RRF and re-ranking |
| Ingest pipeline | `rag/ingest.py` | Orchestrates the whole load → embed → index process |
| Knowledge API | `backend/app/api/knowledge.py` | HTTP endpoints for agents and admin |
| Article schema | `backend/app/schemas/knowledge.py` | Data shapes for API responses |
| Article repository | `backend/app/repositories/knowledge_repository.py` | Database reads/writes for articles |
| Seed integration | `backend/app/services/seed_service.py` | Auto-loads articles into the DB on first boot |
| App integration | `backend/app/main.py` | Runs the ingest pipeline when the server starts |

---

## Why this matters

Without this phase, the AI assistant was essentially making things up or giving generic advice.
With it, every answer can be **grounded in documented company policy** — and every claim can be
**cited back to a specific help article**. That's the foundation for trustworthy AI-powered support.

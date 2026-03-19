# PRD: Migrate Local ChromaDB RAG to Upstash Vector

## 1. Objective

Replace the current local ChromaDB + manual Ollama embedding pipeline with Upstash Vector Database using built-in embeddings.

Goals:
- Keep the same user-facing RAG behavior (interactive CLI, top context retrieval, LLM answer generation).
- Remove local embedding generation and local vector persistence complexity.
- Move vector indexing/query to a managed, serverless vector service.

Non-goals:
- Changing the LLM provider (Ollama `llama3.2` stays as-is).
- Rewriting the app into a web service (CLI-first workflow remains).

---

## 2. Current State (Before)

Current pipeline in `rag_run.py`:
1. Load `foods.json`.
2. Create/open local Chroma collection.
3. For each new item:
	- Build enriched text.
	- Generate embedding via local Ollama embeddings endpoint (`mxbai-embed-large`).
	- Upsert into Chroma with `documents`, `embeddings`, `ids`.
4. On query:
	- Embed question using Ollama.
	- Query Chroma with embedding vector.
	- Build context from top documents.
	- Send prompt to Ollama generation endpoint.

Pain points:
- Two inference calls for embeddings (ingest + query) managed by app code.
- Local vector DB state tied to machine disk.
- Operational coupling to local embedding model availability.
- Manual dedup logic and embedding flow increases code path complexity.

---

## 3. Target State (After)

Upstash Vector index handles vectorization automatically using built-in model:
- Model: `mixedbread-ai/mxbai-embed-large-v1`
- Dimensions: 1024
- Sequence length: 512
- Similarity: cosine

Target pipeline:
1. Load `foods.json`.
2. Initialize Upstash `Index` client using `.env` credentials.
3. For each new item:
	- Build enriched text.
	- Upsert raw text (`data`) + metadata + id to Upstash.
4. On query:
	- Call Upstash `query(data=<question>, top_k=3, ...)` with raw question text.
	- Receive nearest matches.
	- Build context from returned text payload.
	- Send prompt to Ollama generation endpoint.

Result:
- No embedding vectors handled in application code.
- No local vector store persistence required.
- Retrieval quality preserved with similar embedding family.

---

## 4. Architecture Comparison

### Before (Chroma local)
- Storage: local disk (`chroma_db/`)
- Embeddings: local Ollama embed endpoint
- Query input: precomputed query vector
- Ingestion input: precomputed document vector
- Failure domain: local process, local filesystem, local model runtime

### After (Upstash managed)
- Storage: Upstash managed serverless vector index
- Embeddings: Upstash built-in embedding model
- Query input: raw text query
- Ingestion input: raw text document
- Failure domain: network/API/auth/rate limits (instead of local embedding runtime)

### Architectural implications
- Simpler app logic (remove `get_embedding` and vector plumbing).
- Added dependency on internet and Upstash availability.
- Better portability and multi-machine consistency for indexed data.

---

## 5. API Differences and Implications

### Ingestion API mapping
- Before (Chroma):
  - `collection.add(documents=[...], embeddings=[...], ids=[...])`
- After (Upstash):
  - `index.upsert([(id, raw_text, metadata)])`

Implication:
- Remove manual embedding call.
- Metadata can store `region`, `type`, and original text if needed.

### Query API mapping
- Before (Chroma):
  - `collection.query(query_embeddings=[q_emb], n_results=3)`
- After (Upstash):
  - `index.query(data=question, top_k=3, include_metadata=True, ...)`

Implication:
- Query accepts raw text; Upstash embeds internally.
- App must parse Upstash result schema (IDs, scores, data/metadata) instead of Chroma `documents/ids` arrays.

### Auth
- Before: no external auth for local Chroma.
- After: token-based auth with Upstash REST URL + token.

Implication:
- Add startup validation for required env vars.
- Prefer least-privilege token split:
  - Read-only token for query path.
  - Full token for ingestion/admin path.

---

## 6. Detailed Implementation Plan

## Phase 0: Prerequisites
1. Ensure Upstash vector index is created with embedding model `mixedbread-ai/mxbai-embed-large-v1` and cosine similarity.
2. Ensure env vars exist:
	- `UPSTASH_VECTOR_REST_URL`
	- `UPSTASH_VECTOR_REST_TOKEN`
	- optional: `UPSTASH_VECTOR_REST_READONLY_TOKEN`
3. Install Python dependency:
	- `upstash-vector`

## Phase 1: Introduce a vector store adapter
Create a small abstraction so retrieval logic remains stable:

```python
class VectorStore:
	 def upsert_foods(self, foods: list[dict]) -> int: ...
	 def query(self, question: str, top_k: int = 3) -> list[dict]: ...
```

Implement `UpstashVectorStore` with:
- `Index(url, token)` initialization.
- `upsert` using raw text + metadata.
- `query(data=...)` and normalized return format:

```python
[
  {"id": "31", "text": "Adobo is ...", "score": 0.83, "metadata": {...}},
  ...
]
```

## Phase 2: Replace ingestion flow
1. Remove `get_embedding()` function.
2. Replace Chroma dedup logic with one of these:
	- Option A (simple): always upsert all IDs (idempotent overwrite).
	- Option B (optimized): fetch existing IDs in batches and upsert only missing.
3. Keep text enrichment strategy (`region`, `type`) but pass enriched content as raw text.

Recommended initial migration: Option A for correctness/simplicity.

## Phase 3: Replace query flow
1. Replace query embedding generation with direct Upstash text query.
2. Normalize results to same internal context format used by prompt builder.
3. Keep same `top_k=3` and same prompt template to preserve UX.

## Phase 4: Authentication and startup checks
At startup:
- Validate required env vars.
- Fail fast with clear message if missing.
- Optionally instantiate two clients:
  - ingest client with full token
  - query client with read-only token

## Phase 5: Error handling and resilience
Add robust exception handling around Upstash calls:
- Timeout handling.
- Rate limit (`429`) retry with exponential backoff + jitter.
- Transient server errors (`5xx`) retry.
- Auth errors (`401/403`) fail fast and suggest token check.
- Graceful fallback message for users when retrieval is unavailable.

## Phase 6: Validation and rollout
1. Build a fixed query regression set from README sample queries.
2. Compare top-3 retrieval relevance before vs after.
3. Compare answer quality and latency.
4. Roll out with feature flag:
	- `VECTOR_BACKEND=chroma|upstash`
5. Keep Chroma path temporarily for rollback.

---

## 7. Code Structure Changes Required

### Minimal-change approach (single file)
In `rag_run.py`:
- Remove imports:
  - `chromadb`
- Remove constants:
  - `CHROMA_DIR`, `COLLECTION_NAME`, `EMBED_MODEL`
- Add imports:
  - `from upstash_vector import Index`
  - `from dotenv import load_dotenv`
- Replace Chroma setup with Upstash `Index` setup.
- Delete `get_embedding()` function.
- Update ingestion loop to call `index.upsert(...)` with raw text.
- Update `rag_query()` to call `index.query(data=question, top_k=3, ...)`.

### Recommended maintainable approach (small refactor)
- `rag_run.py`: app orchestration and CLI loop.
- `vector_store.py`: Upstash client + ingest/query normalization.
- `llm_client.py`: Ollama generation call.
- `config.py`: env loading and validation.

Benefits:
- Easier testing.
- Cleaner backend swaps in future.
- Reduced risk when modifying retrieval layer.

---

## 8. Error Handling Strategy

### Categories
1. Configuration errors:
	- Missing/invalid URL or token env vars.
	- Strategy: fail fast at startup with actionable error text.

2. Network/timeouts:
	- Temporary connectivity issues.
	- Strategy: retries with capped exponential backoff.

3. API/auth failures:
	- 401/403 unauthorized.
	- Strategy: no retry, print clear operator guidance.

4. Rate limits:
	- 429 responses.
	- Strategy: obey retry headers when available, else backoff.

5. Partial ingestion failures:
	- Some records fail in a batch.
	- Strategy: batch-level retry + dead-letter logging of failed IDs.

### User-facing behavior
- If retrieval fails, respond with a graceful message:
  - "I could not access the knowledge index right now. Please try again shortly."
- Keep CLI interactive loop alive.

---

## 9. Performance Considerations

Expected changes:
- Ingestion latency per item may increase due to network call, but local embedding compute is removed.
- Query latency now includes network RTT + managed embedding + vector search.
- For small datasets, absolute latency should remain acceptable for CLI use.

Optimization levers:
- Batch upserts instead of per-record upserts.
- Keep `top_k` modest (3-5).
- Avoid overly long text payloads (model sequence recommendation is 512 tokens).
- Cache repeated query results for repeated questions (optional).

Quality considerations:
- Upstash model is high quality for semantic retrieval (MTEB benchmark).
- Since model differs slightly from local Ollama embedding implementation details, retrieval ranking may shift; validate with regression queries.

---

## 10. Cost Implications (Cloud vs Local)

### Local Chroma + local embeddings
- Direct cloud cost: near-zero.
- Hidden cost: local compute usage, setup friction, machine-specific persistence, maintenance.

### Upstash Vector
- Direct cost: usage-based pricing (storage, requests, vector operations/embedding operations depending on plan).
- Benefits: managed operations, no local DB hosting, easier scaling, shared data across environments.

Cost control recommendations:
- Use batch ingestion.
- Avoid unnecessary re-upserts (or rely on explicit update workflows).
- Use read-only token for query clients to reduce blast radius.
- Monitor request volume and index size from Upstash dashboard.

---

## 11. Security Considerations for API Keys

1. Never hardcode tokens in source.
2. Keep `.env` out of version control.
3. Use least privilege:
	- Read-only token for runtime query where possible.
	- Admin token only for ingestion/maintenance.
4. Rotate tokens on suspected exposure.
5. Do not log tokens or full auth headers.
6. In CI/deploy, inject secrets via environment manager, not files.
7. Add startup redaction logic for config logging.

Important:
- Treat any token that has been pasted into public channels/logs as compromised and rotate it.

---

## 12. Proposed Data Mapping in Upstash

For each food item:
- `id`: item `id`
- `data`: enriched text for semantic retrieval
- `metadata`:
  - `text`: original text
  - `region`
  - `type`

This allows:
- Strong retrieval from enriched narrative text.
- Faithful response generation using original text in prompt context.

---

## 13. Testing and Acceptance Criteria

Functional acceptance:
1. App starts successfully with Upstash config.
2. Ingestion completes without embedding API calls to Ollama.
3. Query returns top-3 relevant docs from Upstash.
4. Answer generation flow remains unchanged from user perspective.

Non-functional acceptance:
1. Error messages are actionable and non-sensitive.
2. Query p95 latency remains acceptable for CLI (< 3-5s target, environment dependent).
3. No secret leakage in logs.

Regression tests:
- Use the existing README sample queries and compare answer relevance before/after.

---

## 14. Migration Checklist

- [ ] Add `upstash-vector` and `python-dotenv` dependencies.
- [ ] Remove ChromaDB dependency from runtime path.
- [ ] Implement `UpstashVectorStore` adapter.
- [ ] Replace embedding generation with raw text upsert/query.
- [ ] Add env validation and token strategy.
- [ ] Add retry/backoff and error categorization.
- [ ] Validate retrieval quality with sample query set.
- [ ] Add backend switch flag for temporary rollback.
- [ ] Update README setup instructions.

---

## 15. Example Pseudocode (Target Retrieval Flow)

```python
load_dotenv()
index = Index(url=os.getenv("UPSTASH_VECTOR_REST_URL"), token=os.getenv("UPSTASH_VECTOR_REST_TOKEN"))

def upsert_food(item):
	 enriched = build_enriched_text(item)
	 index.upsert([(item["id"], enriched, {
		  "text": item["text"],
		  "region": item.get("region"),
		  "type": item.get("type"),
	 })])

def retrieve(question):
	 result = index.query(data=question, top_k=3, include_metadata=True)
	 docs = normalize_matches(result)
	 return docs

def rag_query(question):
	 docs = retrieve(question)
	 context = "\n".join(d["text"] for d in docs)
	 return generate_with_ollama(context, question)
```

---

## 16. Risks and Mitigations

1. Retrieval ranking shifts after embedding model/provider change.
	- Mitigation: regression test set, tune enrichment text and top_k.

2. Cloud dependency/network outages.
	- Mitigation: retries, graceful errors, optional cached fallback responses.

3. Unexpected cost growth with request volume.
	- Mitigation: monitor usage, reduce duplicate upserts, tune batch cadence.

4. Token leakage risk.
	- Mitigation: strict secret handling, rotation policy, least privilege.

---

## 17. Recommended Next Step

Implement the migration behind a backend flag (`VECTOR_BACKEND=upstash`) so Chroma can remain as a short-term fallback during validation.
# PRD: Migrate Local Ollama LLM to Groq Cloud API

## 1. Objective

Replace the current local Ollama `llama3.2` generation call with the Groq Cloud API using `llama-3.1-8b-instant`, keeping the same RAG behavior, prompt structure, and user-facing CLI experience.

Goals:
- Remove dependency on locally running Ollama process.
- Reduce generation latency (Groq runs inference on custom LPU hardware, typically faster than local CPU/GPU inference).
- Enable usage from any machine without model setup.

Non-goals:
- Changing the vector retrieval layer (covered separately in `upstash-migration-prd.md`).
- Enabling streaming responses (out of scope for this migration).
- Switching to a different LLM family.

---

## 2. Current State (Before)

In `rag_run.py`:

```python
LLM_MODEL = "llama3.2"

response = requests.post("http://localhost:11434/api/generate", json={
    "model": LLM_MODEL,
    "prompt": prompt,
    "stream": False
})
return response.json()["response"].strip()
```

Pipeline:
1. Build context from ChromaDB top-3 docs.
2. Construct prompt string (context + question).
3. POST to `localhost:11434/api/generate` with raw prompt string.
4. Extract answer from `response.json()["response"]`.

Pain points:
- Ollama must be installed, running, and have `llama3.2` pulled locally.
- Inference speed varies by local hardware.
- Cannot run the app in environments without a GPU/Ollama installation.
- Local process management is a hidden operational dependency.

---

## 3. Target State (After)

```python
import os
from groq import Groq

LLM_MODEL = "llama-3.1-8b-instant"
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

def generate_answer(prompt: str) -> str:
    chat_completion = groq_client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=LLM_MODEL,
    )
    return chat_completion.choices[0].message.content.strip()
```

Pipeline:
1. Build context from vector store top-3 docs.
2. Construct same prompt string (context + question).
3. POST to Groq's chat completions endpoint via official SDK.
4. Extract answer from `choices[0].message.content`.

Result:
- No local Ollama process required.
- No local model download required.
- Groq LPU inference (low latency, typically faster than local).
- Same prompt structure and answer quality tier (Llama 3.1 8B ≈ Llama 3.2).

---

## 4. Architecture Comparison

### Before (Local Ollama)

```
User input
  → Embed question (Ollama embed)
  → ChromaDB query
  → Build prompt
  → POST localhost:11434/api/generate (Ollama generate)
  → Print answer
```

Dependency chain: Python → Ollama process → local model weights

### After (Groq Cloud)

```
User input
  → Embed question (Upstash or Ollama embed)
  → Vector DB query
  → Build prompt
  → Groq SDK → api.groq.com/openai/v1/chat/completions
  → Print answer
```

Dependency chain: Python → Groq SDK → Groq API (network)

### Key architectural shifts

| Dimension          | Before (Ollama)               | After (Groq)                       |
|--------------------|-------------------------------|------------------------------------|
| Hosting            | Local machine                 | Groq Cloud (managed)               |
| Request format     | Raw prompt string             | OpenAI-compatible chat messages    |
| Auth               | None (localhost)              | Bearer token via `GROQ_API_KEY`    |
| Response key       | `response.json()["response"]` | `choices[0].message.content`       |
| Setup per machine  | Install Ollama + pull model   | Set env var                        |
| Speed              | Varies by local hardware      | Consistent low-latency LPU         |
| Cost               | Compute electricity cost      | Usage-based (tokens in/out)        |

---

## 5. API Differences and Implications

### Request format change

**Before (Ollama generate API):**
```python
requests.post("http://localhost:11434/api/generate", json={
    "model": "llama3.2",
    "prompt": "Use the following context...\n\nQuestion: ...\nAnswer:",
    "stream": False
})
```
- Single `prompt` field with the full instruction block.
- Ollama-specific endpoint and schema.

**After (Groq / OpenAI chat completions):**
```python
groq_client.chat.completions.create(
    messages=[{"role": "user", "content": "Use the following context...\n\nQuestion: ...\nAnswer:"}],
    model="llama-3.1-8b-instant",
)
```
- Messages array with role/content objects.
- Same prompt text moves into `content` of the user message.
- No changes needed to the prompt template itself.

### Response format change

**Before:**
```python
response.json()["response"].strip()
```

**After:**
```python
chat_completion.choices[0].message.content.strip()
```

### Authentication change

**Before:** No auth (local endpoint).

**After:**
- Groq SDK reads `GROQ_API_KEY` from environment automatically when you pass it via `Groq(api_key=os.environ["GROQ_API_KEY"])`.
- Never hardcode the key in source code.

---

## 6. Detailed Implementation Plan

### Phase 0: Prerequisites

1. Install the Groq Python SDK:
   ```
   pip install groq
   ```
2. Ensure `GROQ_API_KEY` is set in `.env`.
3. Ensure `python-dotenv` is installed so `.env` is loaded at startup:
   ```
   pip install python-dotenv
   ```

### Phase 1: Add environment loading

At the top of `rag_run.py`, add:
```python
from dotenv import load_dotenv
load_dotenv()
```
This must run before any `os.environ` access.

### Phase 2: Replace Ollama generation call

1. Remove:
   - `LLM_MODEL = "llama3.2"` constant.
   - The `requests.post("http://localhost:11434/api/generate", ...)` block.
   - `response.json()["response"].strip()` extraction.

2. Add:
   ```python
   from groq import Groq

   LLM_MODEL = "llama-3.1-8b-instant"
   groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
   ```

3. Replace the generation logic in `rag_query()`:
   ```python
   chat_completion = groq_client.chat.completions.create(
       messages=[{"role": "user", "content": prompt}],
       model=LLM_MODEL,
   )
   return chat_completion.choices[0].message.content.strip()
   ```

### Phase 3: Startup validation

Add a config check at startup to catch missing credentials early:
```python
required_env = ["GROQ_API_KEY"]
for var in required_env:
    if not os.environ.get(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")
```
This prevents confusing runtime auth failures mid-query.

### Phase 4: Error handling

Wrap generation calls to handle Groq-specific exceptions:
```python
from groq import APIError, AuthenticationError, RateLimitError

try:
    chat_completion = groq_client.chat.completions.create(...)
except AuthenticationError:
    print("❌ Groq authentication failed. Check your GROQ_API_KEY.")
except RateLimitError:
    print("⏳ Groq rate limit reached. Please wait before retrying.")
except APIError as e:
    print(f"⚠️ Groq API error: {e}. Try again shortly.")
```

### Phase 5: Validation

Use the 10 sample queries from the README and compare:
- Response relevance before (Ollama) vs after (Groq).
- Response latency.
- Any answer format regressions.

Groq's Llama 3.1 8B is architecturally equivalent to Llama 3.2; answers should remain comparable in quality.

---

## 7. Code Structure Changes Required

### Minimal-change approach (single file)

Changes to `rag_run.py`:

| Action  | Target                                            |
|---------|---------------------------------------------------|
| Remove  | `LLM_MODEL = "llama3.2"`                         |
| Remove  | `requests.post(...api/generate...)` block         |
| Remove  | `response.json()["response"].strip()`             |
| Add     | `from groq import Groq`                           |
| Add     | `from dotenv import load_dotenv; load_dotenv()`   |
| Add     | `groq_client = Groq(api_key=os.environ[...])`     |
| Add     | `LLM_MODEL = "llama-3.1-8b-instant"`             |
| Replace | Generation call with `groq_client.chat.completions.create(...)` |
| Replace | Response extraction with `choices[0].message.content.strip()` |

Note: The `requests` import can be removed entirely if Ollama embedding is also migrated (as planned in `upstash-migration-prd.md`). If Ollama embedding is still in use during interim, keep `requests`.

### Recommended maintainable approach

Introduce a `llm_client.py` module:
```python
# llm_client.py
import os
from groq import Groq, APIError, AuthenticationError, RateLimitError

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
MODEL = "llama-3.1-8b-instant"

def generate(prompt: str) -> str:
    try:
        completion = _client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=MODEL,
        )
        return completion.choices[0].message.content.strip()
    except AuthenticationError:
        raise RuntimeError("Invalid GROQ_API_KEY.")
    except RateLimitError:
        raise RuntimeError("Groq rate limit reached.")
    except APIError as e:
        raise RuntimeError(f"Groq API error: {e}")
```

`rag_run.py` then calls:
```python
from llm_client import generate
answer = generate(prompt)
```

Benefits: isolated, testable, swappable.

---

## 8. Error Handling Strategy

| Error Class         | Trigger                        | Strategy                                      |
|---------------------|--------------------------------|-----------------------------------------------|
| `EnvironmentError`  | Missing `GROQ_API_KEY` at boot | Fail fast with clear message before any I/O   |
| `AuthenticationError` | Invalid or expired key        | No retry; print rotation guidance             |
| `RateLimitError`    | Token/request quota exceeded   | Exponential backoff, notify user to wait      |
| `APIError` (5xx)    | Groq service issue             | Retry up to 3 times with backoff              |
| `APIError` (4xx)    | Bad request (too-long prompt)  | Log prompt length, trim context, retry once   |
| `requests.Timeout`  | Network timeout                | Retry once; fail gracefully                   |
| General `Exception` | Unexpected failure             | Catch-all; display safe message, keep CLI up  |

### User-facing messages

All error messages must:
- Never expose the API key or internal paths.
- Provide actionable guidance (e.g., "check your API key", "retry in a moment").
- Not crash the interactive loop; allow the user to ask another question.

---

## 9. Performance Considerations

### Latency

- Groq's LPU hardware is specifically designed for transformer inference and is typically 5–10× faster than CPU-based local inference.
- Expect token generation latency of ~150–300ms for this model/prompt size.
- Network RTT adds ~50–150ms overhead but is offset by faster inference.

### Context window

- `llama-3.1-8b-instant` context window: 128k tokens.
- Current prompt is well within limits (3 retrieved docs + question).

### Token budgeting

- Current average prompt: ~200–400 tokens (3 short food descriptions + question).
- Expected output: ~100–300 tokens.
- Very low per-query token cost.

### Prompt safety

- Avoid sending very long prompts if food descriptions grow. Keep `top_k=3`.
- Trim enriched text if it exceeds ~300 tokens per doc to avoid edge-case 4xx errors.

---

## 10. Cost Implications

### Local Ollama

- No cloud API cost.
- Runs on local hardware (CPU/GPU electricity cost, hardware wear).
- Requires setup time per machine.

### Groq Cloud

- Usage-based: charged per million input/output tokens.
- `llama-3.1-8b-instant` is among the lowest-cost models on Groq.
- For this food RAG app:
  - Average prompt: ~300 tokens in, ~200 tokens out.
  - At 1,000 queries/month: negligible cost (fraction of $1).
- Free tier is available for development and low-volume testing.

### Cost control measures

- Use the smallest effective model (`llama-3.1-8b-instant`).
- Keep `top_k=3` and short enriched docs to minimize input tokens.
- Add a query character limit in the CLI to prevent excessively long prompts.
- Monitor usage in the Groq console dashboard.

---

## 11. Security Considerations

1. Never commit `GROQ_API_KEY` to source control.
2. Ensure `.env` is listed in `.gitignore`.
3. Do not print or log `os.environ["GROQ_API_KEY"]` anywhere.
4. Treat the key in `.env` as a secret on par with a database password.
5. Rotate the key immediately if it appears in logs, error output, or is shared.
6. In deployment, prefer injecting secrets through environment variables at runtime, not file-based `.env`.
7. Groq API keys can be scoped or revoked from the Groq console — prefer short-lived keys for CI pipelines.

---

## 12. Testing and Acceptance Criteria

### Functional acceptance

1. App starts with valid `GROQ_API_KEY` and no Ollama process running.
2. Ingestion flow is unaffected (generation is not involved in ingestion).
3. `rag_query()` returns a coherent, relevant answer from Groq.
4. Error conditions (bad key, rate limit, network down) produce safe, readable messages without crashing the CLI loop.

### Non-functional acceptance

1. First-answer latency is perceptibly faster than local Ollama on CPU.
2. No API key or sensitive data appears in stdout or stderr.
3. App behaves correctly when `GROQ_API_KEY` is missing (fail-fast error on startup).

### Regression test set

Run all 10 README sample queries and verify answers remain contextually relevant:

| Query | Expected context                                  |
|-------|---------------------------------------------------|
| What is Adobo? | Filipino dish, vinegar, soy sauce, garlic |
| Which foods are high in protein? | Lentils, Salmon                 |
| Tell me about Filipino foods | Sinigang, Adobo, Lechon              |
| What vegan options are available? | Lentils, Kale, Avocado           |
| What foods can be grilled? | Chicken, grilled meats                  |
| What is Sinigang? | Sour tamarind-based Filipino soup             |
| What are healthy gluten-free foods? | Lentils, Quinoa, Kale          |
| Tell me about Spanish cuisine | Paella, Spanish food culture           |
| What is Halo-Halo? | Filipino dessert, crushed ice, mixed sweets  |
| What international dishes use rice? | Nasi Lemak, Paella, Pad Thai  |

---

## 13. Migration Checklist

- [ ] Install `groq` Python package.
- [ ] Install `python-dotenv` if not present.
- [ ] Confirm `GROQ_API_KEY` is in `.env` and `.env` is in `.gitignore`.
- [ ] Add `load_dotenv()` call at top of `rag_run.py`.
- [ ] Add startup env validation for `GROQ_API_KEY`.
- [ ] Replace `LLM_MODEL` constant.
- [ ] Remove Ollama generation `requests.post` call.
- [ ] Add Groq client initialization.
- [ ] Replace generation call with `groq_client.chat.completions.create(...)`.
- [ ] Replace response extraction with `choices[0].message.content`.
- [ ] Add error handling for `AuthenticationError`, `RateLimitError`, `APIError`.
- [ ] Run regression queries from README.
- [ ] Remove `requests` import if Ollama embedding is also migrated (Upstash PRD).
- [ ] Update README setup instructions to remove Ollama model pull requirement.

---

## 14. Interaction with Upstash Migration

If both this migration and the Upstash Vector migration (`upstash-migration-prd.md`) are implemented together:

- The `requests` library can be removed entirely — no more Ollama calls anywhere.
- The `EMBED_MODEL` constant and `get_embedding()` function are also removed.
- Only two external dependencies remain at runtime:
  - `groq` (LLM generation)
  - `upstash-vector` (vector retrieval)
- Both are cloud-hosted with API key auth loaded from `.env`.

Full combined removal list from `rag_run.py`:
- `import chromadb`
- `import requests`
- `CHROMA_DIR`, `COLLECTION_NAME`, `EMBED_MODEL`, `LLM_MODEL = "llama3.2"`
- `get_embedding()` function
- ChromaDB client and collection setup
- Ollama embed and generate `requests.post` calls

---

## 15. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Groq outage or degraded service | Retry with backoff; clear user message; optional fallback to Ollama if available |
| API key expiry or revocation | Fail-fast at startup with rotation guidance |
| Rate limiting during bulk testing | Add delay between regression queries |
| Answer quality regression vs Llama 3.2 | Regression test set; models are architecturally equivalent |
| Unexpected token cost spike | Monitor Groq console; add input length guard |
| `.env` key accidentally committed | Ensure `.gitignore` is correct before first commit |

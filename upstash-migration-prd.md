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

# Retrieval pipeline for a Vietnamese legal RAG system (Law + Decrees + Circulars), state as of 2026-11-22

Scope: parsing, chunking, embedding, indexing, hybrid search, reranking, query processing and citation for interlinked Vietnamese legal documents. Stack constraints: Supabase Postgres + pgvector (free tier, 500 MB), FastAPI on Vercel (no ML models), embedding and reranker on a Kaggle T4 behind a tunnel, ingestion offline.

Labels used below: **[verified]** means fetched this session. **[prior knowledge]** means from training data, not re-fetched; verify before relying on it. **[older]** means the source predates 2026.

---

## 1. Best open Vietnamese embedding models (2025-2026), with evidence

### Takeaway
Fine-tuned Vietnamese models beat stock BGE-M3 and multilingual-e5 by a wide margin on Zalo legal retrieval. Two 2025-2026 candidates fit a T4 and pgvector's HNSW limit without truncation (both 1024-d): **`AITeamVN/Vietnamese_Embedding`** (BGE-M3 fine-tune, 2048 tokens, no prefix) and **`mainguyen9/vietlegal-harrier-0.6b`** (fine-tune of Microsoft Harrier-OSS-v1-0.6B on about 500K Vietnamese legal chunks, NDCG@10 0.781 on ZacLegal). Their reported numbers use different metrics and splits, so neither can be ranked above the other from the model cards. A/B them on your own corpus.

### Cited Findings
- **AITeamVN/Vietnamese_Embedding** [verified]: base `BAAI/bge-m3`, 1024-d, max_seq_length 2048, dot-product similarity, trained on about 300K Vietnamese (query, pos, neg) triplets, Apache-2.0, citation year 2025. The usage example passes raw Vietnamese text (no word segmentation shown). — [HF model card](https://huggingface.co/AITeamVN/Vietnamese_Embedding)
- Same card, evaluated on the Legal Zalo 2021 **training set** (the card says the model was not trained on it). [verified]

  | Model | Acc@1 | Acc@3 | Acc@5 | Acc@10 | MRR@10 |
  |---|---|---|---|---|---|
  | AITeamVN Vietnamese_Reranker | 0.7944 | 0.9324 | 0.9537 | 0.9740 | 0.8672 |
  | Vietnamese_Embedding_v2 | 0.7262 | 0.8927 | 0.9268 | 0.9578 | 0.8149 |
  | Vietnamese_Embedding (public) | 0.7274 | 0.8992 | 0.9305 | 0.9568 | 0.8181 |
  | bkai vietnamese-bi-encoder | 0.7109 | 0.8680 | 0.9014 | 0.9299 | 0.7951 |
  | BGE-M3 | 0.5682 | 0.7728 | 0.8382 | 0.8921 | 0.6822 |

  — [HF model card](https://huggingface.co/AITeamVN/Vietnamese_Embedding)
- v2 (subfolder of the same repo) was trained on 1.1M triplets. It is slightly worse on legal (Acc@1 0.7262 vs 0.7274) but the card says it is better in other domains. — [HF model card](https://huggingface.co/AITeamVN/Vietnamese_Embedding)
- **mainguyen9/vietlegal-harrier-0.6b** [verified]: fine-tuned from `microsoft/harrier-oss-v1-0.6b`, 1024-d, cosine with L2-normalised output, **max 512 tokens**, Apache-2.0, citation year 2026. Training data: 518K legal documents (`th1nhng0/vietnamese-legal-documents`) split into about 500K **article-aware chunks**, plus 507K query-passage pairs (`phamson02/large-vi-legal-queries`), then a 70/20/10 retrieval/classification/STS multi-task stage. Queries need the prefix `Instruct: Given a Vietnamese legal question, retrieve relevant legal passages that answer the question\nQuery: `; passages take no prefix. — [HF model card](https://huggingface.co/mainguyen9/vietlegal-harrier-0.6b)
- ZacLegalTextRetrieval (MTEB task, **818 test queries**), NDCG@10 / MRR@10 / Recall@10: vietlegal-harrier-0.6b 0.7813 / 0.7303 / 0.9321; vietlegal-e5 (mE5-large FT) 0.7310; vietlegal-harrier-270m 0.7174; microsoft/harrier-oss-v1-0.6b 0.7210; intfloat/multilingual-e5-large 0.6660; bkai vietnamese-bi-encoder 0.6160; contextboxai/halong_embedding 0.6009. [verified] — [HF model card](https://huggingface.co/mainguyen9/vietlegal-harrier-0.6b)
- **darklethelong/vnlegal-lal** reports NDCG@10 **0.8488**, MRR@10 0.7993 and Recall@10 0.9772 on the same task. It is vietlegal-harrier-0.6b further trained with 3 rounds of ANCE hard-negative mining plus LoRA **on the Zalo training queries themselves** (`GreenNode/zalo-ai-legal-text-retrieval-vn`, about 2.4K train queries). 2048 max tokens, last-token pooling, Apache-2.0. [verified] — [HF model card](https://huggingface.co/darklethelong/vnlegal-lal)
- **microsoft/harrier-oss-v1** family [verified]: multilingual (94 languages, Vietnamese included), decoder-only (tagged qwen3), sizes 270M (640-d), 0.6B (1024-d) and 27B (5376-d), 32,768-token context, last-token pooling + L2 norm, MIT license. Multilingual MTEB v2: 66.5 (270M), 69.0 (0.6B), 74.3 (27B). Queries use `Instruct: {task}\nQuery: {query}`. Matryoshka support is not mentioned. — [HF model card](https://huggingface.co/microsoft/harrier-oss-v1-0.6b)
- **Qwen/Qwen3-Embedding-0.6B** [verified]: 1024-d with **MRL output dims 32-1024**, 32K context, Apache-2.0, needs transformers ≥ 4.51.0. MTEB Multilingual mean (task): 0.6B 64.33, 4B 69.45, 8B 70.58. Instructions give "typically" 1-5% gain and the card recommends writing them in English. — [HF model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- No published Qwen3-Embedding score on ZacLegalTextRetrieval was found. — [search result summary, no source found]
- **VN-MTEB** (arXiv 2507.21500, Jul 2025): 41 datasets, 6 tasks (retrieval, classification, pair-classification, clustering, reranking, STS), 18 models evaluated. The data is LLM-translated from MTEB. Finding: "bigger and more complex models using Rotary Positional Embedding outperform" models with absolute positional embeddings. The abstract names no top model. — [arXiv](https://arxiv.org/abs/2507.21500)
- The ZacLegalTextRetrieval eval set is on HF as `GreenNode/zalo-ai-legal-text-retrieval-vn` (61.4K corpus documents, 818 test queries). — [HF dataset](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn)
- A Sep-2026 paper on cross-lingual (English→Vietnamese) labour-law QA found dense retrieval strongest (R@5 0.358). Learned-sparse failed cross-lingually (R@5 0.032), and dense "slightly outperforms hybrid". Model IDs are not in the abstract. — [arXiv 2609.27376](https://arxiv.org/abs/2609.27376)
- pgvector HNSW indexes `vector` up to **2,000 dims** and `halfvec` up to **4,000 dims**. Storage is `4*d+8` bytes (vector) and `2*d+8` bytes (halfvec). An expression index can cast: `CREATE INDEX ON items USING hnsw ((embedding::halfvec(3)) halfvec_l2_ops);` — [pgvector README](https://github.com/pgvector/pgvector)

### Inferences
- **Recommendation: default to `AITeamVN/Vietnamese_Embedding`** for these reasons:
  - It takes raw text with no prefix, so the same encode call serves docs and queries.
  - Its 2048-token window holds a whole Điều.
  - It is BGE-M3-based and well-trodden.
- **A/B against `mainguyen9/vietlegal-harrier-0.6b`**, which is trained on far more legal data. Its 512-token limit means child chunks must stay ≤ 512 tokens.
- Do not choose `vnlegal-lal` on its 0.849: it was trained on the benchmark's own train queries, so its lead is partly in-distribution.
- All three candidates are 1024-d (no Matryoshka needed). Store as `halfvec(1024)`: 2,056 B/row vs 4,104 B for `vector(1024)`. That halves the storage that counts against the 500 MB free tier, and halfvec(1024) is far under the 4,000-d HNSW limit.
- Rough storage for 30K chunks: 30K × 2 KB ≈ 62 MB of vectors, plus an HNSW index of similar magnitude, plus text and tsvector. That sits comfortably below 500 MB. The HNSW-size-equals-data-size assumption is [prior knowledge]; check with `pg_relation_size` after the first load.
- If you need a larger model: Qwen3-Embedding-4B (2560-d) or 8B (4096-d) exceed the 2,000-d vector limit. Use the MRL truncation to ≤ 2,000 (Qwen3 supports 32-1024 for 0.6B; for 4B/8B check the card), or use halfvec (≤ 4,000). On a T4 with 16 GB, the 0.6B-class models are the realistic choice while the same GPU also serves the LLM. [inference]
- All candidates fit a T4 in fp16. BGE-M3 is about 568M params (the parameter count is [prior knowledge]); Harrier-0.6B and Qwen3-0.6B are about 0.6B. T4 has no bf16, so load with `torch_dtype=float16`. [prior knowledge]
- Older options are dominated on ZacLegal: `bkai-foundation-models/vietnamese-bi-encoder` (needs pyvi word segmentation, 256-token limit, PhoBERT-based) and `dangvantuan/vietnamese-embedding`. The segmentation and token-limit details are [prior knowledge, older]. jina-embeddings-v3/v4 (v3 is CC-BY-NC, [prior knowledge]) have no Vietnamese legal evidence found and carry licensing friction, so skip them.

### Gaps
- No single leaderboard evaluates AITeamVN, vietlegal-harrier, Qwen3-Embedding, gte-multilingual and jina-v3/v4 on the same Vietnamese legal split. The VN-MTEB per-model table was not retrieved; only the abstract was read.
- The Harrier-OSS-v1 release date and whether it supports Matryoshka truncation were not stated on the card.
- Whether the AITeamVN fine-tune keeps a usable BGE-M3 sparse/ColBERT head is unknown; the card shows dense usage only.

---

## 2. Best rerankers for Vietnamese

### Takeaway
**`AITeamVN/Vietnamese_Reranker`** has the only Vietnamese-legal evidence found. On the same Zalo eval it lifts Acc@1 from 0.727 (best embedding) to 0.794 and MRR@10 from 0.818 to 0.867. Use it as default, with `BAAI/bge-reranker-v2-m3` as fallback. Qwen3-Reranker is stronger on vendor multilingual benchmarks but has no Vietnamese-legal number.

### Cited Findings
- Vietnamese_Reranker on Legal Zalo 2021 train set [verified]: Acc@1 0.7944, Acc@3 0.9324, Acc@5 0.9537, Acc@10 0.9740, MRR@10 0.8672. It was trained on the same 1.1M triplets as Embedding_v2. — [AITeamVN Vietnamese_Embedding card](https://huggingface.co/AITeamVN/Vietnamese_Embedding)
- Qwen's vendor table: bge-reranker-v2-m3 scores 57.03 MTEB-R and 58.36 MMTEB-R, vs Qwen3-Reranker-4B at 69.76 and 72.74 (self-reported). — [search summary of Qwen blog](https://qwen.ai/blog?id=qwen3-embedding)
- One third-party latency benchmark: bge_reranker_v2_m3 at 527 ms vs qwen3_reranker_0.6b at 445 ms per rerank call. Hardware and batch context are unclear. — [AIMultiple reranker benchmark](https://aimultiple.com/rerankers)
- **ViRanker** (arXiv 2509.09131, Sep 2025) is a BGE-M3 + blockwise-parallel-transformer cross-encoder for Vietnamese. It is evaluated on MMARCO-VI (general domain), beats multilingual baselines and is close to PhoRanker. No comparison to bge-reranker-v2-m3 or Qwen3-Reranker was found in the summary. — [arXiv](https://arxiv.org/pdf/2509.09131)
- Sources disagree on the bge-reranker-v2-m3 license (Apache-2.0 vs MIT). Check the model card. — [search summary](https://reranker.uk/guides/compare-rerankers)
- Anthropic: adding reranking on top of contextual embeddings and contextual BM25 cut top-20 retrieval failure from 2.9% to 1.9%. Passing **20 chunks** to the generator beat 5 or 10. — [Anthropic Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)

### Inferences
- Default: `AITeamVN/Vietnamese_Reranker`. Its architecture is likely a bge-reranker-v2-m3 fine-tune, since it is the same team and data pipeline [inference; card not fetched].
- Rerank the **top 30-50 fused candidates** down to **top 5-8 parent passages** for the LLM. With legal parents (whole Điều, up to about 2K tokens), 20 chunks would blow the context of a small Kaggle-hosted LLM, so use fewer and larger units. [inference]
- Run the reranker as a separate endpoint `/rerank` on the Kaggle notebook (sentence-transformers `CrossEncoder` or FlagEmbedding `FlagReranker(use_fp16=True)`). Truncate pairs to max_length 512-1024 to bound T4 latency. [inference]
- Qwen3-Reranker-0.6B is a reasonable second A/B candidate. It is an LLM-style reranker (yes/no logits) and needs transformers ≥ 4.51 [prior knowledge].
- jina-reranker-v2 has a non-commercial (CC-BY-NC) license [prior knowledge], so skip it.

### Gaps
- No head-to-head Vietnamese legal benchmark compares Vietnamese_Reranker, bge-reranker-v2-m3, Qwen3-Reranker and jina-reranker-v3.
- T4 latency per 40 pairs is unmeasured; benchmark it in the notebook.

---

## 3. Vietnamese word segmentation, lexical search in Postgres, and hybrid RRF on Supabase

### Takeaway
On Supabase free tier, the pragmatic lexical leg is **Postgres built-in FTS with the `'simple'` config**, with three adjustments:
- Vietnamese syllables are space-delimited, so `simple` works at syllable level, and phrase operators recover multi-syllable words.
- Use OR-semantics plus query-side stopword removal; the default AND semantics returns nothing for long questions.
- Match document numbers and article numbers on exact metadata columns rather than FTS.

ParadeDB `pg_search` is **not** a native Supabase extension. Word segmentation is unnecessary for the recommended embedders and optional for FTS. Fuse the legs with **Supabase's RRF `hybrid_search` pattern**.

### Cited Findings
- Supabase hybrid-search reference pattern [verified]:
  - The table has `fts tsvector generated always as (to_tsvector('english', content)) stored`, a GIN index on `fts`, and HNSW on `embedding vector_ip_ops`.
  - The function `hybrid_search(query_text, query_embedding, match_count, full_text_weight=1, semantic_weight=1, rrf_k=50)` builds two CTEs:
    - `full_text`: `row_number() over (order by ts_rank_cd(fts, websearch_to_tsquery(query_text)) desc)`, filtered by `fts @@ websearch_to_tsquery(query_text)`.
    - `semantic`: `row_number() over (order by embedding <#> query_embedding)`.
  - Each CTE is limited to `least(match_count,30)*2`. The CTEs are full-outer-joined and ordered by `coalesce(1.0/(rrf_k+ft.rank_ix),0)*full_text_weight + coalesce(1.0/(rrf_k+sem.rank_ix),0)*semantic_weight`. Output is capped at 30.
  - The page notes that `ts_rank_cd` is not indexable but only ranks rows matching the WHERE clause.

  — [Supabase Hybrid Search docs](https://supabase.com/docs/guides/ai/hybrid-search)
- In that sample the query side calls `websearch_to_tsquery(query_text)` with no config, so it falls back to `default_text_search_config`. Pass the config explicitly on both sides. — [Supabase Hybrid Search docs](https://supabase.com/docs/guides/ai/hybrid-search)
- ParadeDB on Supabase is documented as a **separate** search replica synced via logical replication, not an in-database extension. — [Supabase ParadeDB partner page](https://supabase.com/partners/integrations/paradedb)
- pg_search is deprecated on Neon (new installs blocked, removal in Sep 2026). Tiger Data's `pg_textsearch` (true BM25, Postgres license) hit v1.0 on 2026-04-03 but needs `shared_preload_libraries`. One listing says that limits it on managed Postgres including Supabase. — [PostgreSQL news](https://www.postgresql.org/about/news/pg_textsearch-v10-3264); [Neon docs](https://neon.com/docs/extensions/migrate-pg-search-to-lakebase-text.md); [awesome-search](https://frutik.github.io/awesome-search/Tools/pg_textsearch)
- Supabase ships "over 50 extensions", most installed under the `extensions` schema. Check with `select * from pg_available_extensions;`. — [Supabase extensions docs](https://supabase.com/docs/guides/database/extensions)
- pgvector `sparsevec`: storage up to 16,000 non-zero elements; **HNSW indexes sparsevec only up to 1,000 non-zero elements**; IVFFlat does not support sparsevec. — [pgvector README](https://github.com/pgvector/pgvector)
- In a cross-lingual Vietnamese legal setting, learned-sparse retrieval performed poorly and hybrid was slightly worse than dense alone. — [arXiv 2609.27376](https://arxiv.org/abs/2609.27376)
- A KG-RAG paper on three Vietnamese law domains reports a plain BM25 baseline at 62.3% answer accuracy, vs 85.7% for its graph-aware hybrid. — [DST journal, Jan 2026](https://dsjournals.com/dst/DST-V5I1P101)

### Inferences
- **Word segmentation (underthesea / pyvi / VnCoreNLP)** is needed only for PhoBERT-based bi-encoders such as `bkai-foundation-models/vietnamese-bi-encoder`, which expects pyvi-segmented input [prior knowledge]. AITeamVN (XLM-R tokenizer), Harrier and Qwen3 all take raw text, so skip segmentation in the embedding path.
- For FTS you can skip segmentation too. Use syllable-level `simple` tokens. In `websearch_to_tsquery('simple','"thời hiệu khởi kiện"')`, the quoted phrase becomes `thời <-> hiệu <-> khởi <-> kiện` [prior knowledge], which recovers word-level precision.
- Avoid VnCoreNLP: it needs Java, so it cannot run on Vercel.
- **Critical gotcha:** `websearch_to_tsquery`/`plainto_tsquery` AND all terms [prior knowledge]. A 15-syllable Vietnamese question will almost never match a chunk. Build the lexical query in FastAPI:
  1. Unicode NFC-normalise and lowercase.
  2. Drop a small Vietnamese stopword list (`của, và, là, các, những, được, theo, cho, có, không, thì, này, ...`).
  3. Keep quoted phrases.
  4. OR the rest: `to_tsquery('simple', 'thời <-> hiệu | khởi <-> kiện | lao <-> động')`. A cruder option is `replace(plainto_tsquery('simple', q)::text, ' & ', ' | ')::tsquery`.

  `ts_rank_cd` then rewards chunks matching more terms with proximity. It has no IDF [prior knowledge], which is why stopword removal matters.
- **Exact identifiers** (`15/2020/NĐ-CP`, `Điều 12`, `khoản 3`) should not rely on FTS: the default parser may split slashes and hyphens unpredictably [prior knowledge]. Instead:
  - regex-extract them from the query in FastAPI;
  - apply them as filters or boosts on `legal_docs.doc_number`, `chunks.article` and `chunks.clause`.
- **unaccent:** keep diacritics in the primary index, because unaccenting merges distinct Vietnamese words (ba/bà/bá/bả). If users type without diacritics, add a second tsvector built with an `IMMUTABLE` wrapper around `unaccent()` and query it only when the query has no diacritics. `unaccent()` itself is not immutable, so it cannot be used directly in a generated column [prior knowledge].
- **pg_trgm** is useful for fuzzy title or doc-number lookup (`similarity(title, q)`), not as the main lexical ranker. [inference]
- **BGE-M3 sparse vectors in `sparsevec(250002)`** (XLM-R vocab size [prior knowledge]) are feasible and give a learned lexical leg with IDF-like weights. Costs:
  - The FlagEmbedding sparse head runs on Kaggle at ingest and at query time.
  - The fine-tuned AITeamVN model may not carry a trained sparse head.
  - Chunks with more than 1,000 non-zero tokens cannot be HNSW-indexed (exact scan over a small corpus is fine).

  Treat it as an optional experiment, not the default. [inference]
- **RRF defaults:** `rrf_k = 50`, which is Supabase's default (the original RRF paper used 60 [prior knowledge]). Start with weights full_text 1.0 / semantic 1.0. Raise `full_text_weight` to about 1.5 when the query contains a document number or article reference. Remove the hard `least(match_count, 30)` cap so 40-50 candidates reach the reranker. Add metadata filters (`status`, `doc_type`).
- For filtered vector search, `SET hnsw.iterative_scan = relaxed_order` (pgvector ≥ 0.8.0) avoids empty results under selective filters. Use `hnsw.ef_search` 100 (default 40). [pgvector README](https://github.com/pgvector/pgvector)

### Gaps
- The pgvector version on Supabase as of Nov 2026 (iterative scan needs ≥ 0.8.0; latest upstream is 0.8.7) was not confirmed. Run `select extversion from pg_extension where extname='vector';`.
- Whether Supabase now allowlists `pg_textsearch` or `pg_search` was not confirmed.
- I found no Vietnamese-specific evaluation of Postgres `simple` FTS against BM25 with word segmentation.

---

## 4. Chunking Vietnamese legal and structured documents

### Takeaway
Chunk by legal structure: **Điều = parent unit, Khoản = child retrieval unit**, splitting further by Điểm only when a Khoản exceeds about 400-500 tokens. Prepend a **deterministic breadcrumb header** to every child before embedding and FTS:
- document type, number and title;
- Chương and Mục;
- Điều number and title.

This header is a free, rule-based version of Anthropic's Contextual Retrieval. Retrieve children and return parents (small-to-big). Store document metadata (number, type, issuer, issued and effective dates, effect status) in a separate table and filter on it.

### Cited Findings
- Anthropic Contextual Retrieval: prepend 50-100 tokens of chunk-specific context before embedding **and** BM25 indexing. Results on top-20 failure rate:
  - contextual embeddings alone: 5.7% → 3.7% (-35%);
  - plus contextual BM25: 2.9% (-49%);
  - plus reranking: 1.9% (-67%).

  The prompt template takes `<document>{{WHOLE_DOCUMENT}}</document><chunk>{{CHUNK_CONTENT}}</chunk>` with the instruction "Please give a short succinct context to situate this chunk within the overall document ... Answer only with the succinct context and nothing else." The cost example assumes 800-token chunks and 8K-token docs (about $1.02 per M doc tokens with prompt caching). For knowledge bases under about 200K tokens (about 500 pages), it suggests skipping RAG and putting everything in the prompt. — [Anthropic](https://www.anthropic.com/news/contextual-retrieval)
- vietlegal-harrier was trained on about 500K **article-aware chunks** of Vietnamese legal documents with a 512-token max, which shows the Vietnamese legal-retrieval community chunks at article level. — [HF card](https://huggingface.co/mainguyen9/vietlegal-harrier-0.6b)
- A Vietnamese legal KG-RAG preserves the hierarchy **Document → Chapter → Section → Article → Clause → Point**. — [DST journal, Jan 2026](https://dsjournals.com/dst/DST-V5I1P101)
- AITeamVN/Vietnamese_Embedding was trained at 2048 tokens, which is enough to embed a whole Điều as one vector. — [HF card](https://huggingface.co/AITeamVN/Vietnamese_Embedding)

### Inferences
- **Parsing regex** for Vietnamese legal structure, in a line-anchored, NFC-normalised state machine [inference]:
  - `^Chương\s+([IVXLC]+)` and `^Mục\s+(\d+)`
  - `^Điều\s+(\d+)\.\s*(.*)`
  - `^(\d+)\.\s` for Khoản
  - `^([a-zđ])\)\s` for Điểm

  Phụ lục (appendices) and tables are separate chunks with their own breadcrumb.
- **Chunk text that gets embedded:**
  `"[Nghị định 145/2020/NĐ-CP – Quy định chi tiết ... Bộ luật Lao động] Chương III > Điều 12. Tên điều | Khoản 2: <text>"`

  Store `content` (raw, for quoting) and `embed_text` (breadcrumb + content) separately.
- **Sizes:**
  - child (Khoản) target ≤ 400 tokens, hard cap 512, which keeps vietlegal-harrier compatible;
  - parent (Điều) passed to the LLM, typically under 2K tokens;
  - short Điều without Khoản: child = parent.

  These sizes are inferences, not measured.
- **Contextual Retrieval with an LLM** (Anthropic style) is optional and expensive on a T4. The breadcrumb already captures most of the "which law/article is this" context for legal text. Run LLM contextualisation offline only if eval shows breadcrumb-only misses, for example clauses that say "các trường hợp quy định tại khoản 1" with no self-contained topic. [inference]
- **Late chunking** (jina; embed the whole doc, then pool per chunk [prior knowledge]) adds complexity and is of little value when structural breadcrumbs already carry the context. Skip it.
- Effect status (`còn hiệu lực`, `hết hiệu lực một phần`, `hết hiệu lực toàn bộ`) and amendment relations matter for answer correctness. Default-filter to in-force documents and show the status in citations. [inference]

### Gaps
- I found no published Vietnamese legal study comparing Điều-level, Khoản-level and fixed-token chunking on retrieval metrics.
- I found no token-length distribution of Điều and Khoản in Vietnamese legal corpora; measure it on your corpus.

---

## 5. Exploiting cross-references between documents (graph vs GraphRAG/LightRAG)

### Takeaway
Graph structure measurably helps Vietnamese legal QA (85.7% vs 62.3% for BM25 in one 2026 study). A full GraphRAG or LightRAG (LLM entity extraction over the whole corpus, community summaries, Neo4j) is overkill for a portfolio project on a T4. Build a **regex-extracted reference table in Postgres** and do **1-hop expansion** after reranking.

### Cited Findings
- Pham and Phan, "Integrating Knowledge Graph with RAG for Vietnamese Legal QA" (DST, Jan 2026):
  - The document-aware KG preserves the statute hierarchy and encodes semantic and cross-reference relations.
  - Graph-aware retrieval uses a hybrid ranking of semantic similarity and graph-derived confidence.
  - On Electronic Transaction, Land and Labour law: **85.7%** answer accuracy vs BM25 62.3% vs pure LLM 71.5%, with improved citation quality.

  Edge types, extraction method and storage are not in the abstract. — [DST journal](https://dsjournals.com/dst/DST-V5I1P101)
- **SBV-LawGraph** (ACIIDS 2026) does hybrid RAG for State Bank of Vietnam documents. It has a Legal Retrieval module (sparse-dense with reranking) and a Relationship Retrieval module that traverses a curated legal KG in **Neo4j**. — [Springer](https://link.springer.com/chapter/10.1007/978-981-92-0071-9_16); [author PDF](https://lexuanbach.github.io/publication/ACIIDS2026a.pdf)
- **VLegal-Bench** (arXiv 2512.14554, Dec 2025) includes a legal-graph task for building KGs with inter-article references. LLMs are better at predicting relational edges than at correctly identifying the referenced legal nodes (specific articles or clauses). — [arXiv](https://arxiv.org/html/2512.14554)

### Inferences
- VLegal-Bench shows LLMs are weak at pinpointing *which* article is referenced, while Vietnamese legal cross-references follow rigid templates. So **regex extraction beats LLM extraction** for node identification. [inference]
- Patterns to capture (NFC, case-insensitive):
  - `(điểm\s+([a-zđ])\s+)?(khoản\s+(\d+)\s+)?Điều\s+(\d+)(\s+(của\s+)?(Luật|Bộ luật|Nghị định|Thông tư)[^,.;]*?)?`
  - document numbers `\b(\d+/\d{4}/(QH\d+|NĐ-CP|TT-[A-ZĐ]+|QĐ-[A-ZĐ]+))\b`
  - relation cues `quy định chi tiết|hướng dẫn (chi tiết|thi hành)|sửa đổi, bổ sung|bãi bỏ|thay thế`

  Unqualified "Điều 5" resolves to the same document.
- Pragmatic schema (Postgres, no extra infra):
  ```sql
  create table legal_refs (
    src_chunk_id bigint references chunks(id) on delete cascade,
    dst_doc_id   bigint references legal_docs(id),   -- null if target doc not in corpus
    dst_doc_number text, dst_article int, dst_clause int,
    rel text check (rel in ('references','details','guides','amends','repeals','replaces'))
  );
  create index on legal_refs (src_chunk_id);
  create index on legal_refs (dst_doc_id, dst_article);
  ```
- Document-level edges (Decree X *quy định chi tiết* Law Y, Circular Z *hướng dẫn* Decree X) come from each document's preamble ("Căn cứ ...") and title. Store them as `rel='details'` with null article, or in a `doc_relations` table. [inference]
- **Query-time expansion**, after reranking the top-k parents:
  1. Fetch outgoing refs (the article this clause points to) and incoming `details` or `guides` refs (the Decree or Circular articles implementing this Law article).
  2. Cap at 1 hop and 3-5 extra passages.
  3. Rerank the expanded set once more, or append it as "related provisions" with lower priority.

  This costs one indexed SQL join and no new infra. [inference]
- GraphRAG or LightRAG would need LLM extraction over the whole corpus, run on the shared T4 LLM. That is slow, hard to evaluate, and adds a graph store. Mention it as "future work" in the portfolio write-up. [inference; LightRAG/GraphRAG repos not fetched]

### Gaps
- The full text of the DST and SBV-LawGraph papers (edge taxonomy, hop limits, ablations) was not retrieved; only abstracts were read.
- No published regex grammar or open dataset of Vietnamese legal cross-reference edges was found. VLegal-Bench's graph task data may serve; not checked.

---

## 6. Query-side techniques

### Takeaway
Best gain for least complexity, in order:
1. **Conversational query condensation** (mandatory for multi-turn);
2. **Rule-based extraction** of doc numbers and Điều/Khoản into filters and boosts (free, high precision for legal queries);
3. **Lexical query building** (stopwords + OR + phrases);
4. **Optionally multi-query** (2-3 LLM paraphrases fused by RRF).

HyDE and LLM routing add a full LLM call on a shared T4 for unproven gains in this domain. Skip them by default.

### Cited Findings
- Qwen3-Embedding: query instructions give "typically" 1-5% gain; write instructions in English for multilingual models. — [HF card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- vietlegal-harrier, vnlegal-lal and Harrier require the query-only prefix `Instruct: ...\nQuery: `. Forgetting it is a silent quality bug. — [vietlegal-harrier card](https://huggingface.co/mainguyen9/vietlegal-harrier-0.6b); [Harrier card](https://huggingface.co/microsoft/harrier-oss-v1-0.6b)
- Verifier-guided correction (a post-generation step) improved citation preservation by 0.022-0.034 in a 2026 Vietnamese legal QA study, with no reliable gains on other dimensions. — [arXiv 2609.27376](https://arxiv.org/abs/2609.27376)

### Inferences
- **Condensation:** when history is non-empty, one short LLM call rewrites the last user turn into a standalone Vietnamese question, keeping legal entities and numbers verbatim. Skip the call on turn 1. [inference]
- **Rule extraction:** run the same regex as §5 on the query. On a hit:
  - filter or boost `doc_number`, `article` and `clause`;
  - an exact "Điều 12 Nghị định 145/2020/NĐ-CP" query can bypass search entirely and fetch the row directly.

  [inference]
- **Multi-query:** generate 2-3 paraphrases (lay-term → legal-term, e.g. "đuổi việc" → "đơn phương chấm dứt hợp đồng lao động"). Embed them in one batch call to Kaggle and RRF-fuse. This targets the colloquial-vs-statutory vocabulary gap that dominates legal QA. Measure before keeping it. [inference]
- **HyDE:** generating a fake statute paragraph risks hallucinated article numbers polluting the lexical leg. Not recommended for legal text without eval evidence. [inference]
- **Routing:** a cheap keyword or regex router (chit-chat vs legal question vs exact-article lookup) is enough; no LLM router. [inference]

### Gaps
- I found no Vietnamese-specific study measuring HyDE, multi-query or rewriting gains on legal retrieval; recommendations here are reasoned, not benchmarked.

---

## 7. Parsing Vietnamese docx/pdf (including scanned) and preserving tables

### Takeaway
For **DOCX**, use `python-docx`: paragraph styles, numbering and tables are directly accessible and fit the Chương/Điều regex state machine. For **digital PDFs**, use PyMuPDF or Docling. For **scanned PDFs**, use Docling with **RapidOCR (`vi`)** or EasyOCR, tune the confidence threshold on a sample, and keep VietOCR as a standalone fallback. Docling preserves tables as structured output. Always NFC-normalise.

### Cited Findings
- Docling's RapidOCR language table includes Vietnamese (`vi`). No head-to-head Docling OCR benchmark on Vietnamese was found. — [Docling OCR engines](https://docling-project.github.io/docling/concepts/OCR/); [native language support](https://docling-project.github.io/docling/concepts/OCR_native/)
- A Korean test of Docling (2.132.0, EasyOCR 1.7.2, RapidOCR 3.9.2):
  - The default RapidOCR model (PP-OCRv6) lacked Korean and dropped all of it.
  - EasyOCR and RapidOCR each output about half the text because of Docling's confidence cutoff.
  - Lowering EasyOCR's threshold to 0.2 cut CER from 0.525 to 0.070.
  - Confidence distributions differ by engine and language, so tune per corpus.

  — [WikiDocs test](https://wikidocs.net/441143)
- Guide: Docling's OCR auto-detection order is EasyOCR → Tesseract → RapidOCR, and language codes differ per engine. — [Mintlify Docling OCR guide](https://www.mintlify.com/docling-project/docling/guides/ocr-configuration)
- VietOCR is an open-source Vietnamese printed and handwritten OCR library working on images. No Docling plugin was found. — [search summary](https://www.itechguides.com/best/ocr-software/vietocr/)
- Other Vietnamese OCR options exist: a fine-tuned PaddleOCRv5 for Sino-Vietnamese (arXiv 2510.04003) and `VietAlphaLabs/SenOCR-Vi` on HF. Not evaluated here. — [arXiv](https://arxiv.org/html/2510.04003v2); [HF](https://huggingface.co/VietAlphaLabs/SenOCR-Vi)
- Survey of Vietnamese document analysis and recognition challenges (diacritics, layouts). — [arXiv 2506.05061](https://arxiv.org/html/2506.05061v1)

### Inferences
- Official Vietnamese legal texts are usually available as DOCX or DOC from government portals, so prefer DOCX sources over PDFs where possible. Convert legacy `.doc` with `libreoffice --headless --convert-to docx`. [inference]
- **Must-do normalisation:** `unicodedata.normalize('NFC', text)` at ingest **and** query time. Vietnamese has composed and decomposed diacritic forms that break both FTS and exact match. Old PDFs may use legacy TCVN3/VNI font encodings that extract as mojibake. Detect them and route those files to OCR. [prior knowledge]
- **Tables:** render as Markdown or HTML inside the chunk, with the Điều or Phụ lục breadcrumb. A table larger than about 500 tokens becomes its own chunk with a short header (table caption plus parent Điều). [inference]
- On a scanned page, Docling's layout model plus OCR runs fine on a Kaggle GPU or locally. OCR the scanned subset once, offline, and cache the Markdown. [inference]
- marker and unstructured are alternatives. marker's GPL license and unstructured's heavier dependencies make them less attractive than Docling here [prior knowledge, not verified this session].

### Gaps
- I found no CER/WER benchmark of RapidOCR vs EasyOCR vs VietOCR vs PaddleOCR on Vietnamese legal scans.
- Docling's default RapidOCR model pack for Vietnamese as of Nov 2026 was not confirmed (the Korean test showed PP-OCRv6 default packs can omit languages).

---

## 8. Citation and grounding

### Takeaway
Make the citation unit the retrieval unit:
- every passage sent to the LLM carries an ID plus `doc_number`, Điều and Khoản (and Điểm where present);
- the LLM must cite those IDs;
- the backend checks that every cited ID was actually supplied;
- the system refuses when the top rerank score is below a calibrated threshold.

Graph-aware retrieval and a verifier step both measurably improve citation quality in Vietnamese legal studies.

### Cited Findings
- A verifier-guided correction pass improved citation preservation by 0.022-0.034 at system level. Automatic diagnostics did not fully align with human judgements. — [arXiv 2609.27376](https://arxiv.org/abs/2609.27376)
- The KG-RAG approach improved citation quality alongside accuracy (85.7%). — [DST journal](https://dsjournals.com/dst/DST-V5I1P101)
- The reranker provides a calibrated relevance signal (Vietnamese_Reranker MRR@10 0.867 on Zalo). — [AITeamVN card](https://huggingface.co/AITeamVN/Vietnamese_Embedding)

### Inferences
- Context format for each passage sent to the LLM:
  `[S3] Nghị định 145/2020/NĐ-CP (còn hiệu lực) – Điều 12, khoản 2: "<verbatim text>"`
- The system prompt should require three things:
  - every legal claim ends with `[S#]`;
  - Điều and khoản are quoted from the header, never invented;
  - if the sources don't answer, reply "Không tìm thấy quy định liên quan trong cơ sở dữ liệu" (no relevant provision found in the database).
- **Post-checks in FastAPI**, which are cheap and need no model:
  1. Parse `[S#]` and drop or flag IDs not supplied.
  2. Regex every "Điều N" mentioned in the answer. If it is not in the supplied headers, flag it as a possible hallucination.
  3. Return `sources[]` with `doc_number`, path, `content` and a deep link to the source (page or anchor) for the UI.

  [inference]
- **Refusal gate:** if the max reranker score is below τ, refuse before calling the LLM. Pick τ on a held-out set of answerable and unanswerable questions; for example, take 30 Zalo-style questions plus 10 out-of-corpus questions. [inference]
- Show effect status and issue date in citations. A correct quote from a repealed article is still a wrong answer. [inference]

### Gaps
- No Vietnamese-specific study of citation-check heuristics or refusal-threshold calibration was found.

---

## 9. Recommended end-to-end pipeline (synthesis)

### Takeaway
1. DOCX-first parsing, with Docling + RapidOCR only for scans.
2. Điều/Khoản structural chunks with breadcrumb headers.
3. `AITeamVN/Vietnamese_Embedding` (A/B with `mainguyen9/vietlegal-harrier-0.6b`) stored as `halfvec(1024)` with HNSW.
4. `simple`-config FTS with OR queries and metadata exact match.
5. RRF hybrid in a Supabase SQL function.
6. `AITeamVN/Vietnamese_Reranker` on the top 40.
7. Small-to-big parent expansion plus 1-hop cross-reference expansion.
8. Condensation plus regex query parsing.
9. ID-checked citations with a refusal gate.

Every heavy component runs on the Kaggle T4. Vercel only does HTTP, regex and SQL.

### Cited Findings
- Supabase RRF function pattern and defaults (`rrf_k=50`, weights 1/1) — [Supabase docs](https://supabase.com/docs/guides/ai/hybrid-search)
- pgvector limits, HNSW defaults (`m=16`, `ef_construction=64`, `ef_search=40`) and iterative scans in 0.8.0+ — [pgvector README](https://github.com/pgvector/pgvector)
- Contextual header plus BM25 plus rerank cuts failure 67% in Anthropic's tests — [Anthropic](https://www.anthropic.com/news/contextual-retrieval)
- Model evidence as in §1-2 — [AITeamVN](https://huggingface.co/AITeamVN/Vietnamese_Embedding); [vietlegal-harrier](https://huggingface.co/mainguyen9/vietlegal-harrier-0.6b)

### Inferences
Parameter defaults below are reasoned starting points, not benchmarked values.

| Stage | Choice | Defaults |
|---|---|---|
| Parse | python-docx (DOCX); PyMuPDF/Docling (PDF); Docling + RapidOCR `vi` (scans) | NFC normalise; OCR confidence tuned on sample |
| Chunk | Điều parent / Khoản child / Điểm split if > 450 tok; breadcrumb prefix | child ≤ 400-512 tok; parent ≤ 2K tok |
| Embed | `AITeamVN/Vietnamese_Embedding` (alt `mainguyen9/vietlegal-harrier-0.6b` + query prefix) | fp16 on T4, batch 32, normalised; `halfvec(1024)` |
| Index | HNSW `halfvec_ip_ops` (normalised vectors) + GIN on `to_tsvector('simple', embed_text)` | m 16, ef_construction 64; `hnsw.ef_search` 100 |
| Lexical | OR-tsquery, stopwords removed, phrases kept; regex IDs → metadata filters | full_text_weight 1.0 (1.5 if IDs found) |
| Fuse | RRF in SQL | rrf_k 50, 20-25 per leg, 40 out |
| Rerank | `AITeamVN/Vietnamese_Reranker` (alt `BAAI/bge-reranker-v2-m3`, `Qwen/Qwen3-Reranker-0.6B`) | top 40 → top 5-8 parents; max_length 512 |
| Expand | parent Điều + 1-hop `legal_refs` (details/guides/references) | ≤ 3-5 extra passages |
| Query | condense (multi-turn) → regex IDs → lexical builder → (optional) 2-3 paraphrases | |
| Cite | `[S#]` IDs, post-check, refusal gate on rerank score | τ calibrated on held-out set |
| Eval | `GreenNode/zalo-ai-legal-text-retrieval-vn` (818 test queries) + 50-100 hand-written Q&A on your own corpus | Recall@10, MRR@10, NDCG@10 per stage ablation |

Draft SQL (adapted from the Supabase pattern; untested):
```sql
create extension if not exists vector with schema extensions;

create table legal_docs (
  id bigint generated always as identity primary key,
  doc_number text unique, doc_type text, title text, issuer text,
  issued_date date, effective_date date, status text default 'in_force'
);
create table chunks (
  id bigint generated always as identity primary key,
  doc_id bigint not null references legal_docs(id) on delete cascade,
  parent_id bigint references chunks(id) on delete cascade,
  level text not null,                 -- 'dieu' | 'khoan' | 'diem' | 'table'
  path text not null,                  -- 'Chương III > Điều 12 > Khoản 2'
  article int, clause int, point text,
  content text not null,               -- verbatim, for quoting
  embed_text text not null,            -- breadcrumb + content
  fts tsvector generated always as (to_tsvector('simple', embed_text)) stored,
  embedding extensions.halfvec(1024)
);
create index on chunks using gin (fts);
create index on chunks using hnsw (embedding extensions.halfvec_ip_ops);
create index on chunks (doc_id, article, clause);

create or replace function hybrid_search(
  query_tsq tsquery,                   -- built in FastAPI (OR terms, phrases)
  query_embedding extensions.halfvec(1024),
  match_count int default 40,
  full_text_weight float default 1,
  semantic_weight float default 1,
  rrf_k int default 50,
  only_in_force boolean default true
) returns table (id bigint, parent_id bigint, score float)
language sql stable as $$
with full_text as (
  select c.id, row_number() over (order by ts_rank_cd(c.fts, query_tsq) desc) as rank_ix
  from chunks c join legal_docs d on d.id = c.doc_id
  where c.fts @@ query_tsq and (not only_in_force or d.status <> 'repealed')
  order by rank_ix limit match_count
),
semantic as (
  select c.id, row_number() over (order by c.embedding <#> query_embedding) as rank_ix
  from chunks c join legal_docs d on d.id = c.doc_id
  where (not only_in_force or d.status <> 'repealed')
  order by c.embedding <#> query_embedding limit match_count
)
select c.id, c.parent_id,
  coalesce(1.0/(rrf_k + ft.rank_ix), 0) * full_text_weight +
  coalesce(1.0/(rrf_k + s.rank_ix), 0) * semantic_weight as score
from full_text ft full outer join semantic s on ft.id = s.id
join chunks c on c.id = coalesce(ft.id, s.id)
order by score desc limit match_count
$$;
```
- Call it from FastAPI via `supabase.rpc('hybrid_search', ...)` or psycopg. Pass the tsquery as text and cast `::tsquery` server-side, or accept `text` and call `to_tsquery('simple', ...)` inside. Then send the candidates to Kaggle `/rerank` and fetch parents plus refs in one follow-up query.
- For a filtered semantic leg, run `set local hnsw.iterative_scan = relaxed_order` inside a plpgsql wrapper (requires pgvector ≥ 0.8.0 on Supabase). This is [inference] from the pgvector README; check the installed version.
- Operational risk: Kaggle sessions are time-limited and the tunnel URL changes. Vercel needs a health-check and a graceful "service waking up" error. Ingestion embeddings are computed offline and stored, so only query embedding and rerank depend on the live notebook. [inference]

### Gaps
- None of the parameter defaults above were benchmarked on a Vietnamese legal corpus in a source found. Build an ablation harness (dense only → + FTS → + rerank → + ref expansion).
- Supabase free-tier behaviour of HNSW builds on about 30-50K halfvec rows (maintenance_work_mem limits) was not checked.

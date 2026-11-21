# Evaluation, Observability and Portfolio Differentiators for a Zero-Budget Vietnamese Legal RAG (state as of 2026-11-22)

Scope: portfolio RAG app (FastAPI on Vercel, Supabase pgvector hybrid search, self-hosted Vietnamese LLM + embedding + reranker on a free Kaggle GPU notebook that is only online during demos, Next.js UI, GitHub Actions). Corpus: ~10-30 interrelated Vietnamese legal docx/pdf. Paid LLM APIs are banned for answer generation.

Date flags: items older than ~12 months are marked (OLDER). Free-tier numbers change often; every quota below should be re-checked on the live page before you rely on it.

---

## 1. How to build a Vietnamese golden QA set (~50-150 questions): synthetic vs manual, question types, and public benchmarks

### Takeaway
Use synthetic-first, human-edited: an LLM drafts candidate questions from specific articles (Điều/Khoản), then a human reviews and fixes every item. Set quotas per question type (single-hop, numeric, multi-hop across documents, unanswerable/out-of-scope, adversarial). Label gold evidence at the legal-article level rather than by chunk ID, so the set still works after you change chunking. Public Vietnamese legal benchmarks (Zalo Legal 2021, ALQAC, bkai VNLAWQC, VLegal-Bench, VLQA) are useful as secondary sanity checks for choosing the embedding model and reranker. They cannot replace a golden set built on your own corpus.

### Cited Findings
**Method guidance**
- Hamel Husain recommends building a retrieval eval set by working backwards: take corpus documents, extract key facts, and generate questions those facts would answer. "This reverse process gives you query-document pairs for measuring retrieval performance without manual annotation." — [Hamel Husain, Evals FAQ: RAG](https://hamel.dev/blog/posts/evals-faq/how-should-i-approach-evaluating-my-rag-system.html)
- Jason Liu (May 2025, OLDER but still the standard framing) says to start the improvement flywheel with synthetic data and fast retrieval metrics. He calls the retrieval metrics "the leading indicators that predict future success." — [Jason Liu, There Are Only 6 RAG Evals](https://jxnl.co/writing/2025/05/19/there-are-only-6-rag-evals/)
- A hiring-side view (Mar 2026, updated Aug 2026): "For a focused project, ten carefully chosen examples can be enough to demonstrate the habit." He wants a verified test set and a baseline. — [Louis-François Bouchard, What I look for when hiring AI engineers](https://www.louisbouchard.ai/what-i-look-for-when-hiring-ai-engineers/)

**RAGAS testset generation (current state)**
- Ragas releases: v0.4.0 (03 Dec) brought the BasePrompt architecture and a unified LLM factory. v0.4.1 (10 Dec) added an `LLM_CONTEXT` input to `TestsetGenerator`. v0.4.2 (23 Dec) added `generate_with_chunks` for pre-chunked documents, HuggingFace tokenizer support in knowledge-graph ops, a fixed `BasePrompt.adapt()` and a language-adaptation guide. v0.4.3 (13 Jan) enabled language adaptation for FactualCorrectness and added a DSPy optimizer. v0.4.4 (14 Nov) "restores a working install", fixes CVE-2026-6587 and includes "fix testset generation bugs". The releases page shows no years. From the order, v0.4.0-0.4.2 are late 2025, v0.4.3 is Jan 2026 and v0.4.4 is Nov 2026. — [Ragas GitHub releases](https://github.com/explodinggradients/ragas/releases)
- The "stable" testset-generation docs page still shows `LangchainLLMWrapper(ChatOpenAI(...))` and `generate_with_langchain_docs(docs, testset_size=10)`. It covers a knowledge-graph flow (`default_transforms`, `apply_transforms`) with a default query distribution of `SingleHopSpecificQuerySynthesizer` 0.5, `MultiHopAbstractQuerySynthesizer` 0.25 and `MultiHopSpecificQuerySynthesizer` 0.25. The page does not mention `llm_factory` or non-English adaptation. — [Ragas docs: Testset generation](https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/index.md)

**DeepEval Synthesizer**
- `generate_goldens_from_docs()` accepts .txt, .docx, .pdf, .md, .markdown and .mdx. It is a superset of `generate_goldens_from_contexts()`, which is a superset of `generate_goldens_from_scratch()`. The Synthesizer `model` accepts any custom `DeepEvalBaseLLM` (including Ollama or local models). Unless you set a `FiltrationConfig`, the same model is reused as the critic that filters goldens. — [DeepEval docs: generate from docs](https://deepeval.com/docs/synthesizer-generate-from-docs); [DeepEval Golden Synthesizer](https://deepeval.com/docs/golden-synthesizer)
- Local setup: `deepeval set-ollama --model=<name>`. Document-based generation also needs an embedding model: `deepeval set-ollama-embeddings --model=<name>`. Older docs use `deepeval set-local-model` with a base URL, so syntax depends on the installed version. — [DeepEval guide: custom embedding models](https://deepeval.com/guides/guides-using-custom-embedding-models)

**Public Vietnamese legal retrieval/QA resources (for extra eval)**
- **Zalo AI Legal Text Retrieval 2021**: 2,556 training and 640 evaluation samples, corpus of 61,060 (OLDER, 2021). These figures come from the bkai NAACL 2025 table. — [bkai, NAACL 2025 short paper (PDF)](https://preview.aclanthology.org/moar-dois/2025.naacl-short.12.pdf)
  - Hugging Face mirror (parquet, 10K-100K rows): [another-symato/VMTEB-Zalo-legel-retrieval](https://huggingface.co/datasets/another-symato/VMTEB-Zalo-legel-retrieval/tree/main). A model card says it was evaluated on `GreenNode/zalo-ai-legal-text-retrieval-vn`, which suggests another mirror exists. Contents and license are unverified. — [bqbbao6/vietnamese-legal-embedding](https://huggingface.co/bqbbao6/vietnamese-legal-embedding)
- **bkai-foundation-models/crosslingual**: VNLAWQC is sourced from the Vietnamese Law Library, with 165,347 train samples, 9,992 eval samples and a 224,008-document corpus. VNSynLawQC was augmented with Llama-3-70B. — [HF dataset](https://huggingface.co/datasets/bkai-foundation-models/crosslingual); [NAACL 2025 paper](https://preview.aclanthology.org/moar-dois/2025.naacl-short.12.pdf)
- **bkai synthetic legal queries**: a bkai paper describes generating 500,000 legal queries plus passages with LLMs to improve Vietnamese legal passage retrieval (OLDER, Dec 2024). It shows the synthetic-query method works for this domain. — [Improving Vietnamese Legal Document Retrieval using Synthetic Data (arXiv 2412.00657)](https://arxiv.org/html/2412.00657v1)
- **ALQAC** (Automated Legal Question Answering Competition): a manually annotated legal QA dataset built on Vietnamese statute law. The Hugging Face repo is gated (you must share contact info). It has yearly folders for 2023-2025 and an `additional_data/` folder that includes Zalo and 2022 training data. — [HF nguyenlab/ALQAC](https://huggingface.co/datasets/nguyenlab/ALQAC); described in [ViHERMES (arXiv 2602.07361)](https://arxiv.org/pdf/2602.07361)
- **VLQA** (arXiv 2507.19995, Jul 2025): 3,129 questions from laypeople, checked and labeled by legal professionals, linked to a corpus of ~59,000 legal provisions. Tasks are legal IR and QA. The authors say they will release the dataset and code, but the arXiv abstract page has no dataset link. The paper is licensed CC BY-NC-SA 4.0. — [arXiv abstract](https://arxiv.org/abs/2507.19995); [HTML](https://arxiv.org/html/2507.19995v1)
- **VLegal-Bench** (arXiv 2512.14554, v4): 10,450 expert-verified samples. It is a cognitively grounded benchmark of LLM legal reasoning rather than a retrieval set. — [arXiv HTML v4](https://arxiv.org/html/2512.14554v4)
- **ViHERMES** (arXiv 2602.07361): a graph-grounded multihop QA benchmark plus system for Vietnamese healthcare regulations. It is a direct template for "multi-hop across interrelated regulations". — [arXiv PDF](https://arxiv.org/pdf/2602.07361)
- A 2026 paper on cross-lingual Vietnamese labour-law QA built its eval suite of only 231 pairs from VLegal-Bench and ALQAC. That shows a ~100-250 item suite is a credible size. — [arXiv 2609.27376](https://arxiv.org/pdf/2609.27376)
- **VN-MTEB** (EACL 2026 Findings): 41 Vietnamese embedding datasets across 6 tasks, translated from MTEB with an LLM pipeline. Use it to pick the embedding model. — [ACL Anthology](https://aclanthology.org/2026.findings-eacl.86); [arXiv 2507.21500](https://arxiv.org/abs/2507.21500)

### Inferences
- **Recommended composition for ~100-120 items** (my proposal, built from the question types above):
  | Type | Share | Notes |
  |---|---|---|
  | Single-hop factual (one Điều/Khoản) | ~35% | Draft with an LLM, then edit by hand |
  | Numeric / date / threshold / penalty (mức phạt, thời hạn, tỷ lệ) | ~15% | Can be scored deterministically by number/date match |
  | Multi-hop across documents (Luật ↔ Nghị định hướng dẫn ↔ Thông tư; amended-by; "theo quy định tại Điều X") | ~20% | Build from explicit cross-references (regex on "Điều", "Nghị định số …"), like ViHERMES's graph-grounded approach |
  | Comparative / abstract / summarise | ~10% | Matches RAGAS "multi-hop abstract" |
  | Unanswerable but in-domain (law not in corpus, or detail absent) | ~10% | Expected behaviour is a refusal template |
  | Out-of-domain + prompt-injection probes | ~5-10% | Feeds the guardrail metrics (Q6) |
  | Optional: temporal validity (expired or amended provisions) | few | Strong domain-depth signal for legal RAG |
- **Schema per item**: `id, question, reference_answer, gold_article_ids (e.g. "LuatDN2020:D17:K2"), gold_doc_ids, type, answerable, difficulty, origin (synthetic-edited | manual | from-benchmark), reviewer`. Article-level gold IDs mean qrels survive chunking ablations: map each retrieved chunk to its article ID at eval time.
- **Tooling choice**: for 10-30 documents, a ~50-100 line custom generator gives you more control than RAGAS or DeepEval. Its prompt would be: "Write 2 Vietnamese questions answerable only from this Điều, give the answer and the exact quoted span, as JSON", plus a pairwise prompt for cross-referenced articles. RAGAS's knowledge-graph synthesizers are an option for multi-hop. Its prompts are English by default and its API has churned (v0.3 to v0.4 collections, a broken install fixed only in v0.4.4), so pin the version if you use it.
- **Which LLM drafts the questions**: question drafting is not answer generation, so a free-tier model (e.g., Gemini free tier) does not break the project constraint. The corpus is public law text, so sending it raises no privacy issue (see Q3 for the terms). Prefer a model family different from the answering model, to reduce leakage and self-preference effects. Every item must still be human-reviewed. Report "% of items human-edited" in a dataset card.
- **Use public benchmarks only for component selection**, e.g., "embedding model A vs B: Recall@10 on Zalo-Legal-2021 eval". Their corpora differ from yours, so they say nothing about your end-to-end quality. Check licenses: ALQAC is gated and VLQA is NC.

### Gaps
- No dataset named "ViLQA" was found. It may be confused with VLQA or not exist.
- VLQA's actual release status and link were not found. Zalo 2021 data licensing on the HF mirrors was not verified.
- I found no published evaluation of RAGAS or DeepEval synthetic-question quality in Vietnamese.

---

## 2. Retrieval metrics (Recall@k, MRR, nDCG, hit rate), computed deterministically without an LLM so they run in CI while Kaggle is offline

### Takeaway
Retrieval is a search problem. Score it with classic IR metrics from a qrels file plus a run file using `ranx`, which is checked against TREC Eval and includes significance tests and RRF fusion. No LLM is needed. The only model dependency is query embeddings for the dense leg. The golden questions are fixed, so cache their embeddings, keyed by model, and commit the cache. A small ONNX model on the CPU runner is optional.

### Cited Findings
- Hamel says to evaluate retrieval "using traditional information retrieval (IR) metrics" such as Recall@k, Precision@k and MRR, chosen for the use case, and to "debug retrieval first using IR metrics, then tackle generation quality using properly validated LLM judges." — [Hamel Husain, Evals FAQ: RAG](https://hamel.dev/blog/posts/evals-faq/how-should-i-approach-evaluating-my-rag-system.html)
- Third-party notes on the Husain/Shankar course say to get the retriever's Recall@k to 80%+ before doing error analysis, and to optimise Recall@k first. These are secondhand. — [Vishal Bakshi's course notes](https://vishalbakshi.github.io/blog/posts/2025-08-07-ai-evals/index.html)
- Jason Liu's Tier 1 (precision, recall, MAP@K, MRR@K) is "fast" and needs no LLM. "If your retriever pulls irrelevant context, your generator is doomed from the start." — [jxnl.co](https://jxnl.co/writing/2025/05/19/there-are-only-6-rag-evals/)
- **ranx** covers:
  - **Metrics:** Hits, Hit Rate, Precision, Recall, F1, r-Precision, Bpref, RBP, MRR, MAP, DCG and NDCG, all tested against TREC Eval.
  - **Significance tests:** paired t-test, Fisher's randomization and Tukey's HSD.
  - **Fusion:** about 25 algorithms including RRF, CombSUM and weighted sum, plus `optimize_fusion`.
  - **Reporting:** `compare()` builds report tables and exports LaTeX.
  - **Speed:** Numba-accelerated.
  — [ranx GitHub](https://github.com/AmenRa/ranx)
- **Anthropic Contextual Retrieval** (Sep 2024, OLDER) is the best-known ablation write-up. It measures `1 − recall@20`, starting from a 5.7% failure rate:
  - contextual embeddings: 3.7% (−35%)
  - plus contextual BM25: 2.9% (−49%)
  - plus reranking (score the top 150, keep 20): 1.9% (−67%)
  
  It also found hybrid embeddings+BM25 beat embeddings alone, and tested 5/10/20 chunks, with 20 best. Appendices break results down by dataset, embedding model, BM25, contextualisation and rerank. — [Anthropic, Introducing Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)
- **CPU embeddings for CI**:
  - FastEmbed runs on ONNX Runtime on CPU and supports `intfloat/multilingual-e5-small/base/large` (small is 384-dim, large is 1024-dim, 512-token max). — [qdrant/fastembed](https://github.com/qdrant/fastembed)
  - The model downloads on first use, so a CI job should cache the model directory. — [SurrealDB FastEmbed docs](https://surrealdb.com/docs/integrations/embeddings/fastembed)
  - A Vietnamese-specific ONNX export exists in int8 (135 MB), fp16 (269 MB) and fp32 (538 MB). The base model is not stated. — [laituanmanh32/vietnamese-embedding-onnx](https://huggingface.co/laituanmanh32/vietnamese-embedding-onnx/tree/main/onnx)

### Inferences
- **Metric set to report**: Hit@1, Recall@5, Recall@10, Recall@20, MRR@10 and nDCG@10, at article level and by question type. Exclude unanswerable items from retrieval metrics and score them separately as refusal accuracy (Q6).
- **Making the PR gate deterministic, with Kaggle offline**:
  1. **Query-embedding cache (recommended):** `eval/cache/query_emb.<embedding_model_id>.parquet` maps sha256(question) to a vector. Regenerate it in a Kaggle session whenever the golden set or embedding model changes. In CI, a missing key fails loudly instead of silently skipping.
  2. **CPU model:** only if the production embedding model has a small ONNX export (int8 around 100-300 MB loads in seconds on a GitHub runner). Otherwise CPU vectors won't match the GPU-indexed documents. Use the same model and same normalisation, or the cache approach.
  3. **Frozen eval index:** export the chunk table (text, article_id, embedding, tsvector or tokens) as a CI artifact or a Git LFS file. Run either the real SQL hybrid function against a Postgres+pgvector service container, or an in-process numpy cosine + BM25 equivalent. The service container tests the real SQL. The in-process version is simpler but can drift from production. Either way the gate needs no Supabase network access or secrets.
- **What the gate can and cannot catch**: it catches changes to fusion weights, RRF k, top-k, filters, query preprocessing (e.g., Vietnamese word segmentation or diacritic normalisation for BM25) and SQL. Changes to chunking or the embedding model need re-indexing on GPU, so run them in the manual full-eval workflow (Q4) and label those PRs accordingly.
- **Statistical honesty**: with n≈100, one question is about 1 point of Hit@k. Use ranx's paired tests or a bootstrap CI and say "not significant" when that is the case. Interviewers who know IR will notice.
- **Reranker**: evaluate it offline in the Kaggle session (GPU). If a small cross-encoder runs on CPU, it can join the CI gate. Otherwise, store reranker outputs per query as a cached run file.

### Gaps
- I did not find a published GitHub Actions example of a Vietnamese retrieval-eval gate, so the design above is my synthesis.
- I did not verify the `pgvector/pgvector` Docker image tag or service-container recipe.

---

## 3. Generation metrics (faithfulness, answer relevancy, context precision/recall, citation accuracy): frameworks, Vietnamese performance, and whether a free LLM may act as judge

### Takeaway
Track a small set of judge metrics you validate yourself, with prompts written in Vietnamese: faithfulness/groundedness (A|C), answer correctness against the reference, and context relevance. Add a deterministic layer that needs no LLM: citation validity and accuracy against gold article IDs, numeric and date match, refusal correctness, and answer language. Frameworks (RAGAS v0.4, DeepEval, promptfoo) can serve as harnesses, but their default English prompts and structured-output requirements make them brittle with Vietnamese and small local judges. Published research finds multilingual LLM judges unreliable in lower-resource languages. Using a free hosted LLM only as an offline evaluator is reasonable if you meet the conditions listed under Inferences.

### Cited Findings
**What to measure**
- Liu's six relationships:
  - Tier 2: context relevance C|Q, faithfulness A|C, answer relevance A|Q.
  - Tier 3: C|A, Q|C (answerability) and Q|A.
  - "When your RAG system fails, it fails along one of these dimensions." LLM judges capture the nuance best but are resource-intensive.
  
  — [jxnl.co](https://jxnl.co/writing/2025/05/19/there-are-only-6-rag-evals/)
- Hamel: "don't just use prompts off the shelf". Measure each judge's TPR/TNR against human labels and use them to "correct its estimates to determine the actual failure rate". Add domain-specific evaluators for failure modes found in error analysis. — [Hamel Husain, Evals FAQ: RAG](https://hamel.dev/blog/posts/evals-faq/how-should-i-approach-evaluating-my-rag-system.html)

**Framework state (late 2026)**
- RAGAS changes:
  - Metrics moved to a "collections" API through v0.3.8-v0.4.2, and legacy metrics were deprecated in v0.4.2.
  - `instructor_llm_factory` merged into `llm_factory` (v0.3.8). v0.4.0 switched to `instructor.from_provider` with Instructor and LiteLLM adapters.
  - System prompts were added in v0.4.3, and a `mode` parameter in v0.4.4.
  - Language adaptation: the guide and `adapt()` fix came in v0.4.2, and FactualCorrectness gained adaptation in v0.4.3.
  - After v0.4.3 (Jan 2026) there was no release until v0.4.4 (Nov 2026), which "restores a working install" and fixes a CVE.
  
  — [Ragas releases](https://github.com/explodinggradients/ragas/releases)
- The stable RAGAS docs page still shows LangChain wrappers and doesn't mention `llm_factory`, so docs lag the API. — [Ragas docs](https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/index.md)
- DeepEval accepts any `DeepEvalBaseLLM` (Ollama or local) as the model and supports Ollama via the CLI. — [DeepEval docs](https://deepeval.com/docs/golden-synthesizer); [DeepEval guide](https://deepeval.com/guides/guides-using-custom-embedding-models)
- A third-party package, `rag-eval-gate`, is a "CI/CD-integrated RAG evaluation pipeline": a quality gate using Ragas with a Groq LLM judge. It is precedent for a free-tier judge in CI. — [PyPI rag-eval-gate](https://pypi.org/project/rag-eval-gate/)

**Judge reliability in non-English / Vietnamese**
- Fu & Liu (May 2025, OLDER) found that multilingual LLM-as-a-judge consistency is poor in low-resource languages. Neither model size nor multilingual training improved it, and consistency depends on task ability. They propose an ensemble of judges. — [How Reliable is Multilingual LLM-as-a-Judge? (arXiv 2505.12201)](https://arxiv.org/abs/2505.12201)
- A later paper describes that work as five judges across 25 languages with a mean Fleiss' κ ≈ 0.3. This is secondhand and not verified against the original. — [arXiv 2610.31172](https://arxiv.org/pdf/2610.31172)
- Judges align substantially better with humans on structurally observable criteria than on culturally interpretive ones (AACL 2026). — [Hossain et al., AACL 2026](https://aclanthology.org/2026.aacl-long.249.pdf)
- LLM evaluators recognise and favour their own generations (self-preference bias), and the bias correlates with self-recognition ability. — [Panickssery, Bowman, Feng 2024 (arXiv 2404.13076)](https://arxiv.org/abs/2404.13076)

**Free judge options and their terms**
- OpenRouter's free-API comparison (published 2026-06-15, updated 2026-09-24, figures checked against April 2026 docs):

  | Provider | Rate limit | Volume | Training on free-tier data |
  |---|---|---|---|
  | OpenRouter free models | 20 RPM | 50 req/day (1,000/day after a $10 top-up) | No |
  | Groq | 30 RPM | 1,000 req/day | No |
  | Google AI Studio | 5-15 RPM | 20-1,500 req/day | Yes, outside EU/UK/EEA |
  | Cerebras | 30 RPM | ~1M tokens/day | No |
  | Mistral Experiment tier | variable | ~1B tokens/month | Must opt into training |
  | GitHub Models | 15 RPM | 150-1,000 req/day | No |

  — [OpenRouter blog, Free LLM APIs compared](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)
- Groq limits apply per organisation and per model. The console's limits page is the authoritative source. — [Groq community: rate limits](https://community.groq.com/t/what-are-the-rate-limits-for-the-groq-api-for-the-free-and-dev-tier-plans/42)
- **Gemini API terms (effective 2026-03-23)** for unpaid services:
  - Google uses your content and responses to "provide, improve, and develop" products.
  - "human reviewers may read, annotate, and process your API input and output".
  - "Do not submit sensitive, confidential, or personal information to the Unpaid Services."
  - "You may not use the Services to develop models that compete with the Services."
  - Users must be 18+.
  - Apps serving EEA/CH/UK users must use Paid Services.
  
  — [Gemini API / AI Studio Additional Terms](https://aistudio.google.com/docs/terms)
- Linking a billing account moves a project to paid, and all usage is charged regardless of earlier free limits (Google rep on the forum). — [Google AI forum](https://discuss.ai.google.dev/t/clarification-on-gemini-api-free-tier-vs-paid-tier-after-billing-activation/96995)
- **OpenRouter**:
  - Accounts have separate settings for paid and free endpoints that may train on inputs. With training opted out, OpenRouter won't route to providers that train.
  - Prompt logging is opt-in.
  - Each provider has its own data policy.
  
  — [OpenRouter docs: provider logging](https://openrouter.ai/docs/guides/privacy/provider-logging); [Privacy & logging](https://openrouter.ai/docs/features/privacy-and-logging)
- A third-party analysis (Oct 2026) of 19 free models: 9 sit on hosts that may train and 6 retain prompts without training. The `openrouter/free` router picks models at random, so two requests can be answered by different models. — [TrueFoundry blog](https://www.truefoundry.com/blog/openrouter-free-models-whats-actually-free-and-what-it-costs-you)

### Inferences
- **Is a free LLM reasonable as an evaluator only? Yes, under these conditions:**
  1. It never sits in the serving path, and the README says so explicitly ("answers: self-hosted model X; offline judge: model Y via free tier").
  2. Send only public legal text plus synthetic or edited questions, never real user queries or PII. Gemini's unpaid terms explicitly forbid sensitive or personal data and allow human review.
  3. Pin an exact model ID (never `openrouter/free`). Record the judge model, version and date in every report.
  4. Use a different model family from the answer model, to reduce self-preference bias.
  5. Validate the judge on ~30-50 human-labelled items and report agreement or Cohen's κ. Given the multilingual-judge findings, an unvalidated judge number in Vietnamese is weak evidence.
  6. Account for quota. Roughly 100 items × 3 judge calls × 3-6k tokens of legal context is about 1-2M tokens per full run. A provider with a ~200k tokens/day per-model cap cannot do a full run in a day, while ~1M tokens/day (Cerebras, per the table) or Gemini free tier can. Also run the judge locally (see next point) and use the free hosted judge on a calibration subset.
  The "competing models" clause is not triggered by evaluation. Using Gemini outputs to fine-tune your answer model could be.
- **Self-hosted judge**: run it in the same Kaggle session with structured or JSON-constrained decoding, to avoid parse failures from small models. If VRAM allows, use a larger or different-family model than the answerer. Treat it as primary for volume and cross-check with a free hosted judge on a subset. Two different judges agreeing is a cheap version of the ensemble remedy from arXiv 2505.12201.
- **Deterministic generation checks** (cheap, robust in Vietnamese, CI-friendly, no LLM):
  - Citation validity: every `[n]` in the answer maps to a retrieved chunk.
  - Citation precision/recall: cited article IDs vs gold article IDs.
  - Numeric/date exact match: regex on numbers, percentages and dates in the answer vs the reference.
  - Refusal correctness: a fixed refusal template, e.g. "Không tìm thấy căn cứ trong cơ sở dữ liệu", on unanswerable items vs false refusals on answerable ones.
  - Answer is in Vietnamese.
  - Answer length / latency budget.
- **Framework recommendation**:
  - Retrieval gate: plain pytest + ranx, no framework.
  - Generation eval: custom Vietnamese judge prompts (~100 lines) or RAGAS v0.4 collections metrics with `llm_factory` pointed at the Kaggle vLLM OpenAI-compatible endpoint. If you use RAGAS, pin the version and write Vietnamese-adapted prompts. The RAGAS name is recognisable in a README.
  - DeepEval is the more pytest/CI-native alternative.
  - promptfoo is best for prompt and guardrail regression and red-team YAML tests (Q4, Q6).
  - TruLens and Phoenix evals add little over these for this project size.

### Gaps
- I did not fetch the TruLens or Arize Phoenix eval docs, so there are no specifics on their local-judge support or Vietnamese behaviour.
- I found no study measuring RAGAS faithfulness or answer relevancy on Vietnamese specifically.
- The per-model Groq numbers in search snippets (e.g., for gpt-oss-120b: 30 RPM, 1,000 RPD, 8,000 TPM, 200,000 TPD) came from third-party aggregators, not verified against Groq's console.

---

## 4. Running eval in GitHub Actions: retrieval-only PR gate, manual full eval when Kaggle is online, reports, regression thresholds

### Takeaway
Use two workflows.
1. `eval-retrieval.yml` runs on every PR on a CPU runner. It is deterministic, uses cached query embeddings and a frozen index, compares ranx metrics with a committed `main` baseline, fails on regression, and posts a sticky PR comment plus a job summary and artifacts.
2. `eval-full.yml` runs on `workflow_dispatch` while the Kaggle notebook is up. It takes the tunnel URL as an input and the token as a secret, runs end-to-end generation plus judges plus deterministic checks, uploads the HTML/JSON report, and commits a dated results file that feeds the README table.

### Cited Findings
- The official promptfoo GitHub Action runs a before/after comparison on PRs that modify prompts and posts a PR comment built from `output.json` (`promptfoo/promptfoo-action@v1` in the docs; a v2 tag is also mentioned, so check before pinning). — [promptfoo docs: GitHub Action](https://promptfoo.dev/docs/integrations/github-action); [DeepWiki: PR comment results](https://deepwiki.com/promptfoo/promptfoo-action/4.2-pr-comment-results)
- DIY pattern: `promptfoo eval --share` emits JSON, JUnit and HTML, then `gh pr comment` posts a summary. — [promptfoo docs: CI/CD](https://promptfoo.dev/docs/integrations/ci-cd/)
- A plain eval run only gives the current pass rate. The comparison is what shows a regression. — [Medium: regression evals in CI with promptfoo](https://medium.com/@alexrodriguesj/testing-llm-prompts-like-code-regression-evals-in-ci-cd-with-promptfoo-5242b4dcb9be)
- `rag-eval-gate` comments on PRs and blocks merge on failure (Ragas + Groq judge). `evalcheck` is a pytest plugin that posts regression comments. — [rag-eval-gate](https://pypi.org/project/rag-eval-gate/); [evalcheck](https://pypi.org/project/evalcheck/)
- FastEmbed downloads models on first use, so cache them. — [SurrealDB FastEmbed docs](https://surrealdb.com/docs/integrations/embeddings/fastembed)

### Inferences
- **PR gate steps**:
  1. Checkout.
  2. Restore the pip and model cache.
  3. Load `eval/golden/*.jsonl`, `eval/qrels.json` and `eval/cache/query_emb.*`.
  4. Run the retrieval configurations: BM25 only, dense only, hybrid RRF, plus rerank from cached reranker scores.
  5. Run `ranx.compare()`.
  6. Write a Markdown table to `$GITHUB_STEP_SUMMARY`.
  7. Upload JSON as an artifact.
  8. Post or update one sticky PR comment with `gh pr comment --edit-last` or a sticky-comment action.
  9. Exit non-zero if the thresholds below fail.
- **Thresholds**:
  - Absolute floors on the primary metric, e.g. Recall@10 ≥ 0.85 on answerable items. Set floors after the first honest baseline, never before.
  - Relative regression: fail if a headline metric drops by more than ~2-3 questions' worth vs `eval/baselines/main.json`, or if a ranx paired test shows a significant drop (p<0.05).
  - Update the baseline automatically on push to `main`.
  - Path filters: trigger on `api/retrieval/**`, `eval/**` and `prompts/**`.
- **Full eval**:
  - Inputs are `kaggle_url` (the tunnel URL changes each session) and an optional `subset`.
  - The secret `KAGGLE_API_TOKEN` is checked by the FastAPI or Kaggle server.
  - Steps: health-check the endpoint, run all goldens with concurrency 2-4, judge locally plus a free judge on a subset, run the deterministic checks, write `eval/results/YYYY-MM-DD_<sha>.json` + `.md`, then upload the artifact and open a PR or commit with the results.
  - The README results table and badges are generated from the latest results file. That keeps the numbers reproducible and dated.
- Add a smoke "contract" test that runs without a GPU: mock the LLM endpoint and check that the API returns citations, the refusal path, and timeouts. It keeps CI green and meaningful even when Kaggle is down.

### Gaps
- I did not verify whether Kaggle's API can trigger a notebook run (`kaggle kernels push`) to automate the full eval end-to-end.
- I did not verify the exact current version tags of the promptfoo action or a specific sticky-comment action.

---

## 5. Observability and tracing on free tiers (Langfuse, Phoenix, LangSmith, Helicone), prompt versioning, user feedback

### Takeaway
Langfuse Cloud Hobby is the best zero-budget fit:
- free with no card; 50k units/month (traces + observations + scores); 30-day data access; 2 users; unlimited projects;
- prompt management, datasets, experiments, LLM-as-judge and annotation (1 queue) included;
- MIT and self-hostable.

LangSmith's free tier is smaller (5k traces, 14-day retention). Phoenix is self-host only for free and licensed ELv2. Helicone's free tier is 10k requests with 7-day retention, and its future is uncertain. Capture thumbs up/down as Langfuse scores and keep prompts versioned in git.

### Cited Findings
- **Langfuse Hobby**:
  - Free, no credit card. 50k units/month, with no additional usage offered on Hobby.
  - "Units" are any tracing data point: traces, observations (spans/events/generations) and scores.
  - 30 days of data access. Older data is kept and visible again after upgrading. 2 users, unlimited projects.
  - LLM-as-judge evaluators, human annotation, datasets and experiments included. 1 annotation queue, 2 alerts.
  - Rate limits: ingestion 1,000 req/min, general API 30 req/min, datasets API 100 req/min, Metrics API 100 req/day.
  - Prompt management, OpenTelemetry, public API, CLI and MCP included. Community support only.
  - Self-hosting (Docker Compose or Kubernetes) is free and open source.
  
  — [Langfuse pricing](https://langfuse.com/pricing)
- **Langfuse user feedback**:
  - The Browser SDK sends a score named `user-feedback` (1 positive, 0 negative) from the frontend using the public key. The secret key stays server-side.
  - Filter `user-feedback < 1` to find bad answers.
  - Use a stable score ID per trace so re-rating updates instead of duplicating.
  - Caveat from the docs: thumbs feedback skews toward unhappy users.
  
  — [Langfuse docs: user feedback](https://langfuse.com/docs/observability/features/user-feedback); [Langfuse guide: user feedback loop](https://langfuse.com/guides/user-feedback-loop); [Changelog 2026-06-18: browser score ingestion](https://langfuse.com/changelog/2026-06-18-browser-score-ingestion)
- Langfuse publishes a guide on turning user feedback into evaluation datasets. — [Langfuse: user feedback to evaluation datasets](https://langfuse.com/resources/engineering/user-feedback-to-evaluation-datasets)
- **LangSmith Developer (free)**: 1 seat and 5,000 base traces/month, hard-capped until a card is added, with 14-day trace retention. Plus is $39/seat/month (June 2026 third-party summary). LangSmith is closed source, and self-hosting is Enterprise only. — [inference.net LangSmith pricing](https://inference.net/content/langsmith-pricing/); [LangChain pricing](https://www.langchain.com/pricing)
- **Arize Phoenix**: free to self-host (SQLite or Postgres) under Elastic License 2.0, which is source-available rather than OSI open source. Arize AX (hosted) is proprietary. This comes from a competitor-authored comparison. — [Langfuse vs Arize Phoenix](https://langfuse.com/compare/arize-phoenix)
- **Helicone Hobby**: 10,000 requests/month free, 1 GB storage, 1 seat, 7-day retention. Pro is $79/month. — [Helicone pricing](https://helicone.ai/pricing); [Costbench Helicone free plan](https://www.costbench.com/software/ai-observability/helicone/free-plan/)

### Inferences
- **Unit budget**: one RAG request is about 1 trace plus ~5 observations (dense retrieve, BM25, fuse, rerank, generate) plus 0-2 scores, i.e. ~7-8 units. That allows about 6,000 requests per month, which is plenty for a portfolio. Trace eval runs selectively (e.g., as Langfuse dataset experiments) so CI doesn't burn units.
- **Serverless caveat** (inference): on Vercel Python functions, flush the tracing client before the response finishes, or spans get dropped.
- **Prompt versioning**: keep prompts as files in git (`prompts/answer_vi.v3.txt`), log `prompt_version` and the git SHA in trace metadata, and let the CI gate trigger on `prompts/**`. Langfuse prompt management is free and fine, but git-first keeps prompts reviewable in PRs and tied to eval results. Mention the trade-off in an ADR.
- **What to show in the README**: one screenshot of a Langfuse trace with per-stage latency (Kaggle round-trip vs retrieval vs rerank), a p50/p95 latency table pulled from traces, and a feedback-to-golden-set loop (bad-rated traces become new golden items after review).
- A minimal fallback if you want no third-party dependency: a Supabase `feedback` table (trace_id, rating, comment), since Supabase is already in the stack.

### Gaps
- I could not confirm Arize Phoenix Cloud free-tier terms from Arize itself.
- One search snippet claimed Mintlify acquired Helicone in March 2026 and put the hosted product into maintenance mode. I found no corroboration, so treat it as unverified, but it is a reason to avoid Helicone.

---

## 6. Guardrails: prompt-injection defense, refusing out-of-domain questions, PII (lightweight approaches)

### Takeaway
Use lightweight, measurable layers:
1. Strict system prompt, delimited context, "answer only from context or use the refusal template".
2. A retrieval-confidence gate: if the top rerank or similarity score is below τ, refuse without calling the LLM, which also saves the Kaggle GPU.
3. Regex redaction of Vietnamese PII before logging or sending text to any free-tier judge.
4. Optionally Llama Prompt Guard 2 86M (multilingual mDeBERTa). Vietnamese is not among its evaluated languages, so measure it on your own Vietnamese injection probes.

Report guardrail behaviour as metrics from the golden set (refusal precision/recall, injection block rate).

### Cited Findings
- **Llama Prompt Guard 2**:
  - The 86M model is built on mDeBERTa-base and is trained to detect English and non-English injections and jailbreaks. The 22M model is on DeBERTa-xsmall, which has no multilingual pretraining, so the gap between the two is larger on multilingual data.
  - Evaluated languages are English, French, German, Hindi, Italian, Portuguese, Spanish and Thai. Vietnamese is not listed.
  - Binary output (benign/malicious). 512-token window, so split longer inputs.
  - Meta's own numbers: latency 19.3 ms (22M) vs 92.4 ms (86M); AUC .995 vs .998; 88.7% vs 97.5% detection at 1% FPR.
  - Gated, Llama 4 Community License.
  
  — [HF Llama-Prompt-Guard-2-86M](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M); [HF Llama-Prompt-Guard-2-22M](https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-22M); [Meta model card](https://www.llama.com/docs/model-cards-and-prompt-formats/prompt-guard/)
- Gemini's unpaid terms: "Do not submit sensitive, confidential, or personal information to the Unpaid Services." — [AI Studio terms](https://aistudio.google.com/docs/terms)
- Langfuse recommends a scores-only public key for browser feedback, with the secret key server-side. — [Langfuse user feedback](https://langfuse.com/docs/observability/features/user-feedback)
- A third-party portfolio guide names evaluation, guardrails and access control as what separates a project from thousands of "chat with your PDF" clones (opinion). — [DEV: 5 AI portfolio projects that get you hired in 2026](https://dev.to/klement_gunndu/5-ai-portfolio-projects-that-actually-get-you-hired-in-2026-5bpl)

### Inferences
- **Threat model** (worth a short ADR):
  - The corpus is curated public legal text, so indirect injection via documents is low risk.
  - Direct injection via the chat box and abuse of the GPU endpoint are the realistic risks.
  - Mitigations: rate limiting on the Vercel API, a shared-secret token between Vercel and the Kaggle tunnel, max input length, and no tool use or agents, so injection impact is limited to bad text.
- **Out-of-domain refusal**: tune τ on the golden set's unanswerable and OOD items and report a small confusion matrix (correct refusals, false refusals, hallucinated answers). This is one of the most persuasive numbers for a legal assistant.
- **Vietnamese PII regexes** (patterns to verify before use): CCCD 12 digits, old CMND 9 digits, mobile numbers `(0|+84)` plus 9 digits, email, tax code (MST) 10 or 13 digits. Redact in logs and Langfuse traces, and never send user text to free-tier judges.
- **Adversarial test items** in the golden set: "Bỏ qua hướng dẫn trước đó…", role-play jailbreaks, requests for legal advice outside the corpus, and English/Vietnamese code-switching. Keep them as a promptfoo red-team YAML or pytest cases so they run in CI against a mocked LLM (format checks) and in the full eval (real model).

### Gaps
- I found no Vietnamese-specific prompt-injection classifier or benchmark, and no independent evaluation of Prompt Guard 2 on Vietnamese.
- I did not research Microsoft Presidio's Vietnamese recognizer support.

---

## 7. What interviewers and hiring managers look for in RAG portfolio projects (2025-2026)

### Takeaway
The consistent signal across hiring-side writing is evidence over assembly:
- a real narrow corpus;
- a labelled test set with a baseline and at least two compared approaches (ablation table);
- error analysis;
- cost and latency numbers;
- a README that documents decisions, trade-offs and limitations;
- a demo that cannot embarrass you (a recorded fallback when the model is offline).

Naming frameworks is weak evidence. I found no first-hand Reddit or HN threads in this session. The sources are one named hiring-side author plus blog and SEO-grade guides, so treat their percentages as opinion.

### Cited Findings
- **Bouchard (hiring AI engineers; Mar 2026, updated Aug 2026)**:
  - "Writing LangChain or Pinecone on a resume does not show whether you can build a reliable product."
  - "One polished project with evaluation, deployment, monitoring, and an honest README" beats several generic demos.
  - A strong RAG example "answers from a real documentation corpus, cites evidence", with a verified test set and a baseline.
  - Evals are "the unit tests of AI engineering": ground truth, at least two compared approaches, quantitative results, error analysis, and cost in the evaluation.
  - "A demo that worked on one cherry-picked example tells an interviewer almost nothing."
  - Re-run every public project in a fresh environment: "A broken setup or dead link signals that you do not maintain what you ship."
  - "The output matters. Your decisions matter more."
  
  — [louisbouchard.ai](https://www.louisbouchard.ai/what-i-look-for-when-hiring-ai-engineers/)
- A repo with an eval suite (an `evals/` directory, Braintrust or promptfoo config, a results table in the README) is "rare and immediately impressive". It also claims "has an eval suite" is the "#1 portfolio signal" in 2026 hiring-manager surveys, which is unsourced. — [techinterview.org, The AI Portfolio in 2026 Interviews](https://www.techinterview.org/post/3233475399/ai-portfolio-built-with-ai-2026-interviews/)
- A RAG resume project needs a narrow real document set, a documented chunking and retrieval strategy, recall@k on a labelled test set, a README on trade-offs and failure modes, and a live demo. Otherwise it reads as a tutorial clone (commercial blog, opinion). — [Slategit](https://slategit.com/blog/rag-project-for-resume-build-one-recruiters-open)
- Before/after eval comparisons around a pipeline change make the strongest resume bullet ("The before/after comparison is your bullet"). — [5 LLM Eval Projects That Signal Senior-Level Thinking (Google Doc)](https://docs.google.com/document/d/1JrwCVhrDScXxZ_1l9s04TmSUj4BaptTU/mobilebasic)
- Interviewers check that you can describe the RAG architecture in the correct component order. Be candid that a portfolio project is not production software. — [FACE Prep, explaining a RAG project in interviews 2026](https://faceprep.in/article/how-to-explain-a-rag-project-in-an-ai-ml-interview-2026/)
- The reference format for an ablation story is Anthropic's Contextual Retrieval: a stepwise table or chart of one failure metric (1−recall@20) as each technique is added, with per-dataset appendices (Sep 2024, OLDER). — [Anthropic](https://www.anthropic.com/news/contextual-retrieval)
- Hamel and Liu frame the method interviewers increasingly expect: retrieval IR metrics first, then validated judges, then error analysis. — [Hamel](https://hamel.dev/blog/posts/evals-faq/how-should-i-approach-evaluating-my-rag-system.html); [Liu](https://jxnl.co/writing/2025/05/19/there-are-only-6-rag-evals/)

### Inferences: portfolio differentiators (ranked by signal per effort)
1. **Ablation table on your golden set**:
   - Rows: Postgres FTS/BM25 → dense → hybrid (RRF) → hybrid + rerank → + structure-aware chunks with header context ("Luật X > Chương Y > Điều Z") → + Vietnamese word segmentation or diacritic normalisation for BM25.
   - Columns: Recall@5/10, MRR@10, nDCG@10, p50/p95 latency, and a significance marker from ranx.
2. **Per-question-type breakdown** (single-hop vs multi-hop vs numeric vs unanswerable), plus an **error-analysis section** with the top 3 failure modes and real examples and what you changed.
3. **Judge validation**: "the judge agrees with my labels on N=40 items (κ=…)". This is rare in portfolios and directly addresses the multilingual-judge reliability problem.
4. **Refusal/guardrail metrics**: a confusion matrix on unanswerable, OOD and injection items.
5. **Citation accuracy**: article-level clickable citations (open the source docx/pdf at that Điều) and citation precision/recall numbers.
6. **CI eval gate visible on PRs**: a sticky comment with a metric diff and a badge. Show at least one PR where the gate caught a regression. That PR is a strong interview story.
7. **Cost and latency table**: $0/month bill of materials (Vercel, Supabase, Kaggle, Langfuse Hobby, free judge), plus an honest estimate of what 10k queries/day would cost on paid GPUs. Per-stage latency comes from Langfuse traces, including the Kaggle cold start.
8. **Offline-resilient demo**:
   - A 60-90 s demo video or GIF at the top of the README.
   - A "Kaggle offline" banner in the UI, with precomputed answers for featured questions and retrieval-only search that still works.
   - An `/health` status indicator.
   
   This answers the "model only online during demos" constraint head-on.
9. **ADRs** (`docs/adr/000N-*.md`): pgvector hybrid vs a dedicated vector DB, self-hosted LLM vs API, no LangChain, article-level chunking, git-versioned prompts, free judge for offline eval only.
10. **Architecture diagram** (Mermaid renders natively on GitHub) plus a request sequence diagram.
11. **Dataset card for the golden set**: creation method, % human-edited, type quotas, license, known biases. Link the public benchmarks used for component selection.
12. **Vietnamese/legal domain depth**: word segmentation, diacritics-insensitive search, amendment and effective-date handling (văn bản hết hiệu lực), cross-reference-aware multi-hop. This is something generic RAG demos lack.
13. **Reproducibility**: `make eval-retrieval` runs from a fresh clone with no GPU. Test the setup instructions in a clean environment (Bouchard's dead-link warning).
14. **Honest limitations section**: small n, judge reliability in Vietnamese, corpus size, not legal advice.
15. **Feedback loop**: thumbs-down traces get reviewed and become new golden items, documented as a flywheel.

### Gaps
- No first-hand Reddit (r/MachineLearning, r/LocalLLaMA, r/cscareerquestions) or HN threads were surfaced by the searches. Community-sentiment claims are therefore not sourced here.
- No hard data (surveys with methodology) exists in the sources about what fraction of hiring managers value evals. Only opinion pieces were found.

---

## 8. Framework choice for a portfolio RAG in 2026: plain Python vs LangChain vs LlamaIndex vs Haystack vs DSPy

### Takeaway
Use plain Python: FastAPI, a Postgres/Supabase client with your own hybrid SQL function, httpx to the vLLM OpenAI-compatible endpoint, ranx for eval, and pinned RAGAS or DeepEval only in the eval code path. This is the most respected and least risky choice for a single-pipeline RAG on Vercel serverless. It also keeps every decision visible to interviewers. Frameworks earn their keep for connectors and agentic orchestration, which this project doesn't need. DSPy is an optional stretch for prompt optimisation against the golden set.

### Cited Findings
- A worked comparison from Oct 2026 concludes LangChain is not required for production RAG. Frameworks help with reusable connectors, orchestration and team-standard patterns. Custom logic pays off for things like hierarchical PDF parsing. — [bswen, Do You Really Need LangChain for RAG in 2026?](https://docs.bswen.com/blog/2026-10-16-do-you-need-langchain-for-rag)
- A standard LangChain install could pull in 80+ packages (2024 report, OLDER). — [Substack: Why you might not need LangChain](https://shuvrojit.substack.com/p/why-you-might-not-need-langchain)
- Blog claims of 140-210 ms per-request overhead for LangChain 0.3 show no rigorous methodology. Treat them as low-quality. — [DEV (johalputt)](https://dev.to/johalputt/why-you-should-never-use-langchain-03-for-production-ai-apps-in-2026-raw-api-calls-are-30-more-3ki8)
- Hiring view: framework names on a resume don't prove you can build a reliable product. — [Bouchard](https://www.louisbouchard.ai/what-i-look-for-when-hiring-ai-engineers/)
- RAGAS v0.4.3 added a DSPy optimizer, so DSPy-style prompt optimisation now sits close to the eval tooling. — [Ragas releases](https://github.com/explodinggradients/ragas/releases)
- The RAGAS stable docs rely on LangChain wrappers for LLM setup. Using RAGAS can pull LangChain in as an eval-only dependency. — [Ragas docs](https://docs.ragas.io/en/stable/getstarted/rag_testset_generation/index.md)

### Inferences
- **Recommendation**: plain Python in the serving path. Allow heavier libraries (RAGAS/DeepEval, and LangChain transitively) only in `eval/` with a separate `requirements-eval.txt`, so the Vercel bundle stays small and cold starts fast. The Vercel function-size limit was not checked in this research. Record this in ADR-000X ("No orchestration framework").
- LlamaIndex or Haystack are defensible if you want their document parsers or pipelines, but for 10-30 legal docs a custom docx/pdf parser that is aware of legal structure (Phần/Chương/Mục/Điều/Khoản/Điểm) is both better and a stronger domain signal.
- **DSPy as a stretch**: optimise the answer or citation prompt against a train split of the golden set and report test-split gains. With ~100 items, use a held-out split to avoid overfitting claims.

### Gaps
- No Hacker News or Reddit threads were found that give community consensus. The evidence comes from blogs of mixed quality.
- I found no 2026 benchmarks comparing current LangChain, LlamaIndex or Haystack versions on overhead.

---

## 9. Synthesis: what is the concrete zero-budget evaluation plan end to end?

### Takeaway
A three-tier plan:
1. **Tier A (every PR, CPU, deterministic)**: retrieval metrics, deterministic answer-format and contract tests, guardrail format tests.
2. **Tier B (manual dispatch while Kaggle is online)**: end-to-end generation, deterministic generation checks (citations, numbers, refusals), local LLM judge, plus a free hosted judge on a calibration subset.
3. **Tier C (continuous, during demos)**: Langfuse traces, latency, thumbs feedback, and turning bad traces into new golden items.

All numbers land in dated, committed result files that generate the README tables.

### Cited Findings
- Order of work: IR metrics first, then validated LLM judges, then error analysis. — [Hamel](https://hamel.dev/blog/posts/evals-faq/how-should-i-approach-evaluating-my-rag-system.html); [Liu](https://jxnl.co/writing/2025/05/19/there-are-only-6-rag-evals/)
- Tools: ranx for IR metrics, significance tests and RRF ([ranx](https://github.com/AmenRa/ranx)); RAGAS v0.4.x or DeepEval for judge metrics and synthetic goldens ([Ragas releases](https://github.com/explodinggradients/ragas/releases); [DeepEval](https://deepeval.com/docs/synthesizer-generate-from-docs)); the promptfoo action or `gh pr comment` for PR reports ([promptfoo](https://promptfoo.dev/docs/integrations/github-action)); Langfuse Hobby for traces, feedback and prompt or dataset management ([Langfuse pricing](https://langfuse.com/pricing)).
- The free judge must not receive sensitive or personal data on unpaid tiers. — [AI Studio terms](https://aistudio.google.com/docs/terms)

### Inferences
**Repository layout (proposal)**
```
eval/
  golden/qa_v1.jsonl          # ~100-120 items, typed, article-level gold
  golden/DATASET_CARD.md
  qrels.json                  # derived from golden (article-level)
  cache/query_emb.<model>.parquet
  cache/rerank_scores.<model>.parquet
  baselines/main.json         # auto-updated on push to main
  prompts/judge_*.vi.txt      # Vietnamese judge prompts (validated)
  labels/human_judgments.csv  # ~40 items for judge validation
  run_retrieval.py            # Tier A
  run_full.py                 # Tier B
  results/YYYY-MM-DD_<sha>.{json,md}
.github/workflows/
  ci.yml                      # lint, unit, contract tests (mock LLM)
  eval-retrieval.yml          # Tier A gate on PRs
  eval-full.yml               # Tier B, workflow_dispatch(kaggle_url)
docs/adr/  docs/architecture.md (Mermaid)
```

**Metric sheet** (targets are suggestions to set after the first baseline)
| Layer | Metric | How computed | Runs where |
|---|---|---|---|
| Retrieval | Hit@1, Recall@5/10/20, MRR@10, nDCG@10 (article-level) | ranx over cached embeddings + frozen index | PR gate (CPU) |
| Retrieval | Same, per question type and per config (BM25 / dense / hybrid / +rerank) | ranx `compare()` + significance | PR gate + README ablation |
| Generation (deterministic) | Citation validity, citation precision/recall vs gold articles, numeric/date match, answer-language check | Python regex and set ops | Tier B (and CI with recorded answers) |
| Generation (judge) | Faithfulness (A|C), answer correctness vs reference, context relevance (C|Q) | Local Kaggle judge (JSON-constrained); free hosted judge on a subset; judge validated on human labels | Tier B |
| Guardrails | Refusal precision/recall on unanswerable/OOD; injection block rate | Template match + golden adversarial items | Tier B (+ format tests in CI) |
| Ops | p50/p95 latency per stage, error rate, thumbs-up ratio, cost $0 | Langfuse traces/scores | Tier C |

**Order of execution** (each step produces a README artifact)
1. Write ~30 manual questions first, covering every type, to learn the corpus.
2. Draft ~100 more with an LLM, edit them all, and freeze `qa_v1`.
3. Build the retrieval eval and the ablation table. Get Recall@10 to an acceptable level before touching prompts.
4. Label ~40 answers by hand, validate the judge prompt (report agreement), then run the full eval.
5. Do error analysis, fix the top failure mode, and re-run for the before/after bullet.
6. Wire up the CI gate and baselines. Open a demo PR that shows the gate catching a regression.
7. Add Langfuse tracing and feedback, the offline demo fallback and video, ADRs, and the dataset card.

### Gaps
- Exact free-tier quotas (Groq per model, Gemini per model, OpenRouter free list) are volatile and only partly verified against primary sources. Re-check them on the provider consoles at implementation time.
- I found no source that measures how well RAGAS or DeepEval synthesizers and metrics perform on Vietnamese legal text. The plan's reliance on human review and judge validation is the hedge against that gap.

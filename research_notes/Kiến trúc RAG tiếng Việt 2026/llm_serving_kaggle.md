# Self-hosting a Vietnamese-capable open LLM on a free Kaggle GPU and exposing it as an OpenAI-compatible API (state as of 2026-11-22)

Scope note: I researched this on 2026-11-22. Search results came back as summaries, so a few numbers below are taken from secondary sources and are flagged as such. Anything marked "(prior knowledge, verify)" comes from my training data (cutoff mid-2026) and was not re-checked against a live source in this session.

## 1. Kaggle free GPU hardware, quotas, sessions, background runs, and ToS on public endpoints/tunnels

### Takeaway
The only usable free GPU on Kaggle for this project is **T4 x2** (2 x 16 GB, sm_75): about **30 GPU-h/week** and **12 h per session**. The P100 no longer works with Kaggle's current PyTorch, and current vLLM needs compute capability 7.5 or higher anyway. The biggest risk is the rules, not the hardware. Kaggle's Terms and Acceptable Use Policy (AUP) limit use to personal, non-commercial use that does not benefit third parties, and they name "server farming" as abuse. A public LLM endpoint behind a tunnel, called by a web app that interviewers use, is in a grey-to-prohibited zone. There is one unverified 2026 report of an account ban.

### Cited Findings
- Kaggle's accelerator menu offers "GPU T4 x2" or "GPU P100". Most 2026 guides put the free quota at about 30 GPU-h/week, but Kaggle publishes no fixed number and the quota "floats". Colab Pro/Pro+ accounts linked to Kaggle reportedly get +15/+30 GPU-h/week. — [gpuperhour: Free Cloud GPUs in 2026](https://gpuperhour.com/blog/free-cloud-gpus-and-credits); [resourify (claims 50 h, an outlier)](https://resourify.com/resources/kaggle)
- Quotes from Kaggle docs (as reproduced in an article dated 2026-10-29): the GPU quota "resets weekly and is 30 hours or sometimes higher depending on demand and resources". Sessions last 12 h for CPU/GPU and 9 h for TPU. "In busy times, you might be placed in a queue." The idle timeout is **conflicting**: the notebook docs say "20 minutes of idle time", while the GPU tips say a "60 minute idle timeout". — [maborak: Kaggle is not a free AI server (2026-10-29)](https://www.maborak.com/blog/kaggle-free-gpu-ai-server)
- A Kaggle T4x2 LLM-server write-up from May 2026 confirms "up to 12 hours per session and 30 GPU hours per week" on T4 x2 (about 30 GB VRAM combined). `kaggle kernels push` cannot choose the GPU type, so you may get a P100. The author opens the notebook in the browser, selects T4 x2 and clicks Run All. Startup took about 5–6 min per session with binaries and models cached as Kaggle Datasets. — [dev.to: Free 35B multimodal LLM server on Kaggle GPU](https://dev.to/tahsine/free-35b-multimodal-llm-server-on-kaggle-gpu-accessible-from-any-openai-compatible-client-4m2h)
- **P100 is effectively dead.** Kaggle docker-python issue #1546 (opened 2026-03-20) reports that the installed PyTorch supports sm_70 and newer only, so the P100 (sm_60) fails. Kaggle PR #1544, "Mark pytorch tests as p100 exempt", says the newer PyTorch was needed for RTX Pro / sm_120 cards and "no longer works on P100s". — [Kaggle docker-python #1546](https://www.goodfirstissue.org/Kaggle/docker-python/issues/1546); [Kaggle PR #1544](https://github.com/Kaggle/docker-python/pull/1544)
- PyTorch 2.8 cu128 builds dropped Maxwell and Pascal (sm_50/sm_60). — [Clore.ai CUDA/PyTorch compatibility guide](https://docs.clore.ai/guides/getting-started/cuda-pytorch-compatibility)
- Current vLLM states "Compute capability 7.5 or higher (T4, RTX20xx, A100, L4, H100, B200, etc.)". That excludes the P100 (6.0) and the V100 (7.0). — [vLLM GPU installation docs](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/)
- **ToS/AUP (effective 22 June 2025), as quoted:** "You will only use the Services for your own internal, personal, non-commercial use". The Terms exclude use "on behalf of or for the benefit of any third party". The AUP lists "server farming", "activity unrelated to ML data science" and "tools for circumvention/obfuscation". Also: "abuse or misuse of GPU resources may result in the suspension or termination of your Kaggle account." The author reads a public inference endpoint as the "server farming" case and a public tunnel as "close to" circumvention. — [maborak (2026-10-29)](https://www.maborak.com/blog/kaggle-free-gpu-ai-server); [Kaggle Terms](https://kaggle.com/terms)
- A Kaggle product-feedback thread titled "Tutorial wave is converting Kaggle Notebooks into free public LLM servers - GPU availability is degrading" asks Kaggle to act. According to a search summary, it claims a "suspicious action: request to local network" abuse filter is catching Ollama/vLLM and tunnel setups. I could not load the thread body, so this is unverified and I found no staff reply. — [Kaggle discussion 743895](https://www.kaggle.com/discussions/product-feedback/743895)
- A commenter on the May 2026 dev.to tutorial said their account was **banned on the second run** and the appeal was denied, with the reason given as "server farm". This is a single unverified report. — [dev.to tutorial comments](https://dev.to/tahsine/free-35b-multimodal-llm-server-on-kaggle-gpu-accessible-from-any-openai-compatible-client-4m2h)
- In an older case, Kaggle "blocked any attempt of creating an SSH tunneling into a running Kaggle kernel", and the remokaggle repo warns that this "WILL GET YOUR KAGGLE ACCOUNT BANNED". — [lamhoangtung/remokaggle](https://github.com/lamhoangtung/remokaggle)
- A softer reading says LLM inference for research or experimentation is acceptable use, while commercial production workloads may violate the terms. — [logicity](https://logicity.in/en/blog/how-to-run-70b-llms-free-using-kaggle-s-hidden-gpu-tier)
- Background batch runs ("Save & Run All") run "to completion in a clean container" inside the same 12 h limit. No source says they are meant to host a server. — [maborak](https://www.maborak.com/blog/kaggle-free-gpu-ai-server)

### Inferences
- For 1–2 h demo sessions, 30 GPU-h/week covers roughly 15–25 demos a week. Quota is not the bottleneck. Account risk is.
- To lower (not remove) the ToS risk: start the notebook only for a demo, stop it afterwards, keep the endpoint behind a bearer token, never publish the tunnel URL, and don't keep the GPU running idle. Also build a **graceful "LLM offline" mode** in the Vercel app, plus a recorded demo video as a fallback, so a banned or queued Kaggle account doesn't break an interview. Use one Kaggle account only, since multiple accounts are an explicit ToS violation per maborak.
- A commit (Save & Run All) whose last cell blocks (for example `server.wait()`) would probably keep the server alive headlessly for up to 12 h. That avoids the interactive idle-timeout question, but it is the most "server-farm-like" pattern. Untested.
- The PR #1544 mention of "RTX Pro / sm_120 cards" hints that Kaggle added Blackwell GPUs somewhere, probably competitions or paid tiers. I found nothing showing they are on the free menu.

### Gaps
- No official Kaggle page was loaded directly. The quota, session and idle numbers come via secondary quotes, and the 20-min vs 60-min idle conflict is unresolved, including whether a long-running blocking cell counts as "idle".
- Whether internet access still requires phone verification in 2026: I did not confirm this. (Prior knowledge, verify: it historically did.)
- TPU details (v5e-8, weekly TPU hours) were not researched. A TPU is not useful for llama.cpp, and vLLM-TPU is out of scope.
- No official Kaggle statement on tunnels/ngrok or cloudflared specifically.

## 2. Best Vietnamese-capable open instruct LLMs that fit on T4 x2 (32 GB, sm_75, no bf16, no FA2); Vietnamese evidence; licenses

### Takeaway
No public leaderboard yet scores Qwen3, Qwen3.5 or Qwen3.6 on VMLU. Indirect evidence says Qwen3-generation 8B models are far stronger in Vietnamese than the 2024 Vietnamese fine-tunes: a Qwen3-VL-8B-Thinking fine-tune scores 74.9 vs 50–57 for Vistral, SeaLLM, Qwen2.5-7B and Vi-Qwen2-7B-RAG. The best open models on VMLU (85–90) are private Vietnamese corporate models. The practical choice is **Qwen3-8B** (plain GQA transformer, Apache-2.0, works in every engine on Turing) or **Qwen3.5-9B** (newer, Apache-2.0, but a hybrid Gated-DeltaNet architecture with unproven T4 support in vLLM). The stretch option is **Qwen3.6-35B-A3B** (MoE, 3B active), which has already been run on Kaggle T4x2 with llama.cpp. Keep **AITeamVN/Vi-Qwen2-7B-RAG** as a RAG-specialised baseline to A/B test. It was trained for Vietnamese negative rejection and noisy context, but it is a 2024-vintage Qwen2 model with an 8K context.

### Cited Findings
- **VMLU leaderboard (vmlu.ai), selected rows:** QwQ-32B 76.13; Qwen2.5-72B-Instruct-AWQ 69.17; gemma-2-9b-it 59.04; Qwen2.5-7B-Instruct 57.51; BloomVN-8B-chat 56.56; Vintern-3B-beta 54.81; SeaLLM-7B-v2.5 53.30; Ml4uLLM-7B-Chat 52.08; Vistral-7B-Chat 50.07; DeepSeek-R1-Distill-Qwen-7B 48.56; Qwen2-7B-Instruct 28.85; PhoGPT-7B5-Instruct 24.01. **Unicorn-VL-R3 (base Qwen3-VL-8B-Thinking): 74.87 (2026-01-16).** Qwen3, Qwen3.5, Arcee VyLinh and GreenMind do not appear. — [VMLU leaderboard](https://vmlu.ai/leaderboard)
- **Top of the VMLU fine-tuned table, all private (not downloadable):** VAI-LLM-v1.6+ (Viettel AI) 90.04 (2026-08-06); V-LLM v2.1 (VinSmart Future) 89.85; MISA-AI-2.0 87.93 (2026-10-23); Vi-Qwen3.6 (Zoom AI Lab) 85.36 (2026-05-04); VNPTAI.IO up to 79.61. — [VMLU leaderboard](https://vmlu.ai/leaderboard)
- Viettel AI's VAI-LLM is a 120B model on NVIDIA Nemotron 3 Super. I found no Hugging Face release, and at 120B it would not fit a T4x2 anyway. — [Viettel AI news](https://viettelai.vn/en/tin-tuc/viettel-ai-ghi-nhan-ket-qua-buoc-dau-trong-hop-tac-cung-nvidia)
- The VMLU README warns users to treat leaderboard scores with caution. VMLU has 10,880 multiple-choice questions across 58 subjects (Zalo AI + JAIST). — [VMLU GitHub](https://github.com/ZaloAI-Jaist/VMLU/); [VMLU ACL 2025 paper](https://aclanthology.org/2025.acl-long.563)
- **AITeamVN/Vi-Qwen2-7B-RAG:** fine-tuned from Qwen2-7B-Instruct; **Apache-2.0**; 8,192-token context. Trained for extracting answers from noisy documents, **refusing when the context lacks the answer**, multi-document integration and context-relevance judgement (the card claims about 99%). VMLU 56.04. The recommended prompt is Vietnamese, with "Ngữ cảnh"/"Câu hỏi"/"Trả lời" sections and temperature 0.1. Sibling models are 1.5B and 3B (Qwen2.5). A "next release" is promised, but there is no Qwen3 version as of the card. — [HF model card](https://huggingface.co/AITeamVN/Vi-Qwen2-7B-RAG)
- **Qwen3.5 small models:** four dense models at 0.8B, 2B, 4B and **9B**, completed in March 2026, open-weight under **Apache 2.0**. — [NYU Shanghai RITS: Qwen 3.5 small models](https://rits.shanghai.nyu.edu/ai/qwen-3-5-small-models-9b-parameters-that-beat-120b/)
- Qwen3.5-9B alternates **3 Gated-DeltaNet (linear-attention) blocks to 1 full-attention block**. The official vLLM recipe needs **vLLM ≥ 0.17.0** and lists "single 24 GB GPU (RTX 4090 / L4 / A10G / H100)". The T4 is not listed. GGUF: `unsloth/Qwen3.5-9B-GGUF`. AWQ: `QuantTrio/Qwen3.5-9B-AWQ`. — [vLLM recipe Qwen/Qwen3.5-9B](https://recipes.vllm.ai/Qwen/Qwen3.5-9B); [unsloth GGUF](https://huggingface.co/unsloth/Qwen3.5-9B-GGUF); [QuantTrio AWQ](https://huggingface.co/QuantTrio/Qwen3.5-9B-AWQ)
- A third-party calculator estimates Qwen3.5-9B 4-bit on a T4 at "fits T4 · 9.4 GB free · ~33 tok/s". This is an estimate, not a benchmark. — [llmrun.dev](https://llmrun.dev/model/qwen-qwen3-5-9b?hw=g.t4)
- **Qwen3.6:** Qwen3.6-27B (dense, multimodal, April 2026) and Qwen3.6-35B-A3B (MoE, 3B active), both **Apache 2.0**. I found no Qwen3.6 small dense models (4B/9B). — [RITS: Qwen3.6-27B](https://rits.shanghai.nyu.edu/ai/qwen3-6-27b-a-dense-27b-model-that-beats-a-397b-moe-on-coding); [RITS: Qwen3.6-35B-A3B](https://rits.shanghai.nyu.edu/ai/qwen3-6-35b-a3b-alibaba-open-sources-a-frontier-class-agentic-coder/)
- **Qwen3.6-35B-A3B has been served on Kaggle T4x2** with llama.cpp, Unsloth `UD-Q4_K_XL` (about 22 GB) plus mmproj, fully GPU-offloaded. The article did not report tokens/s. — [dev.to (May 2026)](https://dev.to/tahsine/free-35b-multimodal-llm-server-on-kaggle-gpu-accessible-from-any-openai-compatible-client-4m2h)
- Gemma 4 models with head_dim=512 fail on Turing (SM75) in vLLM: the Triton unified-attention kernel needs about 98 KB of shared memory per block, but Turing offers 64 KB. This was still unresolved as of v0.30.0rc1 and needs an unmerged community patch. — [vLLM forum: OutOfResources on Turing](https://discuss.vllm.ai/t/title-outofresources-shared-memory-98304-65536-on-turing-sm75-global-attention-layers-with-head-dim-512/2990)
- Indirect multilingual signal: on the Burmese benchmark BURMESE-SAN, Qwen3-8B scores well above Qwen2.5-7B and SeaLLMs-v3-7B on most columns. Burmese is not Vietnamese. — [BURMESE-SAN arXiv 2602.18788](https://arxiv.org/pdf/2602.18788)
- A vendor guide (SiliconFlow) lists Qwen3-8B among its top 2026 open picks for Vietnamese, with no benchmark numbers shown. — [SiliconFlow (JA)](https://www.siliconflow.com/ja/articles/best-open-source-llm-for-vietnamese)
- T4 spec: 16 GB GDDR6, about 320 GB/s memory bandwidth, Turing tensor cores (FP16/INT8, no BF16). — [NVIDIA T4 product page](https://www.nvidia.com/en-us/data-center/tesla-t4/)

### Inferences
- **VRAM math, weights (fp16 = 2 B/param, Q4_K_M ≈ 0.6 B/param, AWQ-4bit ≈ 0.7 B/param including unquantised embeddings):**
  - Qwen3-8B (8.2B): fp16 ≈ 16.4 GB, which does not fit one T4 (about 15 GiB usable) but does fit TP=2 at about 8.2 GB/GPU. AWQ ≈ 5.7–6 GB. Q4_K_M GGUF ≈ 5.0 GB. Q5_K_M ≈ 5.9 GB. Q8_0 ≈ 8.7 GB.
  - Qwen3-14B: Q4_K_M ≈ 9 GB, so it fits one T4 with little KV headroom, or both GPUs comfortably.
  - Qwen3.5-9B: Q4_K_M ≈ 5.5–6 GB. Only about 1/4 of its layers keep a KV cache, so long contexts are cheap.
  - Qwen3.6-35B-A3B UD-Q4_K_XL ≈ 22 GB (cited). Split across two T4s that is about 11 GB per GPU, leaving about 3–4 GB per GPU for KV, the embedder and the reranker. Tight but proven to load.
- **KV cache, Qwen3-8B** (36 layers, 8 KV heads, head_dim 128, fp16): 2 × 36 × 8 × 128 × 2 B = **144 KiB/token**, so an 8K context ≈ 1.13 GiB per sequence and 16K ≈ 2.25 GiB. A typical RAG prompt (about 3–6K tokens of context) at 2–4 concurrent sequences needs about 3–5 GB. With a Q4/Q5 model that fits on **one T4**, which leaves GPU1 free for embedding and reranking. (Architecture numbers from prior knowledge of the Qwen3-8B config; verify in config.json.)
- **Expected decode speed** (memory-bandwidth bound, 320 GB/s): the ceiling ≈ 320 / bytes read per token. Q4_K_M 8B (5 GB) gives at most ~64 tok/s, so a realistic single-stream rate is **~25–40 tok/s**, consistent with the ~33 tok/s estimate for Qwen3.5-9B. fp16 8B with vLLM TP=2 reads about 8.2 GB per GPU per token, so roughly 20–30 tok/s. Qwen3.6-35B-A3B Q4 reads about 2 GB of active weights per token, so in theory it could match or beat the 8B on decode, but layer-split adds latency (unbenchmarked). Prefill on a T4 (65 TFLOPS FP16) for a 4K-token RAG prompt should take roughly 1–3 s with llama.cpp (unbenchmarked estimate).
- **Ranking for this project:** (1) Qwen3-8B Q5_K_M/Q4_K_M as the safe default. (2) Qwen3.5-9B Q4_K_M as the newer A/B candidate, llama.cpp only. (3) Qwen3.6-35B-A3B UD-Q4_K_XL for the best answer quality if VRAM headroom holds with the embedder and reranker. (4) Vi-Qwen2-7B-RAG as a Vietnamese RAG-faithfulness baseline. **Avoid on T4:** Gemma 4 in vLLM (head_dim 512 bug), and any model needing bf16 or FA2.
- Licenses: Qwen3, Qwen3.5 and Qwen3.6 are Apache-2.0 (Qwen3 from prior knowledge, the others cited), and so is Vi-Qwen2-7B-RAG. All are fine for a portfolio. Vistral-7B-Chat and SeaLLMs carry custom or older licenses and score lower on VMLU, so they are not worth using.

### Gaps
- No VMLU, ViLLM-Eval or Vietnamese RAG-faithfulness score for Qwen3-8B, Qwen3.5-9B or Qwen3.6 was found. A head-to-head on the user's own Vietnamese eval set (faithfulness and refusal rate) is needed.
- I could not determine whether Vi-Qwen3.6 (Zoom AI Lab) is downloadable. The leaderboard shows the corporate rows as private.
- Arcee VyLinh, GreenMind, and the Zalo, FPT and VinAI 2025–2026 open models were not found with T4-relevant releases or scores. Not researched further.
- No measured tokens/s on Kaggle T4 for any of these models. All speed numbers are bandwidth-based estimates.

## 3. Serving engines on T4 (vLLM, SGLang, llama.cpp, TGI, Ollama): what actually works on Kaggle in 2026

### Takeaway
**llama.cpp `llama-server` (GGUF)** is the most reliable engine on Kaggle T4 in 2026. It has been demonstrated with Qwen3.6-35B-A3B on T4x2, its kernels are not tied to Ampere, it handles new architectures like Qwen3.5's Gated-DeltaNet, and it exposes `/v1/chat/completions` with streaming. vLLM officially supports T4 (CC ≥ 7.5, fp16 only), but the Turing path has real breakage: Marlin and compressed-tensors quant kernels need sm_80, Gemma 4 fails on Turing, and Qwen3.5-on-T4 is unverified. Use vLLM only with a plain dense model such as Qwen3-8B (AWQ-format or fp16 TP=2) with `--dtype half --enforce-eager`. Ollama is the easiest install but gives less control.

### Cited Findings
- vLLM: minimum compute capability 7.5 (T4 listed). Wheels are built for CUDA 12.9 (12.8/13.0 also available), Python 3.11–3.14. Install with `uv pip install vllm --torch-backend=auto && vllm download-kernels`, or `pip install vllm --extra-index-url https://download.pytorch.org/whl/cu129`. — [vLLM GPU install docs](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/)
- vLLM attention backends with "Any" compute capability include `TRITON_ATTN` (fp16/bf16/fp32) and `FLEX_ATTENTION` (fp16/bf16/fp32). `FLASH_ATTN` needs ≥ 8.0, and FlashInfer is listed for 8.x–9.x. The docs give no SM 7.x selection order (page dated 2026-11-16). — [vLLM attention backends](https://docs.vllm.ai/en/stable/design/attention_backends/)
- Older vLLM (v0.8–v0.9) rejected CC < 8.0 for the V1 engine and fell back to V0. Current docs list T4 as supported, so this behaviour is outdated. — [vLLM forum, Ray/DeepSeek AWQ thread](https://discuss.vllm.ai/t/ray-cluster-deepseek-r1-distill-qwen-32b-awq/1119.md); [vLLM forum T4 cpu-offload](https://discuss.vllm.ai/t/nvidia-t4-cpu-offload-gb-error/493)
- T4 has no native bf16, so pass `--dtype half`/float16 explicitly. — [NVIDIA forum](https://forums.developer.nvidia.com/t/how-to-set-dtype-for-nvidia-nim-3-8b/352121)
- **Quantization pitfall:** on vLLM 0.11.0 with a Turing RTX 5000 (sm_75) at TP=2, `cpatonn/Qwen3-VL-30B-A3B-Instruct-AWQ-4bit` (loaded as `compressed-tensors`) failed with "Quantization scheme is not supported for the current GPU. Min capability: 80. Current capability: 75." The maintainer explained that AWQ on MoE uses the Marlin kernel, "only available for Ampere or later GPUs", and suggested W8A8 or bitsandbytes on an unquantized checkpoint. — [vLLM issue #26297](https://github.com/vllm-project/vllm/issues/26297)
- A persistent sharded-state Qwen2.5-3B checkpoint "validated on a Kaggle Notebook with two Tesla T4" uses `tensor_parallel_size=2`, `dtype=float16`, `enforce_eager=True` and `disable_custom_all_reduce=True`. — [HF waqasm86/vllm-kaggle-models](https://huggingface.co/waqasm86/vllm-kaggle-models)
- There is an unofficial `kaggle-vllm` PyPI package targeting Kaggle 2x T4 (SM75) with TP 1 or 2. I could not load its pins. — [PyPI kaggle-vllm](https://pypi.org/project/kaggle-vllm/)
- Gemma 4 on Turing fails in vLLM (shared-memory 98 KB > 64 KB) up to at least v0.30.0rc1. — [vLLM forum](https://discuss.vllm.ai/t/title-outofresources-shared-memory-98304-65536-on-turing-sm75-global-attention-layers-with-head-dim-512/2990)
- A vLLM forum answer says SM75 support "is not guaranteed in recent versions" for gpt-oss-20B. It looks like an automated reply, so low confidence. — [vLLM forum gpt-oss T4](https://discuss.vllm.ai/t/build-issues-when-serving-gpt-oss-20b-on-tesla-t4-gpus-with-vllm/1673)
- **llama.cpp on Kaggle T4x2 (May 2026):** build with `cmake -DGGML_CUDA=ON -DCMAKE_PREFIX_PATH=/usr/local/nvidia -DCMAKE_CUDA_ARCHITECTURES=75`. This needs `ln -sf /usr/local/nvidia/lib64/libcuda.so /usr/local/cuda/lib64/libcuda.so`, otherwise you get "cannot find -lCUDA::cuda_driver". The compile takes about 26 min, so **save the binaries and all `.so` files as a Kaggle Dataset** (copying only `llama-server` crashes with a missing shared library). Run with `LD_LIBRARY_PATH=/kaggle/working`. In the health check, wait for `status == "ok"`, not just HTTP 200 while it is "loading". Startup is about 5–6 min with cached datasets. — [dev.to](https://dev.to/tahsine/free-35b-multimodal-llm-server-on-kaggle-gpu-accessible-from-any-openai-compatible-client-4m2h)
- A community HF repo hosts `llama-server` prebuilt for T4 sm_75 on Kaggle's image. It is from an unknown publisher, so treat it as untrusted. — [HF afsafwtggg/llama-cpp-t4-cache](https://huggingface.co/afsafwtggg/llama-cpp-t4-cache)
- Ollama on Kaggle with an ngrok tunnel is a documented pattern. — [Medium: Remote LLM server using Kaggle + Ollama](https://medium.com/data-science-collective/create-a-remote-llm-server-using-kaggle-notebooks-and-ollama-acb299ead1e5)

### Inferences
- **Recommended llama.cpp launch on GPU0** (flags from prior knowledge of llama-server; verify with `--help` on the built version):
  `CUDA_VISIBLE_DEVICES=0 ./llama-server -m /kaggle/input/<dataset>/Qwen3-8B-Q5_K_M.gguf -ngl 99 -c 16384 -np 2 -fa on --jinja --host 127.0.0.1 --port 8080 --api-key $LLM_KEY`
  `--jinja` uses the model's chat template, which is needed for Qwen3's thinking toggle. `-fa` FlashAttention in llama.cpp has its own Turing kernels, unlike FA2. For the 35B-A3B MoE, drop `CUDA_VISIBLE_DEVICES` and use `--split-mode layer --tensor-split 1,1` across both GPUs.
- **vLLM fallback (dense Qwen3-8B only):** `vllm serve Qwen/Qwen3-8B-AWQ --dtype half --quantization awq --enforce-eager --max-model-len 16384 --gpu-memory-utilization 0.85`, single GPU. Or `vllm serve Qwen/Qwen3-8B --dtype half --tensor-parallel-size 2 --enforce-eager --disable-custom-all-reduce`. Avoid compressed-tensors/W4A16, Marlin-only and MoE-AWQ checkpoints on T4. Plain AutoAWQ GEMM has a sm_75 minimum in vLLM (prior knowledge, verify). Installing vLLM pulls its own torch over Kaggle's image, which adds a few minutes per session, and the first boot downloads kernels.
- **Thinking mode** (prior knowledge, verify): Qwen3 uses `enable_thinking`. In vLLM send `extra_body={"chat_template_kwargs": {"enable_thinking": false}}`. In llama.cpp use `--jinja` plus `--chat-template-kwargs '{"enable_thinking":false}'` or `--reasoning-budget 0`. Alternatively, Qwen3's `/no_think` soft switch in the user/system message works in any engine. Disable thinking for RAG answers to save latency on T4.
- SGLang and TGI: I found nothing Kaggle- or T4-specific for 2026. SGLang targets sm_80+ attention kernels by default, and TGI has been in maintenance mode (both prior knowledge, verify). Neither is worth the risk on T4.

### Gaps
- No 2026 source confirms vLLM serving Qwen3.5 (Gated-DeltaNet, Triton/FLA kernels) on sm_75.
- No measured tokens/s on Kaggle T4 for llama.cpp or vLLM.
- I did not verify llama-server's current flag names (`-fa on`, `--chat-template-kwargs`, `--reasoning-budget`) or the vLLM AWQ minimum capability against live docs.

## 4. Running the embedding model (BGE-M3) and reranker (bge-reranker-v2-m3) in the same notebook

### Takeaway
Both models are small. BGE-M3 (568M) and bge-reranker-v2-m3 (568M) take about 1.1 GB each in fp16, so roughly 3–4 GB with activations at modest batch sizes. They fit easily on **GPU1** while the LLM uses GPU0, and they fit even alongside the 22 GB Qwen3.6-35B-A3B split if batch sizes stay small. vLLM can serve both through its pooling runner, but only one model per process. The simplest and lowest-risk option is a small FastAPI using sentence-transformers or FlagEmbedding on GPU1 that also acts as the authenticated gateway in front of llama-server.

### Cited Findings
- vLLM supports `BAAI/bge-reranker-v2-m3` (XLMRobertaForSequenceClassification, cross-encoder score/rerank API) and `BAAI/bge-m3` embeddings. `vllm serve <model> --runner pooling` starts pooling mode, and `--runner auto` usually detects it. The endpoints are `/pooling`, plus the specific embed and score/rerank endpoints. — [vLLM pooling models docs](https://docs.vllm.ai/en/v0.17.0/models/pooling_models/); [vLLM scoring docs](https://docs.vllm.ai/en/stable/models/pooling_models/scoring/); [vLLM pooling example v0.12](https://docs.vllm.ai/en/v0.12.0/examples/online_serving/pooling/)
- BGE-M3 in vLLM rejects custom output dimensions with a 400 error ("does not support matryoshka representation"). Its sparse and ColBERT heads are reachable via `"task":"token_embed"` for multi-vector retrieval. — [vLLM pooling docs](https://docs.vllm.ai/en/stable/models/pooling_models/scoring/)

### Inferences
- **Memory split:** GPU0 (15 GiB usable) holds Qwen3-8B Q5_K_M (~6 GB) plus about 4–6 GB of KV, leaving ~3 GB free. GPU1 holds BGE-M3 fp16 (~1.1 GB) and the reranker fp16 (~1.1 GB) plus activations (~1–2 GB at batch 16–32 and max_len 512–1024), leaving more than 10 GB free. That spare room could hold a second LLM for A/B testing, such as Vi-Qwen2-7B-RAG Q5 (~5.4 GB).
- **The gateway pattern** gives one tunnel endpoint, one auth check, and fewer moving parts. A single FastAPI (uvicorn on :8000, GPU1) exposes `/v1/embeddings` (SentenceTransformer `BAAI/bge-m3`, fp16) and `/v1/rerank` (CrossEncoder `BAAI/bge-reranker-v2-m3`, fp16). It reverse-proxies `/v1/chat/completions` to llama-server at 127.0.0.1:8080 with `httpx` streaming passthrough, and checks `Authorization: Bearer <key>` on every route. If you use vLLM for pooling instead, run two extra processes with `--gpu-memory-utilization ~0.3` each on GPU1. vLLM preallocates memory by fraction, so set the fractions explicitly or the processes OOM each other.
- Models: preload all weights as Kaggle Datasets or Models (mounted under `/kaggle/input`) so each session doesn't re-download from HF. This keeps cold start in the ~5-min range.
- Ingestion (embedding the corpus) should run offline, on Kaggle once or locally, with vectors stored in the app's vector DB. The live notebook then only embeds queries and reranks top-k, which is milliseconds of work on a T4.

### Gaps
- I did not verify whether vLLM pooling for XLM-R encoders works on sm_75. The encoder attention backend on Turing is unknown, which is one more reason to prefer sentence-transformers here.
- No measured BGE-M3 or reranker latency on T4.

## 5. Exposing the endpoint publicly with a stable URL, securing it, and streaming/timeout behaviour

### Takeaway
Use the **ngrok free plan's dev domain**. It is a single static `*.ngrok-free.app` (or `.ngrok-free.dev`) hostname per account that "doesn't change when you restart the agent", with no endpoint timeout. Put it in the Vercel env var once. The browser interstitial does not affect server-to-server API calls, and the quotas (20k requests/month, 1 GB egress/month) are enough for demos. **Do not use Cloudflare Quick Tunnels** for this: the URL changes every session and they **do not support SSE**, which breaks streaming. A Cloudflare named tunnel gives a stable URL only if you own a domain added to Cloudflare. Secure everything with a bearer token checked by the gateway or `llama-server --api-key`.

### Cited Findings
- **ngrok free plan:** one auto-assigned dev domain (for example `your-assigned-name.ngrok-free.app`), and it "doesn't change when you restart the agent". Up to 3 online endpoints and 3 concurrent agents. **Timeouts: none.** Custom, reserved and wildcard domains need a paid plan. Monthly quotas: **1 GB data transfer out, 20,000 HTTP requests**, 5,000 TCP connections. Rate limit 4,000 HTTP requests/min. The interstitial warning appears only for HTML browser traffic, "does not affect API clients or programmatic access", and can be skipped with the header `ngrok-skip-browser-warning: <any>` or a non-browser User-Agent. — [ngrok free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)
- ngrok's blog and a third-party blog mention February 2026 pricing and quota changes that tightened the free tier. I could not confirm details beyond the current docs. — [ngrok blog: free static domains](https://ngrok.com/blog/free-static-domains-ngrok-users); [dev.to instatunnel](https://dev.to/instatunnel/ngrok-vs-localhostrun-the-zero-friction-standard-14e)
- **Conflict:** the dev.to Kaggle author says they rejected ngrok because "its free tier cuts streaming responses". ngrok's docs list no timeout and no streaming restriction. — [dev.to](https://dev.to/tahsine/free-35b-multimodal-llm-server-on-kaggle-gpu-accessible-from-any-openai-compatible-client-4m2h) vs [ngrok free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)
- **Cloudflare Quick Tunnel (trycloudflare):** "no uptime guarantee"; "up to 200 in-flight requests. Additional requests return a 429"; "**Quick Tunnels do not support Server-Sent Events (SSE)**"; "The hostname changes each time you create a Quick Tunnel." No account or domain is needed. — [Cloudflare Quick Tunnels docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
- **Cloudflare named (remotely managed) tunnel:** "Before you publish an application through your tunnel, you must add a website to Cloudflare". In other words, you need your own domain on Cloudflare DNS, and `cloudflared` runs with a dashboard-generated token command. — [Cloudflare: create remote tunnel](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/)
- Cloudflare proxy read timeout: "default 125 seconds" (error 524). Only Enterprise can raise it, up to 6,000 s. The docs do not say whether streamed bytes reset it. **The often-quoted "100 s" figure is outdated.** — [Cloudflare error 524](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/)
- In the dev.to Kaggle setup, the quick-tunnel URL was written to `/kaggle/working/server_url.txt` each session (not stable), and no API key was used (`api_key="none"`). — [dev.to](https://dev.to/tahsine/free-35b-multimodal-llm-server-on-kaggle-gpu-accessible-from-any-openai-compatible-client-4m2h)

### Inferences
- **Notebook commands for ngrok** (prior knowledge, verify): `pip install pyngrok`, then `ngrok.set_auth_token(<from Kaggle Secrets>)`, then `ngrok.connect(8000, "http", domain="<your-dev-domain>.ngrok-free.app")`. Or download the ngrok agent and run `ngrok http 8000 --url=https://<dev-domain>`. Keep the authtoken and API key in **Kaggle Secrets**, never in the notebook source, especially if the notebook is public.
- **Budget check:** a RAG answer of about 500 tokens is roughly 3–5 KB of SSE, so 1 GB/month allows well over 100k answers. 20k requests/month is about 650/day. Both are ample for interview demos. The 20k cap counts embed and rerank calls too, so batch them per query, or keep embedding and reranking somewhere the app can reach without ngrok.
- **Streaming:** ngrok HTTP endpoints proxy chunked/SSE responses. Run a 2-minute streaming test in the first session because of the dev.to claim. Vercel's FastAPI function should stream through to the browser, and the Vercel function duration limit on the Hobby plan applies (not researched here).
- **Security:** the gateway enforces `Authorization: Bearer $LLM_KEY` (constant-time compare). Store the same key in a Vercel env var. Optionally add an ngrok traffic-policy rule (15 rules per policy are allowed on free) to reject requests without the header at the edge. Add per-IP rate limiting in the Vercel app, since the public web app is the real abuse surface.
- **Stable-URL alternatives:** (a) a Cloudflare named tunnel with a cheap domain gives a stable hostname, no SSE restriction on named tunnels as far as I know (verify), and a 125 s read timeout. (b) Keep a changing quick-tunnel URL but have the notebook write it to a small KV store such as a Supabase row or Upstash, which the Vercel app reads per request. This does not fix the quick tunnels' lack of SSE. Pinggy and localtunnel were not researched; localtunnel is historically unreliable (prior knowledge).
- HF Inference Endpoints or ZeroGPU Spaces would avoid the Kaggle ToS problem but are out of scope or not wanted. Mention them only as a contingency.

### Gaps
- I did not confirm whether ngrok's free plan breaks long SSE streams in practice (the conflicting claim above).
- No Cloudflare doc confirming SSE behaviour on named tunnels, or whether streaming resets the 125 s timeout.
- I did not research Pinggy free-tier limits or Vercel streaming/duration limits.

## 6. Concrete recommendation (synthesis)

### Takeaway
**Qwen3-8B GGUF Q5_K_M** (fallback Q4_K_M) on **llama.cpp `llama-server`**, built for sm_75 and cached as a Kaggle Dataset, on **GPU0**. **BGE-M3 + bge-reranker-v2-m3 (fp16, sentence-transformers)** go inside a **FastAPI gateway** on **GPU1**, and that gateway also proxies `/v1/chat/completions` (SSE) and enforces a bearer token. Expose port 8000 through the **ngrok free static dev domain**, so the Vercel env var never changes. A/B test **Qwen3.5-9B Q4_K_M** and **Vi-Qwen2-7B-RAG Q5** on the user's Vietnamese eval set. If quality is lacking and VRAM allows, try **Qwen3.6-35B-A3B UD-Q4_K_XL** split over both GPUs. Accept and mitigate the Kaggle ToS risk with short sessions, a private key, an offline fallback and a demo video.

### Cited Findings
- llama.cpp on Kaggle T4x2 is demonstrated end to end (build flags, Dataset caching, ~5–6 min cold start). — [dev.to](https://dev.to/tahsine/free-35b-multimodal-llm-server-on-kaggle-gpu-accessible-from-any-openai-compatible-client-4m2h)
- vLLM's Turing pitfalls: Marlin and compressed-tensors need sm_80, and Gemma 4 fails on SM75. — [vLLM #26297](https://github.com/vllm-project/vllm/issues/26297); [vLLM forum Gemma 4 Turing](https://discuss.vllm.ai/t/title-outofresources-shared-memory-98304-65536-on-turing-sm75-global-attention-layers-with-head-dim-512/2990)
- The ngrok free dev domain is static, has no timeout, and its interstitial does not affect API clients. — [ngrok free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)
- Quick Tunnels have no SSE and a changing hostname. — [Cloudflare docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/)
- Kaggle AUP forbids "server farming" and limits use to personal non-commercial use; there is one reported ban. — [maborak](https://www.maborak.com/blog/kaggle-free-gpu-ai-server); [dev.to comment](https://dev.to/tahsine/free-35b-multimodal-llm-server-on-kaggle-gpu-accessible-from-any-openai-compatible-client-4m2h)

### Inferences
- **Exact IDs** (repo names from prior knowledge unless cited; verify on HF): LLM `Qwen/Qwen3-8B-GGUF` (official) or `unsloth/Qwen3-8B-GGUF` → `Qwen3-8B-Q5_K_M.gguf`. Alternatives: `unsloth/Qwen3.5-9B-GGUF` (cited), `Qwen/Qwen3-8B-AWQ` for the vLLM path, and `AITeamVN/Vi-Qwen2-7B-RAG` (cited; needs a community GGUF or self-conversion). Stretch: `unsloth/Qwen3.6-35B-A3B-GGUF` UD-Q4_K_XL; the article did not state the repo. Embedding: `BAAI/bge-m3`. Reranker: `BAAI/bge-reranker-v2-m3`.
- **Session runbook (about 5–7 min to ready):**
  1. Open the notebook in the browser with Accelerator = GPU T4 x2 and Internet ON.
  2. Read secrets: `NGROK_AUTHTOKEN`, `LLM_KEY`.
  3. Copy the cached llama.cpp binaries and `.so` files from `/kaggle/input`.
  4. Start llama-server on GPU0 in the background and poll `/health` until `status=="ok"`.
  5. Start the uvicorn gateway on GPU1.
  6. Run `ngrok http 8000 --url=<static dev domain>`.
  7. Run a smoke test: one streamed Vietnamese RAG answer with `/no_think`, then one embed and one rerank call.
  8. Stop the session after the demo to save quota and lower the ToS footprint.
- **Expected performance:** about 25–40 tok/s per stream for an 8B Q4/Q5 model on one T4. A 500-token answer takes about 15–20 s, so streaming is mandatory for UX. Time to first token is about 1–3 s for a 4K-token prompt. All of these are estimates. Measure with `llama-bench` in the first session.
- **Known pitfalls checklist:**
  - P100 is unusable, so always select T4 x2 (the CLI cannot).
  - No bf16: use fp16, `--dtype half`.
  - No FA2: llama.cpp `-fa` is fine; in vLLM use the TRITON or FLEX backends.
  - Avoid Marlin, compressed-tensors and MoE-AWQ checkpoints in vLLM.
  - Gemma 4 is broken in vLLM on T4.
  - The libcuda symlink is needed for the llama.cpp build.
  - Copy all `.so` files.
  - Health-check `status=="ok"`.
  - Use Quick Tunnels only without streaming.
  - The idle timeout (20 vs 60 min) is ambiguous, so keep a cell running.
  - Weekly quota is about 30 h, and sessions can be queued at peak.
  - Treat the ToS ban risk as real.

### Gaps
- Every speed number is unmeasured on Kaggle hardware.
- Which model is best at Vietnamese RAG faithfulness (Qwen3-8B vs Qwen3.5-9B vs Vi-Qwen2-7B-RAG vs Qwen3.6-35B-A3B) is unknown without the user's own eval.
- The legality of a demo endpoint under Kaggle's ToS cannot be settled from public sources. Only Kaggle can, and their published wording leans against it.

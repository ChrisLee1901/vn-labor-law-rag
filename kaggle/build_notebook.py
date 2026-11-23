"""Generate kaggle/serve.ipynb. gateway.py is embedded verbatim, so edit it, then run:

python kaggle/build_notebook.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SECRETS = r"""# [1] secrets
import os, subprocess, sys
from kaggle_secrets import UserSecretsClient

_s = UserSecretsClient()
for name in ("NGROK_AUTHTOKEN", "NGROK_DOMAIN", "GATEWAY_API_KEY", "HF_TOKEN"):
    value = _s.get_secret(name)
    if not value:
        raise RuntimeError(f"Kaggle secret {name} is missing (Add-ons > Secrets, attach to this notebook)")
    os.environ[name] = value.strip()
    print(name, "OK")
os.environ["NGROK_DOMAIN"] = os.environ["NGROK_DOMAIN"].removeprefix("https://").rstrip("/")
os.makedirs("/kaggle/working", exist_ok=True)
os.chdir("/kaggle/working")
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pyngrok", "fastapi", "uvicorn", "httpx"], check=True)
"""

LLAMA_BIN = r"""# [2] llama-server binary (dataset llamacpp-sm75-bin, else build from source ~26 min)
import glob, os, shutil, stat, subprocess

DATASET = "/kaggle/input/llamacpp-sm75-bin"
DEST = "/kaggle/working/llama-bin"


def find_server(root):
    hits = glob.glob(f"{root}/**/llama-server", recursive=True)
    return hits[0] if hits else None


if os.path.isdir(DATASET) and find_server(DATASET):
    shutil.copytree(DATASET, DEST, dirs_exist_ok=True, symlinks=True)
else:
    print("WARNING: dataset llamacpp-sm75-bin not attached -> building llama.cpp from source (~26 min).")
    print("Attach the dataset (see docs/runbook-kaggle.md) to skip this.")
    SRC = "/kaggle/working/llama.cpp"
    if not os.path.isdir(SRC):
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/ggml-org/llama.cpp", SRC], check=True)
    # libcuda stub: lets the linker resolve -lcuda on a machine without the driver library at build time.
    # Kept in its own dir and used for the build only, never at runtime (the real driver must win there).
    stub_dir = "/kaggle/working/cuda-stub"
    os.makedirs(stub_dir, exist_ok=True)
    stub = "/usr/local/cuda/lib64/stubs/libcuda.so"
    for n in ("libcuda.so", "libcuda.so.1"):
        if not os.path.lexists(f"{stub_dir}/{n}"):
            os.symlink(stub, f"{stub_dir}/{n}")
    env = dict(os.environ, LIBRARY_PATH=stub_dir, LD_LIBRARY_PATH=stub_dir + ":" + os.environ.get("LD_LIBRARY_PATH", ""))
    subprocess.run(["cmake", "-B", "build", "-DGGML_CUDA=ON", "-DCMAKE_CUDA_ARCHITECTURES=75", "-DLLAMA_CURL=OFF"],
                   cwd=SRC, env=env, check=True)
    subprocess.run(["cmake", "--build", "build", "--target", "llama-server", "-j", str(os.cpu_count())],
                   cwd=SRC, env=env, check=True)
    shutil.copytree(f"{SRC}/build", DEST, dirs_exist_ok=True, symlinks=True)

LLAMA_SERVER = find_server(DEST)
assert LLAMA_SERVER, "llama-server not found after copy/build"
for root, _, files in os.walk(DEST):
    for f in files:
        p = os.path.join(root, f)
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
lib_dirs = sorted({os.path.dirname(p) for p in glob.glob(f"{DEST}/**/*.so*", recursive=True)} | {os.path.dirname(LLAMA_SERVER)})
os.environ["LD_LIBRARY_PATH"] = ":".join(lib_dirs + [os.environ.get("LD_LIBRARY_PATH", "")])
print("llama-server:", LLAMA_SERVER)
"""

LLAMA_RUN = r"""# [3] llama-server on GPU 0 (Qwen3-8B Q5_K_M, thinking off)
import glob, json, os, subprocess
from huggingface_hub import hf_hub_download

ggufs = sorted(glob.glob("/kaggle/input/qwen3-8b-gguf/**/*.gguf", recursive=True), key=lambda p: "Q5_K_M" not in p)
if ggufs:
    GGUF = ggufs[0]
else:
    print("dataset qwen3-8b-gguf not attached -> downloading from Hugging Face")
    GGUF = hf_hub_download("Qwen/Qwen3-8B-GGUF", "Qwen3-8B-Q5_K_M.gguf", local_dir="/kaggle/working/models",
                           token=os.environ["HF_TOKEN"])
os.environ["LLM_MODEL"] = os.path.basename(GGUF)
print("GGUF:", GGUF)

cmd = [
    LLAMA_SERVER, "-m", GGUF, "-ngl", "99", "-c", "16384", "-np", "2",
    "--jinja", "--reasoning-budget", "0",
    "--chat-template-kwargs", json.dumps({"enable_thinking": False}),
    "--host", "127.0.0.1", "--port", "8080",
]
llama_log = open("/kaggle/working/llama.log", "wb")
llama_proc = subprocess.Popen(cmd, stdout=llama_log, stderr=subprocess.STDOUT,
                              env=dict(os.environ, CUDA_VISIBLE_DEVICES="0"))
print("llama-server pid", llama_proc.pid, "- log: /kaggle/working/llama.log")
"""

GATEWAY_START = r"""# [5] gateway on :8000 (background thread; loads embedder + reranker fp16 on cuda:1)
import os, sys, threading, traceback
import uvicorn

sys.path.insert(0, os.getcwd())
import gateway

gateway_err = []


def _serve():
    try:
        embedder, reranker = gateway.load_models("cuda:1")
        app = gateway.create_app(embedder, reranker, "http://127.0.0.1:8080",
                                 os.environ["GATEWAY_API_KEY"], os.environ["LLM_MODEL"])
        uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")).run()
    except BaseException:
        gateway_err.append(traceback.format_exc())
        print(gateway_err[-1])


threading.Thread(target=_serve, daemon=True).start()
print("gateway thread started (models load while llama-server loads)")
"""

WAIT = r"""# [6] wait until gateway /health says ok (llm + embedder + reranker), max 15 min
import json, time, urllib.request

H = "http://127.0.0.1:8000/health"


def health():
    try:
        with urllib.request.urlopen(H, timeout=3) as r:
            return json.load(r)
    except Exception:
        return None


t0 = time.time()
while True:
    h = health()
    print(f"[{int(time.time() - t0):4d}s]", h or "gateway not up yet (loading models)")
    if h and h.get("status") == "ok":
        break
    if llama_proc.poll() is not None:
        print(open("/kaggle/working/llama.log", errors="replace").read()[-3000:])
        raise RuntimeError(f"llama-server exited with code {llama_proc.returncode}")
    if gateway_err:
        raise RuntimeError("gateway thread crashed, see traceback above")
    if time.time() - t0 > 900:
        print(open("/kaggle/working/llama.log", errors="replace").read()[-3000:])
        raise TimeoutError("not ready after 15 min")
    time.sleep(10)
print("local stack ready in", int(time.time() - t0), "s")
"""

NGROK = r"""# [7] public tunnel (static ngrok domain -> :8000)
import os, re
from pyngrok import ngrok

try:
    ngrok.set_auth_token(os.environ["NGROK_AUTHTOKEN"])
    ngrok.connect(8000, "http", domain=os.environ["NGROK_DOMAIN"])
except Exception as e:
    # pyngrok puts the authtoken in its exception text: report only the type and the ERR_NGROK code
    code = re.search(r"ERR_NGROK_\d+", str(e).replace(os.environ["NGROK_AUTHTOKEN"], "***"))
    raise RuntimeError(f"ngrok setup failed: {type(e).__name__} {code.group() if code else ''}") from None
PUBLIC_URL = "https://" + os.environ["NGROK_DOMAIN"]
"""

SMOKE = r"""# [8] smoke test through the gateway, then READY
import json, os, urllib.request

BASE = "http://127.0.0.1:8000"
AUTH = {"Authorization": "Bearer " + os.environ["GATEWAY_API_KEY"], "Content-Type": "application/json"}


def post(path, body):
    req = urllib.request.Request(BASE + path, json.dumps(body).encode(), AUTH)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


emb = post("/v1/embeddings", {"input": ["Thời gian thử việc tối đa là bao lâu?"]})
print("embeddings: dim =", len(emb["data"][0]["embedding"]))
rr = post("/v1/rerank", {"query": "thử việc tối đa bao lâu",
                         "documents": ["Thời gian thử việc không quá 60 ngày đối với công việc cần trình độ cao đẳng.",
                                       "Cách nấu phở bò truyền thống."]})
print("rerank:", rr["results"])
chat = post("/v1/chat/completions", {"model": os.environ["LLM_MODEL"], "max_tokens": 64, "temperature": 0,
                                     "messages": [{"role": "user", "content": "Xin chào! Trả lời một câu ngắn bằng tiếng Việt."}]})
msg = chat["choices"][0]["message"]["content"]
print("chat:", msg)
if "<think>" in msg:
    print("WARNING: thinking is NOT disabled; check llama-server flags")
print("READY", PUBLIC_URL)
"""

KEEPALIVE = r"""# [9] keep-alive: log /health every 60 s.
# STOP THE SESSION after the interview (Kaggle > Session options > Stop session). Do not leave it running (Kaggle ToS).
import json, time, urllib.request

while True:
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as r:
            print(time.strftime("%H:%M:%S"), json.load(r))
    except Exception as e:
        print(time.strftime("%H:%M:%S"), "health failed:", e)
    time.sleep(60)
"""


def _cell(src: str, kind: str = "code") -> dict:
    cell = {"cell_type": kind, "metadata": {}, "source": src.splitlines(keepends=True)}
    if kind == "code":
        cell.update(execution_count=None, outputs=[])
    return cell


def build() -> dict:
    # repo is eol=lf; normalise so the notebook is identical on Windows and Linux checkouts
    gateway = (HERE / "gateway.py").read_bytes().decode("utf-8").replace("\r\n", "\n")
    sources = [
        SECRETS,
        LLAMA_BIN,
        LLAMA_RUN,
        "%%writefile gateway.py\n" + gateway,
        GATEWAY_START,
        WAIT,
        NGROK,
        SMOKE,
        KEEPALIVE,
    ]
    return {
        "cells": [_cell(s) for s in sources],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }


if __name__ == "__main__":
    out = HERE / "serve.ipynb"
    out.write_text(
        json.dumps(build(), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("wrote", out)

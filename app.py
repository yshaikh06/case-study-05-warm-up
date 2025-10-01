import os, json, subprocess, shlex, pathlib
from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

# ----- TinyLlama via Ollama settings (Stage 2) -----
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "tinyllama")

@app.get("/")
def home():
    return render_template("index.html")

# Stage 1: echo
@app.post("/api/echo")
def echo():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    return jsonify({"reply": (text + "?") if text else "?"}), 200

# Stage 2: proxy to Ollama
@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("text") or "").strip()
    if not prompt:
        return jsonify({"reply": "(empty prompt)"}), 200

    system_prefix = "You are UVA SDS GPT. Answer concisely.\n"
    full_prompt = system_prefix + prompt

    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": full_prompt},
            timeout=60,
        )
        # Try single JSON first
        try:
            js = r.json()
            text = js.get("response") or ""
        except ValueError:
            text = ""
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    piece = json.loads(line).get("response","")
                    text += piece
                except Exception:
                    pass
        return jsonify({"reply": (text.strip() or "(no response)")}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 502

# ----- Stage 3: smolagents safe shell tool -----
try:
    from smolagents import Tool, CodeAgent, LiteLLMModel
except Exception:
    Tool = None
    CodeAgent = None
    LiteLLMModel = None

SANDBOX_DIR = pathlib.Path(__file__).parent / "sandbox"
SAFE_CMDS = {"pwd", "ls", "cat", "head", "tail", "echo"}

def _in_sandbox(path: str) -> pathlib.Path:
    p = (SANDBOX_DIR / path).resolve()
    if not str(p).startswith(str(SANDBOX_DIR.resolve())):
        raise ValueError("Path escapes sandbox")
    return p

def _secure_parse(cmd: str):
    banned = ["|", "&&", "||", ";", "`", "$(", ">", "<"]
    if any(b in cmd for b in banned):
        raise ValueError("Pipes/redirects/chaining not allowed")
    parts = shlex.split(cmd)
    if not parts:
        raise ValueError("Empty command")
    if parts[0] not in SAFE_CMDS:
        raise ValueError(f"Command '{parts[0]}' not allowed")
    mapped = []
    for i, tok in enumerate(parts):
        if parts[0] == "echo" and i > 0:
            mapped.append(tok); continue
        if tok.startswith("-"):
            mapped.append(tok); continue
        if any(ch in tok for ch in ("/","\\")):
            mapped.append(str(_in_sandbox(tok)))
        else:
            mapped.append(tok)
    return mapped

if Tool is not None:
    class SafeShellTool(Tool):
        name = "safe_shell"
        description = ("Run a small set of read-only shell commands inside a sandbox folder. "
                       "Allowed: pwd, ls, cat, head, tail, echo. Relative paths only.")
        inputs = {"cmd": {"type": "string", "description": "Shell command"}}
        output_type = "string"

        def __call__(self, cmd: str) -> str:
            try:
                parts = _secure_parse(cmd)
                proc = subprocess.run(
                    parts, cwd=SANDBOX_DIR, capture_output=True, text=True, timeout=3
                )
                out = (proc.stdout or "") + (proc.stderr or "")
                if len(out) > 8000:
                    out = out[:8000] + "\n... [truncated]"
                return out.strip() or "(no output)"
            except Exception as e:
                return f"error: {e}"

    def _build_agent():
        model_id = os.getenv("SMOL_MODEL_ID", f"ollama_chat/{OLLAMA_MODEL}")
        base_url = os.getenv("SMOL_BASE_URL", OLLAMA_URL)
        try:
            model = LiteLLMModel(model_id=model_id, api_base=base_url, api_key="none")
        except Exception:
            model = LiteLLMModel(model_id=model_id)
        tools = [SafeShellTool()]
        return CodeAgent(tools=tools, model=model, add_base_tools=False)
else:
    def _build_agent():
        return None

_AGENT = None

@app.post("/api/agent")
def agent_endpoint():
    global _AGENT
    if _AGENT is None:
        _AGENT = _build_agent()
        if _AGENT is None:
            return jsonify({"error": "smolagents not installed"}), 500
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"reply": "(empty prompt)"}), 200
    try:
        result = _AGENT.run(text)
        return jsonify({"reply": str(result)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)

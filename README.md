# UVA SDS GPT (Warm-Up + Case Study + Tools)

Black-themed GPT-like UI with Flask backend.
- Stage 1: `/api/echo` appends `?`
- Stage 2: `/api/chat` proxies to TinyLlama via Ollama
- Stage 3: `/api/agent` uses **smolagents** with a **safe shell tool** (whitelisted)

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py   # http://127.0.0.1:5000
```

## Deploy to Azure App Service
```bash
REGION="eastus"
RG_APP="uva-sds-gpt-rg"
APP_NAME="uva-sds-gpt-$RANDOM"

az group create --name "$RG_APP" --location "$REGION"
az webapp up --runtime "PYTHON:3.11" --resource-group "$RG_APP" --location "$REGION" --name "$APP_NAME"
az webapp config set -g "$RG_APP" -n "$APP_NAME" --startup-file "gunicorn app:app --bind=0.0.0.0:\$PORT"
echo "https://$APP_NAME.azurewebsites.net"
```

## TinyLlama on an Azure VM (Ollama)
Provision VM, open port 11434, install Ollama, `ollama pull tinyllama`. Set App Settings:
```bash
az webapp config appsettings set   --name "$APP_NAME" --resource-group "$RG_APP"   --settings OLLAMA_URL="http://$VM_PUBLIC_IP:11434" OLLAMA_MODEL="tinyllama"
az webapp restart -g "$RG_APP" -n "$APP_NAME"
```

## Agent Tools (smolagents)
- Requirements include: `smolagents`, `litellm`
- Environment (defaults shown):
  - `SMOL_MODEL_ID=ollama_chat/tinyllama`
  - `SMOL_BASE_URL=$OLLAMA_URL`  (e.g., `http://<vm-ip>:11434`)

### Safe Shell Tool
- **Allowed commands:** `pwd`, `ls`, `cat`, `head`, `tail`, `echo`
- **Sandbox:** `./sandbox` only; relative paths enforced
- **Safety:** No pipes/redirects/chaining, 3s timeout, 8KB output cap
- **Demo:** Switch UI to **Agent (Tools)** and try:
  - `pwd`
  - `ls`
  - `cat README.txt`

> ⚠️ For class use only. Add auth/rate limits if exposing on the public internet.


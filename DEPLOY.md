# Deploying Intelli-Credit (hosted, no VPN)

The app is a single Streamlit process, so **Streamlit Community Cloud** is the
fastest way to a public URL. It's free and installs the system Tesseract binary
for you via `packages.txt`.

## One-time deploy

1. Push this repo to GitHub (already done: `Nooronclouds/intelli_credit`).
2. Go to <https://share.streamlit.io> and sign in with GitHub.
3. **New app** → select:
   - **Repository:** `Nooronclouds/intelli_credit`
   - **Branch:** `master`
   - **Main file path:** `ui/app.py`
4. Open **Advanced settings → Secrets** and paste:
   ```toml
   GEMINI_API_KEY = "your_gemini_api_key_here"
   ```
5. **Deploy.** First build takes a few minutes (it compiles the ML deps).

That's it — you get a permanent `https://<app>.streamlit.app` URL, reachable
without a VPN.

### What's already wired for you
- `packages.txt` → installs `tesseract-ocr` on the server (OCR fallback works).
- `.streamlit/config.toml` → theme + 50 MB upload limit.
- `ui/app.py` → reads the key from `st.secrets` on Cloud, and from `.env` locally.

## Run locally
```bash
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # add your GEMINI_API_KEY
streamlit run ui/app.py
```

## Heads-up: dependency weight
`sentence-transformers` pulls in **PyTorch**, which is large. On Streamlit
Community Cloud's ~1 GB memory tier this builds and runs, but it's the heaviest
part of the app and the most likely thing to slow the first boot.

If you ever hit memory/build limits, the clean fix is to drop the local
embedding model and use **Gemini's embedding API** for RAG instead — that
removes `torch` + `faiss-cpu` entirely. It's a contained change in
`agents/ingestor.py` (`build_rag_index` / `query_rag`) and a good future
optimization, not required for the current deploy.

# Initial agents Setup Guide


---

## Step 1 — Clone the Repo
```bash
git clone <repo-url>
cd projectfiles
```

---

## Step 2 — Create Virtual Environment
```bash
py -3.11 -m venv venv
venv\Scripts\activate
```

---

## Step 3 — Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Step 4 — Install and Start Ollama
Agent 1 requires Ollama running locally with llama3.1:8b.

1. Download Ollama from https://ollama.com
2. Open a terminal and run:
```bash
ollama pull llama3.1:8b
ollama serve
```
Keep this terminal open. Ollama must be running before the pipeline starts.

---

## Step 5 — Install Tesseract OCR
Agent 1 uses Tesseract as OCR fallback for scanned PDFs.

1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default path: `C:\Program Files\Tesseract-OCR\`
3. Add to system PATH during installation (check the box)


## Demo Checklist
- [ ] Ollama running in background (`ollama serve`)
- [ ] Run pipeline once before demo to warm up FAISS cache
- [ ] Test with `data/sample_annual_report.pdf` first
- [ ] Keep `outputs/cam.docx` closed during runs
- [ ] Internet connection for Agent 2 web search
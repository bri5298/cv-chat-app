# CV Chat App

A small RAG-style chat app that answers questions about CV content stored in a JSON knowledge base.

The app uses:

- React, TypeScript, and Vite for the frontend
- FastAPI for the Python backend
- Groq for chat model responses
- Vercel for deployment

## Project Structure

```text
cv-chat-app/
  api/
    index.py
  backend/
    __init__.py
    requirements.txt
    app/
      __init__.py
      main.py
      models.py
      rag_chat.py
      data/
        knowledge.json
  frontend/
    src/
      App.tsx
      App.css
      api.ts
      index.css
      main.tsx
      types.ts
  .vscode/
    launch.json
  vercel.json
```

## Environment Variables

Create a local `.env` file at the repo root:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
```

Do not commit `.env`.

For Vercel, add the same variables in the Vercel project settings:

```text
GROQ_API_KEY
```

## Install Dependencies

### Backend

From the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
cd backend
pip install -r requirements.txt
```

### Frontend

From the repo root:

```powershell
cd frontend
npm install
```

## Run Locally

Use two terminals.

### Terminal 1: Backend

From the repo root:

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn app.main:app --reload --host localhost --port 8000
```

The backend runs at:

```text
http://localhost:8000
```

Health check:

```text
http://localhost:8000/health
```

### Terminal 2: Frontend

From the repo root:

```powershell
cd frontend
npm run dev
```

The frontend runs at:

```text
http://localhost:5173
```

In local development, the frontend calls:

```text
http://localhost:8000/chat
```

In production, it calls:

```text
/api/chat
```

## Run With VS Code Debugger

This repo includes `.vscode/launch.json` with three launch options:

- `Backend: FastAPI`
- `Frontend: Vite`
- `App: Backend + Frontend`

To run the full app in debug mode:

1. Open the repo root in VS Code.
2. Make sure `.env` exists at the repo root with `GROQ_API_KEY`.
3. Make sure backend dependencies are installed in `.venv`.
4. Make sure you have run npm install from the frontend folder.
5. Open the Run and Debug panel.
6. Select `App: Backend + Frontend`.
7. Press Start Debugging.

The compound launch starts:

- FastAPI with Uvicorn from `backend/`
- Vite from `frontend/`

Then open:

```text
http://localhost:5173
```

## Knowledge Base

The CV knowledge base is stored at:

```text
backend/app/data/knowledge.json
```

Each record should include fields like:

```json
{
  "id": "technical-skills",
  "title": "Technical Skills",
  "category": "skills",
  "content": "CV content goes here.",
  "tags": ["python", "typescript", "fastapi"]
}
```

The backend searches this JSON file, sends the relevant records to Groq, and returns an answer with source titles.

### Generate the Knowledge Base

The knowledge base is generated from the source CV `.docx` file by running:

```powershell
.\.venv\Scripts\Activate.ps1
python backend/scripts/generate_knowledge.py
```

By default, the script reads:

```text
backend/app/data/Brielle Johnston CV EN.docx
```

It then:

- extracts the CV text from the `.docx` file
- splits the CV into structured knowledge records for the RAG backend
- writes the generated JSON to `backend/app/data/knowledge.json`
- writes a browsable HTML version to `frontend/public/cv.html`
- converts the source CV to `frontend/public/cv.pdf`

The PDF conversion requires LibreOffice. The script looks for `soffice` or `libreoffice` on your `PATH`, or a default LibreOffice installation path on Windows or macOS.

You can override the input and output paths if needed:

```powershell
python backend/scripts/generate_knowledge.py `
  --cv "path/to/cv.docx" `
  --output backend/app/data/knowledge.json `
  --html-output frontend/public/cv.html `
  --pdf-output frontend/public/cv.pdf
```

## Deployment Notes

The Vercel API entry point is:

```text
api/index.py
```

It imports the FastAPI app from:

```text
backend/app/main.py
```

The Vercel config is:

```text
vercel.json
```

Vercel builds the frontend from `frontend/` and routes `/api/*` requests to the FastAPI backend.

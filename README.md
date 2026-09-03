# QuizGen AI Backend

FastAPI backend for Supabase authentication/history, local Qdrant + FastEmbed retrieval,
and Groq-based grounded question generation and short-answer evaluation.

## One-time setup

1. Activate the environment and install packages:

   ```cmd
   venv\Scripts\activate
   python -m pip install -r requirements.txt
   ```

2. In Supabase, open **SQL Editor**, paste the contents of
   `supabase/migrations/001_quizgen_schema.sql`, and click **Run**.

3. Confirm `.env` contains valid Supabase publishable/secret keys and a Groq key.
   Never expose the Supabase secret key or Groq key in frontend code.

4. Start the API:

   ```cmd
   python -m uvicorn app.main:app --reload
   ```

5. Open `http://127.0.0.1:8000/docs` or run the frontend with VS Code Live Server
   on `http://127.0.0.1:5500` / `http://localhost:5500`.

## Notes

- Text-based PDF and PPTX files are supported. Scanned PDF pages use local
  Tesseract OCR when `OCR_ENABLED=true`.
- Text-form equations are preserved when the document extractor can read them.
- The first material upload downloads the configured FastEmbed model and may be slower.
- Qdrant data is stored locally in `data/qdrant` and is ignored by Git.

## Scanned PDF OCR

Install Tesseract OCR on the API machine, then configure `.env`:

```env
OCR_ENABLED=true
OCR_LANGUAGE=eng
OCR_DPI=300
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

OCR runs only for PDF pages without enough embedded text. For Bangla and English,
install both Tesseract language data files and use `OCR_LANGUAGE=eng+ben`.

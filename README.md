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

- Only text-based PDF and PPTX are supported. Image-only/scanned documents need OCR.
- Text-form equations are preserved when the document extractor can read them.
- The first material upload downloads the configured FastEmbed model and may be slower.
- Qdrant data is stored locally in `data/qdrant` and is ignored by Git.

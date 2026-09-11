import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.services import answer_evaluation as grading
from app.services import question_generation as generation
from app.api.v1.endpoints import materials


def candidate(kind="short", text="Explain energy transfer"):
    return {"type": kind, "question": text, "correct_answer": "Energy moves",
            "explanation": "From the source", "source_id": "S1",
            "options": ["Energy moves", "B", "C", "D"] if kind == "mcq" else None}


class WorkflowTests(unittest.TestCase):
    def test_exact_counts_and_final_retry(self):
        context = [{"source": "Page 1", "text": "Energy moves between systems"}]
        # The fourth (last) attempt completes the request; it must be returned.
        with patch.object(generation, "_request_candidates", side_effect=[[], [], [], [candidate()]]), patch.object(
            generation, "filter_duplicates", side_effect=lambda candidates, previous, needed: candidates[:needed]
        ):
            result = generation.generate_questions(context, 0, 1, [])
        self.assertEqual([q["type"] for q in result], ["short"])

    def test_mixed_counts_and_excess_candidates(self):
        context = [{"source": "Page 1", "text": "Energy moves between systems"}]
        with patch.object(generation, "_request_candidates", return_value=[candidate("mcq"), candidate(), candidate()]), patch.object(
            generation, "filter_duplicates", side_effect=lambda candidates, previous, needed: candidates[:needed]
        ):
            result = generation.generate_questions(context, 1, 1, [])
        self.assertEqual([q["type"] for q in result], ["mcq", "short"])

    def test_insufficient_questions_fail(self):
        with patch.object(generation, "_request_candidates", return_value=[]), patch.object(
            generation, "filter_duplicates", return_value=[]
        ):
            with self.assertRaises(HTTPException):
                generation.generate_questions([{"source": "Page 1", "text": "Text"}], 1, 0, [])

    def test_invalid_citation_rejected(self):
        self.assertIsNone(generation._prepare_candidate(candidate(), {}, {"source": "Page 1", "text": "Text"}))

    def test_reupload_skips_extraction_and_embedding(self):
        existing = {"id": "m", "filename": "notes.pdf", "page_count": 2, "chunk_count": 3}
        with patch.object(materials, "find_material", return_value=existing), patch.object(
            materials, "has_material_index", return_value=True
        ), patch.object(materials, "extract_document") as extract, patch.object(materials, "index_chunks") as index:
            result = materials._process_material(b"same", ".pdf", "notes.pdf", "application/pdf", "user")
        self.assertTrue(result["reused"])
        extract.assert_not_called()
        index.assert_not_called()

    def test_reupload_repairs_missing_index(self):
        existing = {"id": "m", "filename": "notes.pdf", "page_count": 2, "chunk_count": 3}
        with patch.object(materials, "find_material", return_value=existing), patch.object(
            materials, "has_material_index", return_value=False
        ), patch.object(materials, "extract_document", return_value=["section"]), patch.object(
            materials, "chunk_sections", return_value=[{"text": "chunk"}]
        ), patch.object(materials, "index_chunks") as index:
            result = materials._process_material(b"same", ".pdf", "notes.pdf", "application/pdf", "user")
        self.assertEqual(result["id"], "m")
        index.assert_called_once_with("user", "m", [{"text": "chunk"}])

    def test_previous_questions_are_passed_to_generation_and_filter(self):
        context = [{"source": "Page 1", "text": "Energy moves between systems"}]
        with patch.object(generation, "_request_candidates", return_value=[candidate()]) as request, patch.object(
            generation, "filter_duplicates", side_effect=lambda candidates, previous, needed: candidates[:needed]
        ) as dedup:
            generation.generate_questions(context, 0, 1, ["A previously used question"])
        self.assertIn("A previously used question", request.call_args.args[0][1]["content"])
        self.assertIn("A previously used question", dedup.call_args.args[1])

    def question(self):
        return {**candidate(), "id": "q", "source_text": "Energy moves", "source": "Page 1"}

    def test_nonanswers_get_zero_without_ai_or_embeddings(self):
        for answer in ["", "don't know", "I don’t know.", "idk", "no idea"]:
            with self.subTest(answer=answer), patch.object(grading, "_evaluate_short_batch") as ai, patch.object(grading, "_semantic_score") as semantic:
                result = grading.evaluate_answers([self.question()], {"q": answer})[0]
                self.assertEqual(result["awarded_marks"], 0)
                ai.assert_not_called()
                semantic.assert_not_called()

    def test_factual_credit_controls_marks(self):
        for factual in [0, 0.25, 0.5, 0.75, 1]:
            with self.subTest(factual=factual), patch.object(grading, "_evaluate_short_batch", return_value=[
                {"question_id": "q", "factual_score": factual, "feedback": "Rubric"}
            ]), patch.object(grading, "_semantic_score", return_value=0.99):
                result = grading.evaluate_answers([self.question()], {"q": "Some response"})[0]
                self.assertEqual(result["awarded_marks"], factual)
                self.assertEqual(result["correct"], factual == 1)

    def test_unavailable_grading_does_not_invent_marks(self):
        with patch.object(grading, "_evaluate_short_batch", return_value=[]):
            with self.assertRaises(HTTPException) as raised:
                grading.evaluate_answers([self.question()], {"q": "Some response"})
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()

from pydantic import BaseModel


class SubmittedAnswer(BaseModel):
    question_id: str
    answer: str = ""


class SubmitAttemptRequest(BaseModel):
    answers: list[SubmittedAnswer]
    auto_submitted: bool = False

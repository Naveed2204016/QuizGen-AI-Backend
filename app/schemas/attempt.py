from pydantic import BaseModel, Field, model_validator


class SubmittedAnswer(BaseModel):
    question_id: str
    answer: str = Field(default="", max_length=10_000)


class SubmitAttemptRequest(BaseModel):
    answers: list[SubmittedAnswer] = Field(max_length=50)
    auto_submitted: bool = False

    @model_validator(mode="after")
    def question_ids_are_unique(self):
        question_ids = [item.question_id for item in self.answers]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("Each question may be submitted only once")
        return self

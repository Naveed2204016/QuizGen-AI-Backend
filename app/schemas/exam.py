from pydantic import BaseModel, Field, model_validator


class GenerateExamRequest(BaseModel):
    material_id: str
    mcq_count: int = Field(ge=0, le=50)
    short_count: int = Field(ge=0, le=20)
    duration_minutes: int = Field(ge=1, le=180)

    @model_validator(mode="after")
    def validate_total(self):
        if self.mcq_count + self.short_count < 1:
            raise ValueError("At least one question is required")
        if self.mcq_count + self.short_count > 50:
            raise ValueError("At most 50 questions are allowed")
        return self

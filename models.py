"""Pydantic models shared by the web API and OpenAI structured outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class InteractionClassification(BaseModel):
    """Structured pedagogical description of one student message.

    The labels are intentionally broad. They should remain stable across
    different subject tutors so that classroom-level analytics are comparable.
    Subject-specific meaning is carried mainly by ``topic`` and ``subtopic``.
    """

    intent: Literal[
        "question",
        "debugging",
        "concept_explanation",
        "code_request",
        "verification",
        "other",
    ]
    topic: str = Field(description="Short subject topic, e.g. PWM or op_amp")
    subtopic: str = Field(description="More specific topic or 'general'")
    problem_type: Literal[
        "conceptual",
        "syntax",
        "hardware",
        "algorithmic",
        "measurement",
        "organizational",
        "other",
    ]
    student_state: Literal["confident", "uncertain", "stuck", "exploring"]
    possible_misconception: str | None = Field(
        default=None,
        description=(
            "Only a clearly evidenced false belief or reasoning error explicitly "
            "supported by the current student message. Use null when uncertain, "
            "when the statement may be valid, or when a false assumption would "
            "have to be inferred."
        ),
    )
    teacher_attention: bool = False
    teacher_attention_reason: str | None = None
    response_strategy: Literal[
        "diagnostic_question",
        "hint",
        "explanation",
        "example",
        "code_fragment",
        "check_understanding",
    ]
    understanding_signal: Literal["positive", "neutral", "negative"] = "neutral"
    communication_style: Literal[
        "appropriate", "frustrated", "rude", "suspicious"
    ] = "appropriate"


class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=8000)


class ChatResponse(BaseModel):
    answer: str
    classification: InteractionClassification
    moderation_flagged: bool = False

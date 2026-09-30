"""All OpenAI API interaction lives in this module.

Keeping the API boundary in one file makes later model changes, cost tuning,
or replacement of the hosted retrieval layer much easier.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from openai import OpenAI

from config import (
    CLASSIFIER_MODEL,
    MODERATION_MODEL,
    OPENAI_API_KEY,
    TUTOR_MODEL,
)
from models import InteractionClassification


def _client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY ni nastavljen. Kopiraj .env.example v .env.")
    return OpenAI(api_key=OPENAI_API_KEY)


def moderate_text(text: str) -> bool:
    """Run OpenAI's moderation model before the pedagogical pipeline."""
    client = _client()
    result = client.moderations.create(model=MODERATION_MODEL, input=text)
    return bool(result.results[0].flagged)


def classify_message(
    *,
    tutor_name: str,
    message: str,
    recent_history: list[dict[str, str]],
    allowed_topics: list[dict[str, str]],
) -> InteractionClassification:
    """Classify one student message into stable pedagogical metadata.

    Structured Outputs with a Pydantic model means the rest of the application
    receives validated fields rather than trying to parse free-form JSON text.
    """
    client = _client()

    topic_text = json.dumps(allowed_topics, ensure_ascii=False) if allowed_topics else "[]"

    classifier_instructions = f"""
You classify student interactions for a classroom AI tutor called {tutor_name}.
The output is used for formative classroom awareness, not for grading.
Use short, stable labels for topic/subtopic. Infer conservatively.
teacher_attention should be true only when a teacher may reasonably need to
intervene: repeated severe frustration, potentially unsafe activity, clearly
inappropriate communication, or a learning blockage visible from context.
Choose a response_strategy that represents the smallest useful pedagogical
support likely to help the learner progress.

Understanding evidence must also be HIGH-PRECISION and conservative.
`understanding_signal` describes what the CURRENT student message demonstrates
about the learner's understanding of the classified topic. It is NOT a measure
of how difficult the question is and NOT a measure of how much help is requested.

Set `understanding_signal` to `positive` only when the current message itself
provides clear evidence of correct understanding, for example when the learner:
- correctly explains a concept or causal relationship;
- gives technically correct reasoning or a justified prediction;
- correctly applies a concept to a new case;
- explicitly corrects an earlier misconception and now demonstrates the
  corrected understanding.

Set `understanding_signal` to `negative` only when the current message itself
provides clear evidence of incorrect understanding, for example when the learner:
- explicitly states a technically or conceptually false claim as true;
- gives a clearly incorrect causal explanation or reasoning step;
- clearly applies the relevant concept incorrectly.

Set `understanding_signal` to `neutral` in all other cases, especially when the
learner merely:
- asks a question or asks for an explanation;
- asks for help or says that something does not work;
- pastes code, an error message, sensor values, or other evidence without
  clearly explaining their own conceptual reasoning;
- expresses uncertainty or explores alternatives;
- provides too little information to infer understanding reliably.

Prefer `neutral` whenever there is reasonable doubt. A difficult question is
not evidence of poor understanding, and asking for help must never by itself
produce a negative signal.

Examples:
- "How does PWM work?" -> neutral.
- "My motor does not work; what is wrong?" -> neutral.
- "PWM changes the HIGH voltage from 0 V to 5 V depending on the value."
  -> negative (if the learner endorses this as the explanation).
- "PWM keeps digital HIGH/LOW levels and changes duty cycle." -> positive.

Misconception detection must be HIGH-PRECISION and conservative.
Set `possible_misconception` only when the CURRENT student message contains
clear, direct evidence of a technically or conceptually false belief, false
causal explanation, or reasoning step that the student appears to endorse.
The wording should describe the incorrect idea briefly and neutrally.

Set `possible_misconception` to null when:
- the statement is technically valid, even if it is incomplete or unusual;
- the student is merely asking a question, exploring an alternative, or
  expressing uncertainty without endorsing a false claim;
- a misconception is only one of several possible interpretations;
- you would need to infer an unstated assumption or "read between the lines";
- previous turns contained a misconception but the current message corrects,
  rejects, or demonstrates better understanding of it.

Prefer false negatives over false positives: if there is reasonable doubt,
return null. Do not invent a misconception merely because the learner has a
problem or uses a different implementation.

Example: "Motorja sploh ne krmilim s PWM-jem; uporabljam le kombinacijo
`digitalWrite()`." is NOT by itself evidence of a misconception. It can be a
valid statement that the motor is being controlled only in discrete states.
Do not label it as believing that PWM is required, nor as believing that
`digitalWrite()` necessarily guarantees correct motor control, unless the
student explicitly states such a false claim.

Topic classification rules:
- `topic` answers only: "What subject matter is the student talking about?"
- Do NOT use interaction-purpose or problem-type labels as topics. In particular,
  labels such as `debugging`, `question`, `verification`, `syntax`, `conceptual`,
  `hardware`, or `algorithmic` belong in `intent` / `problem_type`, not `topic`.
- Prefer one of the tutor's predefined topics below and use exactly its `id`.
- Choose the closest content topic even when the student is debugging that topic.
  Example: "Why does my distance sensor code not work?" -> topic=`distance_sensor`,
  intent=`debugging`; never topic=`debugging`.
- Use a new short snake_case topic only when the message clearly concerns a
  meaningful content area not covered by the taxonomy. Do not create a new label
  merely because the wording is unusual.

Preferred topic taxonomy:
{topic_text}
""".strip()

    # A few previous turns improve classification of messages such as "še vedno
    # ne dela" without sending the entire lesson history to the classifier.
    input_messages: list[dict[str, str]] = [
        {"role": "system", "content": classifier_instructions},
        *recent_history[-4:],
        {"role": "user", "content": message},
    ]

    response = client.responses.parse(
        model=CLASSIFIER_MODEL,
        input=input_messages,
        text_format=InteractionClassification,
    )

    if response.output_parsed is None:
        raise RuntimeError("Klasifikator ni vrnil strukturiranega rezultata.")
    return response.output_parsed



class LearningEvidence(BaseModel):
    """History-aware formative evidence extracted from one learner message."""

    evidence_type: Literal[
        "explicit_positive",
        "explicit_negative",
        "repeated_question",
        "advanced_question",
        "knowledge_transfer",
        "check_answer_positive",
        "check_answer_negative",
        "progressive_followup",
        "independent_debugging",
        "solution_seeking_without_attempt",
        "neutral",
    ] = "neutral"
    understanding_value: float | None = Field(default=None, ge=0.0, le=1.0)
    understanding_weight: float = Field(default=0.0, ge=0.0, le=2.0)
    progress_value: float | None = Field(default=None, ge=0.0, le=1.0)
    progress_weight: float = Field(default=0.0, ge=0.0, le=2.0)
    independence_value: float | None = Field(default=None, ge=0.0, le=1.0)
    independence_weight: float = Field(default=0.0, ge=0.0, le=2.0)
    reason: str = ""


def classify_learning_evidence(
    *,
    tutor_name: str,
    topic: str,
    message: str,
    understanding_signal: str,
    recent_topic_history: list[dict[str, Any]],
) -> LearningEvidence:
    """Extract history-aware evidence for understanding, progress and independence.

    This second, deliberately narrow classifier complements the general
    interaction classifier.  It compares the current message with recent
    interactions on the SAME topic so that repeated questions, progression,
    transfer and answers to tutor knowledge checks can be distinguished.
    """
    client = _client()
    history_text = json.dumps(recent_topic_history[-6:], ensure_ascii=False, indent=2)

    instructions = f"""
You estimate FORMATIVE LEARNING EVIDENCE for a classroom AI tutor called
{tutor_name}. This is NOT grading. Be conservative and evidence-based.

Current topic: {topic}
The general classifier's current-message understanding signal is:
{understanding_signal}

Use the recent SAME-TOPIC history below to determine whether the learner is
showing learning over time. Do not penalize a learner merely for asking for
help, asking a difficult question, pasting an error, or being uncertain.

Choose exactly one primary evidence_type. The types mean:
- explicit_positive: current message clearly demonstrates correct conceptual
  understanding. understanding_value about 0.9-1.0, weight 1.0-1.5.
- explicit_negative: current message clearly endorses incorrect reasoning.
  understanding_value about 0.0-0.1, weight 1.0-1.5.
- repeated_question: substantially the same conceptual question/problem has
  already been answered and the learner now repeats it WITHOUT a new attempt,
  measurement, detail, interpretation, or deeper step. This is only mild
  negative evidence: understanding_value about 0.30-0.40 and progress_value
  about 0.20-0.35, usually weight 0.5-0.8.
- advanced_question: the learner asks a more advanced question that genuinely
  relies on or correctly uses ideas from earlier work. Merely mentioning an
  advanced term is not enough. Use mild positive understanding/progress
  evidence, usually value 0.70-0.80 and weight 0.4-0.7.
- knowledge_transfer: the learner correctly applies an earlier concept in a new
  situation, component or problem. This is strong positive evidence, usually
  understanding 0.85-0.95, progress 0.80-0.95.
- check_answer_positive: the previous tutor turn explicitly asked the learner
  to explain/predict/check understanding and the current message answers that
  check correctly. Strong positive evidence.
- check_answer_negative: the current answer to such a tutor check clearly
  demonstrates incorrect understanding. Strong negative evidence.
- progressive_followup: the learner follows up on a previous problem with a
  new test, measurement, observation, refined hypothesis, or materially more
  specific question. This should NEVER be treated as repeated_question. It is
  mild positive progress evidence and may be mild positive understanding.
- independent_debugging: learner reports their own test, diagnosis, correction
  or experiment. This is positive independence/progress evidence.
- solution_seeking_without_attempt: use ONLY when history shows repeated requests
  for a complete solution/code while the learner provides no own attempt even
  after prior scaffolding. Asking for help once is neutral. This is mild
  negative independence/progress evidence, not automatically poor understanding.
- neutral: there is insufficient evidence for any of the above.

Three axes:
1. understanding_value: 0=clear weak understanding, 1=clear strong
   understanding, None=no evidence.
2. progress_value: 0=no learning movement / regression, 1=strong learning
   progression, None=no evidence.
3. independence_value: 0=strong dependence on supplied solutions, 1=strong
   self-directed testing/reasoning, None=no evidence.

Weights express evidential strength, not severity. 0 means that axis must not
move. Prefer low weights and None when uncertain. Never infer knowledge from
the quality of the tutor's answer. Base evidence on what the learner actually
demonstrates. Keep `reason` to one short factual sentence and do not include
private labels or advice.

Recent same-topic history (oldest to newest):
{history_text}
""".strip()

    response = client.responses.parse(
        model=CLASSIFIER_MODEL,
        instructions=instructions,
        input=message,
        text_format=LearningEvidence,
    )
    if response.output_parsed is None:
        return LearningEvidence(reason="No reliable learning evidence was produced.")
    return response.output_parsed

def generate_tutor_answer(
    *,
    tutor_instructions: str,
    activity_instructions: str,
    student_state: dict[str, Any],
    classification: InteractionClassification,
    history: list[dict[str, str]],
    message: str,
    vector_store_id: str | None,
    microcheck_due: bool = False,
    scaffolding: dict[str, str] | None = None,
) -> str:
    """Generate the learner-facing answer with optional hosted file search."""
    client = _client()

    # Keep machine-generated context clearly separated from author-written
    # tutor instructions. The student state is explicitly described as an
    # uncertain estimate so the model does not treat it as an assessment grade.
    runtime_context = f"""

## Current activity
{activity_instructions or 'No specific activity was selected.'}

## Estimated learner state
This is an uncertain internal estimate based only on prior chat interactions.
Never present it as a grade or objective measurement.
`understanding_estimate` ranges from 0 to 1: values near 0 indicate evidence
of weak demonstrated understanding, values near 1 indicate evidence of strong
demonstrated understanding, and values near 0.5 indicate uncertainty.
`observations` counts all classified student messages for the topic, while
`evidence_observations` counts only messages that provided useful formative
evidence. The learner model also estimates progress and independence. Treat all
three dimensions as uncertain, especially when evidence weights are small, and
never expose the internal values to the learner.
{json.dumps(student_state, ensure_ascii=False, indent=2)}

## Adaptive scaffolding
Selected mode: {(scaffolding or {}).get('mode', 'balanced')}
Internal reason: {(scaffolding or {}).get('reason', '')}

Apply the selected mode to HOW MUCH help you provide, while still following the
author-written tutor and activity instructions:
- rebuild: repair the prerequisite concept first. Use one concrete representation
  or example, break the task into a very small step, and explicitly contrast a
  likely incorrect idea with the correct relation. Do not overwhelm the learner
  with a complete solution.
- guided: give one useful hint or partial step, then leave a meaningful part for
  the learner. Ask for a prediction, choice, measurement, explanation, or next
  action. If the learner repeated a question, change representation or strategy
  instead of repeating the previous explanation.
- fading: deliberately reduce assistance. Do not provide a complete solution or
  full code when a hint, question, skeleton, or diagnostic step is sufficient.
  Require the learner to propose or perform the next step before giving more.
- challenge: provide minimal procedural help and raise cognitive demand. Invite
  transfer, comparison, justification, optimization, prediction, or extension to
  a new situation. Avoid re-explaining mastered basics unless the learner asks.
- balanced: use the minimum useful support appropriate to the current request.

Scaffolding must remain responsive: if the learner clearly lacks a prerequisite,
temporarily give more structure even in fading/challenge mode. If safety or a
blocked technical situation requires a direct instruction, provide it. Never tell
the learner which scaffolding mode was selected.

## Current interaction classification
{classification.model_dump_json(indent=2)}

Use the classification only to choose an appropriate pedagogical response.
Prefer the minimum useful support. Do not mention internal labels, learner
scores, analytics, or classification to the student.

## Micro-check
Micro-check requested: {microcheck_due}
If this is True, finish the response with exactly ONE short diagnostic question
that asks the learner to predict, explain, choose, or apply the CURRENT topic.
Match its difficulty to the scaffolding mode: rebuild/guided checks should probe
a prerequisite or immediate relation; fading/challenge checks should require
more independent explanation or transfer. The question must test understanding
rather than recall, should normally be answerable in one or two sentences, and
must not reveal the answer. Integrate it naturally into the response without
calling it a test, quiz, micro-check, or assessment. If False, do not add a
diagnostic question merely for analytics.
"""

    tools: list[dict[str, Any]] = []
    if vector_store_id:
        tools.append(
            {
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
                # Keep retrieval compact; this can be tuned later for cost and quality.
                "max_num_results": 5,
            }
        )

    response = client.responses.create(
        model=TUTOR_MODEL,
        instructions=tutor_instructions + runtime_context,
        input=[*history, {"role": "user", "content": message}],
        tools=tools,
    )

    answer = (response.output_text or "").strip()
    if not answer:
        raise RuntimeError("Tutor ni vrnil besedilnega odgovora.")
    return answer

# Learner Model v3

The learner model is formative, uncertain and explicitly **not a grade**.
Each topic now contains three independent estimates:

- `understanding_estimate`: demonstrated conceptual understanding;
- `progress_estimate`: evidence that the learner is moving forward over time;
- `independence_estimate`: evidence of self-directed testing/reasoning rather
  than repeated dependence on supplied solutions.

All three scales use 0..1. A value of 0.5 means *uncertain / insufficient
evidence*, not "average performance".

## Evidence types

The history-aware evidence classifier compares the current message with recent
interactions on the same topic and can detect:

- explicit positive/negative understanding;
- repeated questions with no new attempt or deeper step;
- genuinely more advanced questions;
- transfer of prior knowledge to a new situation;
- correct/incorrect answers to tutor knowledge checks;
- progressive follow-ups with new tests, measurements or hypotheses;
- independent debugging;
- repeated solution-seeking without an own attempt.

Ordinary questions, requests for help, pasted compiler errors and uncertainty
remain neutral unless the learner actually demonstrates something from which a
formative inference can reasonably be made.

## Weighted updates

Evidence is a value in 0..1 with an independent weight. The update uses a weak
prior centred on 0.5 with strength 2. New evidence is combined as a weighted
running estimate. This makes early evidence visible while preventing one later
message from radically changing a well-supported estimate.

The learner state also records evidence weights and `evidence_types`, making the
estimate auditable and explainable.

## API cost

Learner Model v3 adds one additional small classifier call per student message.
This is intentional because history-aware comparisons cannot be derived safely
from the existing classification schema without changing the application's
shared `InteractionClassification` model.

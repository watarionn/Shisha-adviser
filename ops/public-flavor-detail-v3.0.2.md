# Public flavor detail UI v3.0.2

## Goal
Recommended flavors should be understandable before the user asks a follow-up question.

## UI behavior
- Recommendation cards are keyboard- and tap-accessible.
- Tapping a flavor opens a bottom-sheet detail view.
- The detail view shows a short Japanese taste summary, impression tags, source-derived flavor cues, and the seven sensory axes.
- Axes below confidence 0.45 are visually de-emphasized and are not used to write the natural-language summary.
- Mix labels are split into components when possible and each component is summarized independently.
- Unknown/new flavors fail closed with an explicit "details pending" message instead of invented descriptions.

## Data contract
`public_web_v3_0/flavor-details.json` is a small manifest for five compact data shards generated from the audited 200-flavor scored recommender scope in Recovery Canonical v2.7 working data.

Fields include:
- brand / name / flavor_id
- summary
- impression_tags
- flavor_notes_ja
- evidence_cue
- seven sensory axes as compact value/confidence arrays
- evidence_coverage

## Safety / provenance rules
- LOW_CONFIDENCE_PRIOR values remain available for transparent profile display but are dimmed.
- Natural-language flavor summaries only use source-cue translations and axes with confidence >= 0.45.
- No sensory body value is inferred from tobacco strength or nicotine strength.
- The detail catalog is read-only UI metadata and does not mutate recommender Scores.

## Runtime
The production entrypoint now launches `production_public_web_v3_0_2.py`, which wraps v3.0.1 and serves/injects the flavor-detail assets without changing the recommendation API contract.

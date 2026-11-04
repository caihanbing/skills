# Source-risk rubric and explicit calibration

Source risk is a 1–5 judgment about whether one Source can carry a Claim; agent, broker, operator, or landlord identity is not proof of deception. Record observed, missing, and uncertain evidence with every rating.

| Risk | Use |
|---:|---|
| 1–2 | Specific, timely, attributable, and corroborated evidence; minor gaps only |
| 3 | Material ambiguity, limited corroboration, or incomplete key terms |
| 4–5 | Compounded lead-generation, implausible terms, mismatch, contradiction, or no credible resolution |

Calibration is maintenance, not ordinary research. Run it only when the user explicitly requests it. Use `scripts/calibration_metrics.py --assign-split <public-post-id>` before a user score is shown; append only the public ID/URL, times, scores, evidence flags, round, and deterministic split to `state/calibration-log.jsonl` after a score is received. Never store post body or housing preferences.

Holdout alignment is good only at 30+ items across 3+ rounds, every user risk grade represented at least four times, MAE ≤ 0.75, within-one ≥ 85%, high-risk recall 100%, and high-risk precision ≥ 50%. Weighted kappa is diagnostic only.

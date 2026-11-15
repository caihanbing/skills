# Work Item Workflow

Use `intake → clarified → planned → implementing → verifying → handoff-ready → closed`.

`blocked`, `cancelled`, and `rolled-back` are exceptional states. A failed verification or review returns the item to `implementing`.

| Transition | Blocking gate |
| --- | --- |
| `clarified` | No `BLOCKER` decision remains. |
| `planned` | Scope, at least one requirement and acceptance criterion, and all impact dimensions are resolved. |
| `implementing` | A concrete, well-formed plan exists; unchecked items are allowed. |
| `verifying` | All retained plan items are complete. Deferred scope is tracked through the existing requirement, decision and follow-up Work Item records. |
| `handoff-ready` | Requirements have verification evidence; medium/high review passes; high risk includes release and rollback; user regression handoff is complete. |
| `closed` | User regression is passed or not required; durable Feature knowledge is updated. |

Treat `OPEN` as non-blocking only when it is unrelated to the next transition. Elevate the risk rather than suppress a material uncertainty.

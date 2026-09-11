# Representative Feature Knowledge Evals

- Fresh audit of a Feature Doc whose `code-basis` does not match HEAD: report drift without silently rewriting it.
- Fenced Markdown containing a level-two heading: ignore the fenced heading during structural validation.
- Duplicate header metadata, a future verified date, and a broken image link: reject structural validation.
- Incremental bug fix affecting two Feature IDs: update both long-lived documents, not a task-specific Feature Doc.

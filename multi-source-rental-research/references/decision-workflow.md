# Decision workflow

## Select the scope

Use **catalog mode** only for an explicit inventory, table, or per-category quantity. Keep residential communities and centralized long-term rental apartments separate. Seek the requested count through 3 km, then 5 km, then 8 km expansion, and report any truthful shortage.

Otherwise use decision mode:

| Request shape | Submode | Candidate boundary |
|---|---|---|
| Nearby options, recommendation, budget, commute | Discovery decision | Build leads, then filter Offers and Projects |
| Named project(s), compare A/B, due diligence | Scoped due diligence | Research only named candidates/offers unless alternatives are requested |

Default property types remain residential communities and centralized long-term rental apartments. Respect an explicit type limit. Include another long-term type only with user permission, in its own category.

## Build the decision profile

Extract known budget, recurring-fee inclusion, commute target/window, room type, move-in timing, lease term, hard constraints, and weights. Ask only for information that blocks the requested decision.

Use these states exactly:

- **known**: apply the stated constraint;
- **unknown**: do not invent a value or filter on it;
- **no_constraint**: user explicitly says it does not matter;
- **blocking unknown**: a stated P0 requirement has no evidence for an offer, so it cannot pass.

Establish the **commute constraint** and resolve the target location before discovery. Do not calculate a candidate commute until a candidate location is known. Use route data with departure/return window and sample time when available; otherwise label a distance fallback and never convert it into a precise commute promise.

## Build a place-based candidate pool

For Catalog and Discovery decision work, read [discovery-sources.md](discovery-sources.md). Select applicable geographic and rental-market providers for the target city, record each attempt, and preserve the provider/source chain. A `ProjectLead` identifies a possible physical or operated project. An `OfferLead` identifies a possible dated room, unit, or contract and must remain attached to its potential parent Project rather than being counted as a separate project.

Conservatively normalize leads by name, address, operator, and property type. Flag possible duplicates but never auto-merge. Report three distinct counts: raw leads, manually resolved unique projects, and potential Offer leads. A map POI is a discovery lead rather than a building, fee, or management fact. A rental-platform listing is a dated, scoped market Offer lead. The absence of a lead from a provider proves neither project absence nor lack of availability.

## Research and decide

### Catalog mode

Before each radius expansion, attempt all configured providers applicable to the target city and record unavailable or limited access. Expand from 3 km to 5 km to 8 km only for a category still short.

For every final catalog project, perform **项目级精确小红书检索** with one or two identity-specific queries using the canonical name plus available alias, address, or operator. Record the query and evidence state: public project match found, no public result, access limited, or identity uncertain. This is verification, not deep research; do not replace a missing project match with generic posts about the target location.

### Discovery decision

Start with an applicable geographic and rental-market source. Expand to secondary sources only when the resulting candidate coverage is insufficient for the requested decision, a required property type is missing, or a source class is absent. After candidate locations are known, calculate commute and apply the commute and P0 gates before expensive Xiaohongshu research.

Form an Offer-centric shortlist, then deep-research Xiaohongshu only for its 3–6 most relevant Offers/projects. For every deep candidate, search by project identity with neutral, positive, negative/risk, and decision-specific queries. Keep Project context distinct from the concrete Offer being considered.

### Scoped due diligence

Skip place-based candidate-pool expansion and study only named Projects/Offers, unless the user asks for alternatives.

State search dates, boundaries, source-class coverage, inaccessible evidence, and that the result is a bounded evidence search rather than full market coverage. Xiaohongshu supports attributed renter experience, comment cross-checking, and source-risk assessment; it does not turn a map lead or a listing into a verified fact.

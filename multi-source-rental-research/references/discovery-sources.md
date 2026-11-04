# Discovery sources

Use an adaptive source strategy for place-based work. Select providers that are applicable to the **target city** and usable in the current environment; record providers that are unavailable, limited, or not applicable. Never send a request for one city to a fixed endpoint for another city.

| Source class | Provider examples | Role |
|---|---|---|
| Geographic | AMap / 高德地图; Google Maps where usable | Project names, addresses, geographic range, and explicitly labelled distance references |
| Rental market | Ke / 贝壳找房; Leyoujia / 乐有家 where the target city is supported | Project and dated Offer leads, availability signals, and market references |

The default configured set is AMap and Google Maps for geographic discovery, and Ke and Leyoujia for rental-market discovery. They are defaults, not a nationwide URL registry: use only a city-appropriate public entry point, and use an equivalent public source only when the configured source is not applicable or accessible.

The provider examples are not a mandatory ordered checklist. Start with a primary applicable provider in each source class. For a Discovery decision, add a secondary provider only when coverage is missing, a requested type has no viable candidates, or the resulting pool is not sufficient for a defensible shortlist. For Catalog mode, attempt every configured provider applicable to the target city before expanding the radius from 3 km to 5 km to 8 km.

If no usable provider exists in one class, continue with the available class and state the coverage gap. A source returning no lead is **coverage evidence, not negative existence evidence**: it does not prove that a project does not exist or that it has no vacancy.

## Query roles and records

- **Map discovery:** use the target location plus property-category terms to maximize project recall.
- **Rental-market discovery:** use area or transit location, budget, room type, and rental type to find dated Offer leads.
- **Xiaohongshu retrieval:** after project identity is known, use the project name plus an alias, address, operator, and experience terms relevant to the decision.

Record provider, provider class, target-city applicability, query, entry/result URL, retrieved date, access status, limitation reason, and the observed lead. In V1.1, every attempt has `applicability_status`: `applicable`, `not_applicable`, or `unknown`; `not_applicable` needs a basis. Only an applicable, accessible or limited attempt may yield a Lead. When structured data is available, validate it with `scripts/validate_discovery.py`. It distinguishes allowlisted `project` leads from `offer` leads, preserves the raw source chain, and reports raw leads, manually resolved unique projects, and potential Offer leads. It never resolves or merges entities automatically.

Maps provide discovery leads, not property or cost facts. Rental-platform leads are not current availability guarantees; only a dated and applicable Offer may later be represented as a market reference.

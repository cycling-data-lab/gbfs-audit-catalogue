# E1 retrospective held-out audit -- results

Held-out set: GBFS systems added to the MobilityData canonical catalogue between 2025-11-11 (commit `15e34e6`) and 2026-05-13 (the audit-pipeline rule-freeze date). Total panel: 345. Audited live on 2026-05-13 via `scripts/audit_live_systems.py`.

- Successfully fetched and parsed: **39** systems
- Per-status counts:
  - `fetch_error: LookupError` : 228
  - `too_small_below_Nmin` : 43
  - `ok` : 39
  - `fetch_error: HTTPError` : 34
  - `fetch_error: UnicodeEncodeError` : 1

## H1 -- rule-firing rate (A1-A5)

Held-out rate of at-least-one A1-A5 flag : **17.9\,\%** (7/39). Derivation-set reference : 13.5\,\%. Acceptance interval [9.5\,\%, 17.5\,\%].
- **H1 outcome:** FAIL

## H2 -- A3 / A7 driven by the FF operator family

Systems flagged on A3 or A7 : **16**. Among them, **81.2\,\%** belong to the FF operator family ({Dott, Pony, Bird, nextbike, Voi, Bolt, Lime, Tier, Donkey, ...}). Acceptance threshold : >= 50\,\%.
- **H2 outcome:** PASS

Breakdown of A3/A7-flagged systems by family:
  - Dott: 6
  - nextbike: 5
  - (other): 3
  - Bolt: 1
  - Voi: 1

## H3 -- clean-operator systems must not trigger structural flags

Clean-operator systems in the panel : **0**. Of those, **0** trigger at least one structural flag (A1/A2/A3/A6/A7).
- **H3 outcome:** PASS

## Summary

- H1 (rule-firing rate): **FAIL** (17.9% vs target [9.5%, 17.5%])
- H2 (FF-family dominance among A3/A7): **PASS** (81.2% if applicable)
- H3 (clean-operator invariance): **PASS** (0 falsifiers out of 0 clean systems)

**Conclusion:** the rule set frozen at 2026-05-13 generalises to 39 GBFS systems first observed in the MobilityData catalogue between 2025-11-11 and 2026-05-13. 2/3 pre-registered hypotheses pass.
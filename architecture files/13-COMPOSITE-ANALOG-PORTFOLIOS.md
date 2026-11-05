# Composite analog portfolios and residual gaps

The portfolio feature answers which small set of Earth campaigns can cover the accepted mission's reproducible test requirements. It does not combine locations into a fictional single environment or erase unresolved planetary conditions. Read [11](11-QUALIFICATION-AND-UNCERTAINTY.md) and [12](12-ROUTE-ENERGY-AND-VERIFICATION.md) before implementing `optimize_portfolio`.

## 1. Inputs and eligibility

Inputs are the immutable mission revision, optional rover revision, candidate/qualification revisions, known verification results, maximum selected sites, required evidence scope, and an accepted portfolio policy artifact. All inputs share workspace, run/mode, mission revision, and compatible interpretation. A qualification-only portfolio is permitted without a rover but must not claim rover compatibility or a verified route.

Create a binary coverage matrix `a[i,j]` for requirement i and candidate j. It is 1 only if that candidate has an adequate PASS at the required scope and stage, with resolved blocking critic issues. Preliminary terrain availability is not final coverage of a route-dependent continuity requirement. UNKNOWN, FAIL, and GAP provide no binary coverage. PARTIAL is retained separately with its supported subcondition and may contribute only through a contract-defined compositional rule.

Candidate metadata must distinguish evidence-backed usability from unresolved logistics. Version 1 may not know access permissions, protected land, current hazards, or travel cost. Report these as unassessed planning factors, never a fabricated operational clearance or a reason to declare field deployment approved.

## 2. Requirements that can and cannot be split

Partition requirements into:

- **Independently coverable:** site A can support mobility trials while site B supports a separate thermal campaign.
- **Additive:** repeated trials across sites may be summed only when the mission explicitly permits that experimental design and the measurement is comparable.
- **Coupled:** one experiment must provide slope exposure, science access, return, and reserve on the same continuous route. Those conditions must share one site and one verified route.
- **Natural physical gaps:** reduced gravity, vacuum, or another explicitly non-reproducible condition remains a gap outside the Earth-site coverage problem.

Represent coupled groups in the policy artifact and evaluate them as joint items. Individual PASS rows from different candidates cannot satisfy a joint route. Unknown sampling geology plus supported mobility at another site does not become supported geology by combination. Two PARTIAL thermal proxies do not automatically equal one complete physical thermal test.

## 3. Optimization objective

Use deterministic exhaustive subset enumeration for the initial small candidate set. With up to 12 eligible candidates, a default maximum of three sites, and the API's allowed maximum of five sites, enumeration is simple, reviewable, and avoids a new solver dependency. Initial full-analysis discovery returns at most five candidates, so this exact bounded optimizer is cheap. Sort candidate UUIDs for stable ties.

Optimize lexicographically:

1. Maximize covered mandatory reproducible requirement weight, respecting coupled groups.
2. Maximize covered optional reproducible requirement weight.
3. Minimize site count.
4. Prefer stronger accepted evidence/verified coverage according to a fixed documented rank.
5. Break remaining ties by sorted candidate UUID list.

This prevents adding unnecessary sites merely to improve an arbitrary score. The numerical `objective_value` in the shared wire object is the sum of covered requirement weights, not a Mars-similarity percent; the detailed lexicographic objective and tie-breaks are stored in the optimization evidence. If an explicit cost penalty is later requested, require known cost inputs and a reviewed policy version rather than inventing prices.

For each subset S:

```text
covered_i(S) = any(a[i,j]==1 for j in S)  # independently coverable requirements
covered_group_g(S) = any(joint_verified[g,j]==1 for j in S)
mandatory_coverage = sum(w_i * covered_i(S) for mandatory reproducible i)
optional_coverage = sum(w_i * covered_i(S) for optional reproducible i)
```

Treat coupled groups once in optimization weight accounting, then expand their assigned requirements in the displayed matrix; do not double-count group and child weights. Define additive aggregation separately per observable. Exhaustive enumeration of site subsets does not imply exhaustive route-search optimality; inherit all source and verification limitations.

## 4. Output contract

Return `CompositePortfolio` exactly as defined in `contracts/domain.schema.json`: selected candidate IDs, requirement assignments, coverage states `FULL`, `PARTIAL`, `NONE`, `UNKNOWN`, or `GAP`, objective value, algorithm ID, residual requirement IDs, and limitations. Every selected site must have a named responsibility and supporting qualification/evidence IDs in the associated optimization artifact.

Coverage state semantics:

| Portfolio coverage | Meaning |
|---|---|
| `FULL` | At least one assigned site or permitted composite experiment demonstrably meets the requirement |
| `PARTIAL` | A defined supported subcondition exists; residual explicitly listed |
| `NONE` | Adequate evaluated evidence does not meet the requirement in selected sites |
| `UNKNOWN` | Missing/incompatible evidence prevents deciding coverage |
| `GAP` | Natural Earth site selection cannot directly reproduce the requested condition |

Distinguish "smallest set among evaluated candidates covering these requirements" from "globally minimal Earth campaign." The former is supported; the latter requires a much broader search and operational model. An empty portfolio can be the correct result when no candidate has adequate relevant evidence. Do not force one site merely to fill the interface.

## 5. Interaction with agents and replanning

The Qualification Agent prepares eligible coverage; the Test Designer supplies experiment-coupling rules; the deterministic optimizer selects subsets; the Critic checks whether the combination changes the experiment question. The Mission Director may propose investigating a residual requirement at an additional candidate within its budget.

Each site requiring PROVE IT has its own immutable test and result. A portfolio that includes an unverified proposed test is labeled planned/partially verified. It cannot inherit PASS from a different site's route. If subsequent evidence invalidates one site's requirement, regenerate portfolio and passport revisions; retain the original record for audit.

A residual physical gap produces a recommended facility/simulation test in the passport. No facility is represented as a qualified Earth site unless an actual supported facility adapter and experiment contract are implemented.

## 6. Deterministic acceptance fixtures

Use synthetic requirement matrices with no real-site claims:

1. Site A passes mobility, site B passes thermal, C passes both. With equal evidence and no coupling issue, choose C because it covers the same weights with one site.
2. Remove C; choose A+B for independent campaigns and retain gravity as GAP.
3. Make mobility and thermal a same-test coupled requirement; A+B cannot satisfy the group. Return residual coverage rather than two-site FULL.
4. Make B thermal UNKNOWN; A+B cannot count thermal as covered, and B should not be selected if it adds no supported value.
5. Make site A's route verification INCONCLUSIVE; route-dependent FULL disappears while adequate independent context remains.
6. Give two equal single-site solutions; output remains stable across input order and process restarts.
7. Supply different mission revisions or synthetic/live mixing; reject the operation before optimization.

These tests establish correct coverage logic. Real portfolio scientific validity still depends on the site-specific evidence gates and outcome-neutral validation in [29](29-SCIENTIFIC-VALIDATION.md).

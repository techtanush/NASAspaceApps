# Aradhya — self-audit and loophole checklist

Run this entire file before you declare done (phase U6). It proves your tests can fail, the UI tells the truth, and no shortcut slipped in. Record each result in `STATUS.json.self_audit`.

## 1. Automated scans (implement and run both under `scripts/ui/`)

```bash
python3 scripts/ui/forbidden_scan.py --json out/forbidden.json      # exit 0 required
python3 scripts/ui/mutation_check.py --json out/mutations.json      # exit 0 required: every mutant killed (M1–M36)
python3 scripts/ui/verify_exports.py --self-test                    # renders the 9 fixtures and runs the J01 step-14 checks
```

**`forbidden_scan.py`** scans `apps/web/src`, `analogforge/src/analogforge/rendering/passport`, your tests and scripts; fails on: `TODO`, `FIXME`, `HACK`, `XXX`, `NotImplementedError`; `dangerouslySetInnerHTML`, `innerHTML =`, `eval(`, `new Function(`, `document.write`; `localStorage`/`sessionStorage` used for run, mission, qualification or snapshot data (view preferences only, listed allow-list); `fetch(` or `XMLHttpRequest` outside `api/`; absolute `http(s)://` URLs in `src` other than documentation links in comments and the `VITE_API_BASE_URL` default; hand-written string unions equal to a scientific enum (`'PASS' | 'PARTIAL'`, `'INCONCLUSIVE'`, `'NOT_NATURALLY_REPRODUCIBLE'` …) outside `generated/`; `Math.random`, `Date.now`, `new Date()` in renderer-adjacent TS display code except the time formatter; arithmetic on scientific values in feature code (flagged pattern: `\.(value|measured|threshold|lower|upper|reserve)\w*\s*[-+*/]\s*`, each hit must be explicitly allow-listed with a justification such as "layout pixels"); `test.skip`/`test.fixme`/`it.skip`/`describe.skip`/`xit`/`.only`; in the renderer: any import outside stdlib/`jinja2`/`markupsafe`/`pydantic`/kit, `datetime.now`, `time.time`, `os.environ`, `open(…, 'w')`; hex/`rgb(`/`hsl(` colour literals outside `styles/tokens.css` and `maps/`; `linear-gradient`, `radial-gradient`, `backdrop-filter`, `text-shadow`, `border-radius` above 6 px, emoji code points, `Lorem ipsum`, `Coming soon` in `src`; font CDN hosts (`fonts.googleapis`, `fonts.gstatic`, `use.typekit`, `cdnjs`, `unpkg`, `jsdelivr`); imports of banned UI/animation libraries (`@mui`, `antd`, `@chakra-ui`, `@mantine`, `bootstrap`, `framer-motion`, `gsap`, `lottie`, `chart.js`, `echarts`); NASA insignia filenames (`meatball`, `nasa-logo`, `worm`); `mock` imports reachable from non-mock code paths (`src/mock` must only be imported behind `import.meta.env.VITE_API_MOCK`).

**`mutation_check.py`** applies each mutation to a temporary copy, runs the named tests, and requires **failure**. A surviving mutant means a missing/weak test — fix the test, not the script.

| # | Mutation | Must be killed by |
| --- | --- | --- |
| M1 | one `data-testid` renamed | `testids.test.ts` / journey |
| M2 | null measurement rendered as `0` | `format/quantity.test.ts`, FE-002 |
| M3 | SSE duplicate-seq check removed | `runStream.test.ts` |
| M4 | idempotency key regenerated on retry | FE-006 |
| M5 | candidate selection applied optimistically before server ack | FE-006 / J01 |
| M6 | mock banner removed | UIX-10 / J01 |
| M7 | production build permits `VITE_API_MOCK=1` | `prod-build-guard` |
| M8 | renderer HTML not escaped | `test_escaping.py` |
| M9 | CSV formula escaping removed | `test_csv.py` / `test_escaping.py` |
| M10 | renderer prints the current time | `test_determinism.py` |
| M11 | attempts truncated to the last one | `test_html.py` / J01 step 12–13 |
| M12 | optional UNKNOWN row hidden from the matrix | UIX-05 / J01 step 9 |
| M13 | affine y-axis sign flipped | `affine.test.ts` |
| M14 | Earth corner order changed (NW,NE,SE,SW → NW,SE,…) | `affine.test.ts` / SCN-17 consumer |
| M15 | cover headline "Qualified…" shown for a FAIL | `test_html.py` |
| M16 | GAP rendered with the FAIL label/icon | UIX-05 |
| M17 | HTML export references an external URL | `test_html.py` / `test_purity.py` |
| M18 | UI recomputes `manifest_sha256` client-side | FE-010 / J01 step 13 |
| M19 | SSE cursor not reset on run switch | FE-005 |
| M20 | draft banner missing for `is_draft=true` | `test_html.py` |
| M21 | JSON export drops `canonical_manifest` | `test_json.py` |
| M22 | CSV column order changed | `test_csv.py` |
| M23 | assurance `INCOMPLETE` shown as a success badge | UIX-05 |
| M24 | WebGL failure hides the candidate list | `webgl-fallback.spec.ts` |
| M25–M36 | design mutants (gradient, radius, tiny font, numeric alignment, look-alike glyphs, low-contrast token, emoji, no focus ring, min-width page, hex literal, second primary button, font CDN) | `visual_audit`, `verify_tokens`, `forbidden_scan` — list and killers in [10](10-DESIGN-SYSTEM-AND-VISUAL-QA.md) §5 |

## 2. Manual truthfulness proof

For every status in `PASS, PARTIAL, FAIL, GAP, UNKNOWN, PENDING` and every outcome in `PASS, FAIL, INCONCLUSIVE`: screenshot or DOM-dump evidence (paths in `STATUS.json`) that the label, icon and `data-status` differ and no state is color-only. Search the rendered DOM of J01 for `%` characters next to words like "Mars", "similar", "match", "ready": none allowed (the only percentages are modeled battery reserve and coverage fractions with denominators).

## 3. Adversarial reviewers (spawn at least four subagents; each reports findings, you fix)

1. **Truth auditor:** walk every screen against the mock script data and the truth tables of architecture 40; find any place that hides, softens, merges or invents a status; find any text that states a conclusion not taken from a `permitted_statement`.
2. **State-machine breaker:** hit the UI with duplicate, out-of-order, missing and replayed SSE events; 409 conflicts; lost responses; reload mid-run; two tabs; run switching; offline/online flapping; ensure no duplicate command, no lost state, no stale overwrite.
3. **Renderer attacker:** feed hostile and degenerate bundles (huge strings, RTL, emoji, `</script>`, `javascript:` links, CSV injection variants, null everything, zero attempts, 50 attempts, empty candidates, BLOCKED audit, digest mismatch); the output must stay safe, complete and deterministic, or raise the documented `RendererError`.
4. **Accessibility/responsive auditor:** keyboard-only through J01; focus order/traps in dialogs and drawers; screen-reader names for the matrix and map alternatives; 390 px and 200 % zoom; reduced motion.
5. (optional) **Contract auditor:** compare every request your UI sends with the bundled OpenAPI request schemas (including required headers and `expected_revision`).

## 4. Final truth checks

* `grep -rn "NOT_IMPLEMENTED\|coming soon\|placeholder" apps/web/src` finds no user-visible stubs.
* Every button in the DOM of J01–J13 has an observable effect asserted by a test (list them in `STATUS.json`).
* Delete `node_modules`, `dist`, `out`; run `pnpm install --frozen-lockfile` + the whole gate again: identical results.
* Run the renderer twice in separate processes with different `PYTHONHASHSEED`: identical bytes.
* `python3 "architecture files/contracts/kit/materialize.py" --verify`; ownership check; then fill `STATUS.json`, commit (no build output), push.

## 5. Authoring and audit regressions from the November 11 review

Preserve `MissionEditor.review.test.tsx` and `PassportView.review.test.tsx` in every branch gate. They assert five asynchronous authoring cases: waiting for an existing mission to load before enabling edits; switching directly between mission edit routes; editing while the initial save receipt is delayed; editing during fingerprint preparation; and editing while acceptance is pending. A failed initial read must expose a safe retry without a writable blank form. A receipt may update the editor only when it belongs to the current route and draft version. A later edit must eventually be saved or show a recoverable conflict/error.

Before showing an audited passport, validate the resolved assurance artifact against the unchanged frozen schema and bind its workspace, run, mode, mission hash, and rover hash to the displayed accepted inputs. A malformed or mismatched report stays INCOMPLETE, has a retry action, and exposes no download controls. Do not recompute scientific decisions or manifest digests in the UI. Generate the browser validator using `scripts/ui/generate_assurance_validator.mjs`; builds reject a stale generated file.

The mutation runner must pass its unmodified isolated unit/browser controls before counting mutant failures. Its Vite filesystem allow-list must include both the temporary source tree and the owning dependency checkout. An alternate browser origin must be used consistently for navigation, server readiness, and the actual development-server port.

Mission authoring polish is scoped in `apps/web/src/styles/authoring.css`. Preserve paired geographic inputs at mobile widths, explicit degree units, active-step contrast, keyboard focus, and 44px touch targets. Run the existing authoring scroll check and the complete visual matrix after changing these styles. Keep the existing statuses and scientific wording.

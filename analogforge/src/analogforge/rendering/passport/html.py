"""Self-contained, escaped report with complete structured record appendices."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, StrictUndefined

from analogforge.ports.passport_renderer import PassportExportBundle, ProvidedAsset

from .assets import image_data_uris
from .escaping import html_text

CSS = """
:root { color-scheme: light; font-family: Arial, sans-serif; color: #17212b; background: #fff; }
body { margin: 0 auto; max-width: 1100px; padding: 32px; line-height: 1.5; font-size: 14px; }
h1 { font-size: 26px; } h2 { border-bottom: 2px solid #52606d; padding-bottom: 8px; margin-top: 32px; }
h3 { font-size: 17px; } table { width: 100%; border-collapse: collapse; margin-block: 16px; }
th, td { padding: 8px; border: 1px solid #8492a0; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { background: #edf0f3; } .numeric { text-align: right; font-variant-numeric: tabular-nums; }
.mode, .draft { display: inline-block; padding: 8px 12px; border: 2px solid currentColor; font-weight: bold; }
.draft { color: #8a3000; } .hash { font-family: monospace; overflow-wrap: anywhere; }
li, p, dd { overflow-wrap: anywhere; } dl.record { margin-left: 16px; } dt { font-weight: bold; }
dd { margin-left: 16px; margin-bottom: 8px; } .attempt, tr { break-inside: avoid; page-break-inside: avoid; }
img { max-width: 100%; max-height: 500px; } thead { display: table-header-group; }
@page { margin: 18mm; }
@media print { :root, body { background: #fff; color: #000; } body { padding: 0; max-width: none; }
 h2 { break-after: avoid; } table { font-size: 11px; } .mode { border-color: #000; } }
"""

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AnalogForge — {{ b.mission.name }}</title>
<style>{{ css }}</style>
</head>
<body>
{% macro record(value) -%}
{% if value is mapping %}<dl class="record">{% for key, item in value.items() %}<dt>{{ key }}</dt>
<dd>{{ record(item) }}</dd>{% endfor %}</dl>
{% elif value is sequence and value is not string %}
<ul>{% for item in value %}
<li>{{ record(item) }}
</li>{% else %}
<li>None recorded</li>{% endfor %}
</ul>
{% else %}{{ text(value) }}{% endif %}
{%- endmacro %}
<section id="cover">
<p class="mode">{{ b.mode.upper() }}
{% if b.replay_source_run_id %}
 — source run {{ b.replay_source_run_id }}
{% endif %}
</p>
{% if b.is_draft %}<p class="draft">DRAFT — INCOMPLETE</p>{% endif %}
<h1>AnalogForge — {{ b.mission.name }}</h1>
<h2>{{ headline }}</h2>
{% if qualified %}{{ record(b.passport.qualified_uses) }}{% endif %}
<p>Modeled terrain-feasibility verification — not physical rover execution</p>
<p>Generated {{ b.generated_at }} · Passport {{ b.passport.id }} · Run {{ b.passport.run_id }}</p>
<p>Mission revision {{ b.mission.revision }} · {{ b.mission.id }} · Target {{ b.mission.target.body }}</p>
<p>{{ b.rover.name if b.rover else 'No rover supplied — site qualification only' }}</p>
<p>Manifest SHA-256 <span class="hash">{{ b.manifest_sha256 }}</span>
</p>
<p>Assurance: {{ b.assurance.publication if b.assurance else 'INCOMPLETE' }}</p>
<h3>Irreproducible conditions and critical unknowns</h3>{{ record(b.passport.unsupported_uses) }}
{{ record(b.passport.unknowns) }}

</section>
<section id="mission-contract">
<h2>Mission Test Contract</h2>{{ record(data.mission) }}</section>
<section id="target-and-sites">
<h2>Target and Earth sites</h2>
<p>Display context only; site access and physical performance are not established.</p>
{{ record(data.target_profile) }}{% for c in data.candidates %}<h3>{{ c.name }}</h3>{{ record(c) }}{% endfor %}
{% for image in images %}<figure>
<img src="{{ image.uri }}" alt="{{ image.key }}">
<figcaption>{{ image.key }} · {{ image.sha256 }}</figcaption>
</figure>{% endfor %}
{% if not images %}
<p>Report imagery unavailable; numeric and geometry records are included above.</p>{% endif %}
</section>
<section id="qualification">
<h2>Qualification by accepted requirement</h2>
<table>
<thead>
<tr>
<th>Candidate / requirement</th>
<th>State / stage</th>
<th>Rule / support</th>
<th>Evidence / limitation</th>
</tr>
</thead>
<tbody>
{% for item in matrix %}<tr data-requirement-id="{{ item.requirement.id }}" data-status="{{ item.status }}">
<th scope="row">{{ item.candidate.name }}<br>{{ item.requirement.id }}<br>{{ item.requirement.label }}</th>
<td>{{ item.status }}<br>{{ item.stage }}</td>
<td>{{ item.requirement.observable }}
 · {{ item.requirement.operator }}
 {{ text(item.requirement.lower) }}
 / {{ text(item.requirement.upper) }}
 {{ item.requirement.unit }}

<br>Comparison support {{ text(item.scale) }}
 m · required support {{ text(item.requirement.minimum_support_scale_m) }}
 to {{ text(item.requirement.maximum_support_scale_m) }}
 m</td>
<td>{{ record(item.row) }}</td>
</tr>{% endfor %}</tbody>
</table>
<h3>GAP — not naturally reproduced on Earth</h3>
<ul>{% for q in data.qualifications if q.status == 'GAP' %}
<li>{{ q.requirement_id }}
 · {{ q.candidate_id }}
 · {{ q.explanation }}
</li>{% else %}
<li>No GAP row recorded</li>{% endfor %}
</ul>
<h3>UNKNOWN — insufficient evidence</h3>
<ul>{% for q in data.qualifications if q.status == 'UNKNOWN' %}
<li>{{ q.requirement_id }}
 · {{ q.candidate_id }}
 · {{ q.explanation }}
</li>{% else %}
<li>No UNKNOWN row recorded</li>{% endfor %}
</ul>
</section>
<section id="compatibility">
<h2>Rover compatibility</h2>{{ record(data.compatibility) }}{{ record(data.rover) }}
<p>Declared capabilities are not observed performance.
Preliminary assessments remain separate from verified route results.</p>
</section>
<section id="prove-it">
<h2>PROVE IT — complete attempt history</h2>
{% for attempt in data.attempts %}<article class="attempt" data-attempt-number="{{ attempt.attempt_number }}">
<h3>Attempt {{ attempt.attempt_number }}
 · {{ attempt.candidate_name }}
 · {{ attempt.result.outcome }}
</h3>{{ record(attempt) }}
</article>
{% else %}
<p>Not verified. {{ b.not_run_reason or 'No committed test attempts.' }}
</p>{% endfor %}
{{ record(data.search_limitations) }}
</section>
<section id="portfolio">
<h2>Composite portfolio</h2>{{ record(data.portfolio) }}
<p>Separate campaigns do not establish simultaneous co-located conditions.
Logistics, permissions and access require independent assessment.</p>
</section>
<section id="critic-limitations">
<h2>Critic and limitations</h2>{{ record(data.critiques) }}{{ record(data.passport.limitations) }}</section>
<section id="assurance">
<h2>Scientific assurance</h2>{{ record(data.assurance) }}</section>
<section id="next-steps">
<h2>Next steps</h2>{{ record(data.passport.next_steps) }}</section>
<section id="provenance">
<h2>Provenance appendix</h2>
<h3>Source locks</h3>{{ record(data.source_locks) }}<h3>Evidence records</h3>{{ record(data.evidence_appendix) }}
<h3>Passport references</h3>{{ record(data.passport) }}<p>Renderer 1.0.0 · Manifest SHA-256 {{ b.manifest_sha256 }}</p>
<p>The digest establishes content consistency, not scientific correctness or endorsement.</p>
</section>
</body>
</html>
"""


def render_html(bundle: PassportExportBundle, assets: list[ProvidedAsset]) -> bytes:
    qualified = any(a.result.outcome == "PASS" for a in bundle.attempts) and (
        bundle.assurance is not None and bundle.assurance.publication != "BLOCKED"
    )
    if qualified:
        headline = "Qualified for these tests under these assumptions:"
    elif bundle.not_run_reason:
        headline = bundle.not_run_reason
    elif bundle.attempts:
        latest = max(bundle.attempts, key=lambda a: a.attempt_number)
        headline = f"No supported recommendation under the accepted contract — {latest.result.outcome}"
    else:
        headline = "Not verified"
    data = bundle.model_dump(mode="json")
    rows = {(q.candidate_id, q.requirement_id): q for q in bundle.qualifications}
    matrix: list[dict[str, Any]] = []
    for candidate in bundle.candidates:
        for req in bundle.mission.requirements:
            row = rows.get((candidate.id, req.id))
            matrix.append(
                dict(
                    candidate=candidate,
                    requirement=req,
                    status=row.status if row else "PENDING",
                    stage=getattr(row, "evaluation_stage", "Not supplied by the frozen contract"),
                    scale=row.comparison_scale_m if row else None,
                    row=row.model_dump(mode="json") if row else {"reason": "Not assessed"},
                )
            )
    env = Environment(autoescape=True, undefined=StrictUndefined)
    template = env.from_string(TEMPLATE)
    return template.render(
        b=bundle,
        data=data,
        matrix=matrix,
        headline=headline,
        qualified=qualified,
        images=image_data_uris(assets),
        text=html_text,
        css=CSS,
    ).encode("utf-8")

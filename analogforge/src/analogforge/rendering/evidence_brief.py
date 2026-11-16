"""Offline current-evidence PDF layout. Receives authorized data, never database or network access."""

from __future__ import annotations

import base64
import io
import json
import math
import re
import resource
import sys
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import reportlab  # type: ignore[import-untyped]
from pypdf import PdfReader, PdfWriter
from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String  # type: ignore[import-untyped]
from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Table,
    TableStyle,
)

from analogforge.application.field_guidance import field_guidance

INK, MUTED, ACCENT = colors.HexColor("#17283A"), colors.HexColor("#48586A"), colors.HexColor("#126B78")
PALE, RULE = colors.HexColor("#EDF4F6"), colors.HexColor("#D7E0E7")
WIDTH = A4[0] - 88

CRITERIA = {
    'slope_band_area_fraction': 'Area in the accepted slope band',
    'slope_distribution_w1_deg': 'Target-to-Earth slope distribution difference',
    'unique_slope_exposure_m': 'Unique route distance on the required slopes',
    'completed_task_count': 'Completion of assigned science tasks',
    'final_battery_reserve_pct': 'Battery reserve at the required finish',
    'surface_temperature_min_k': 'Minimum surface temperature',
    'mineral_class_present': 'Mineral context', 'ground_clearance_m': 'Rover ground clearance',
    'planetary_gravity': 'Planetary gravity', 'planetary_atmosphere': 'Planetary atmosphere',
}


def criterion_name(requirement: dict[str, Any]) -> str:
    label = CRITERIA.get(str(requirement.get('observable') or ''), str(requirement['label']))
    if requirement.get('mandatory') is False and '(optional)' not in label.lower():
        label += ' (optional)'
    return label


def readable_state(state: str) -> str:
    return {'AWAITING_REVIEW': 'Evidence ready - choose the next test',
            'BUILDING_PASSPORT': 'Preparing the final report'}.get(state, state.replace('_', ' ').capitalize())


def readable_status(status: str) -> str:
    return {'PASS': 'Met', 'FAIL': 'Unmet', 'PARTIAL': 'Partly met', 'UNKNOWN': 'Needs evidence',
            'GAP': 'Earth limitation', 'INCONCLUSIVE': 'Inconclusive'}.get(
                status, status.replace('_', ' ').capitalize())


def readable_site(candidate: dict[str, Any]) -> str:
    name = candidate.get('name') or 'Earth location'
    if re.fullmatch(r'(?:Practice|Terrain) grid-r\d+c\d+', name, re.IGNORECASE):
        west, south, east, north = candidate['aoi']['bbox']
        return 'Earth site - ' + position([(west + east) / 2, (south + north) / 2])
    return name


def text(value: Any) -> str:
    if value is None:
        return "Unknown"
    return str(value).replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")


def aoi_text(aoi: dict[str, Any]) -> str:
    west, south, east, north = aoi["bbox"]
    return (f"{aoi['body']}\nWest {west} deg; south {south} deg\nEast {east} deg; north {north} deg\n"
            f"Latitude: {text(aoi.get('latitude_type'))}; longitude: {text(aoi.get('longitude_convention'))}")



def simple_quantity(value: Any, unit: str) -> str:
    """Reading aid only; the technical record retains the original units and precision."""
    if value is None:
        return "Unknown"
    if unit == "fraction":
        return f"{format(value * 100, '.4g')}% ({format(value, '.6g')} fraction)"
    readable = format(value, ".6g") if isinstance(value, (int, float)) and not isinstance(value, bool) else text(value)
    return f"{readable} {unit}".strip()


def accepted_rule(requirement: dict[str, Any]) -> str:
    unit = requirement.get("unit", "")
    lower, upper = requirement.get("lower"), requirement.get("upper")
    if requirement["operator"] == "LTE":
        rule = f"At most {simple_quantity(upper, unit)}"
    elif requirement["operator"] == "GTE":
        rule = f"At least {simple_quantity(lower, unit)}"
    elif requirement["operator"] == "BETWEEN":
        rule = f"Between {simple_quantity(lower, unit)} and {simple_quantity(upper, unit)}"
    elif requirement["operator"] == "EQUALS":
        rule = f"Equal to {simple_quantity(lower if lower is not None else upper, unit)}"
    elif requirement["operator"] == "PRESENT":
        rule = "The accepted feature must be present"
    elif requirement["operator"] == "NOT_NATURALLY_REPRODUCIBLE":
        rule = "This planetary condition cannot be naturally reproduced on Earth"
    else:
        rule = f"{requirement['operator']} {unit}".strip()
    band = (requirement.get("parameters") or {}).get("slope_band_deg")
    if isinstance(band, list) and len(band) == 2:
        rule += f"; slope band {band[0]} to {band[1]} deg"
    return rule


# ReportLab ships no type declarations.
class BriefDoc(SimpleDocTemplate):  # type: ignore[misc]
    """PDF sidebar bookmarks are the document's navigable section tabs."""

    def afterFlowable(self, flowable: Any) -> None:  # noqa: N802 - ReportLab hook
        if isinstance(flowable, Paragraph) and flowable.style.name in {"title", "section"}:
            key = f"section-{self.seq.nextf('outline')}"
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(flowable.getPlainText(), key,
                                     level=0 if flowable.style.name == "title" else 1, closed=False)


def position(point: list[float]) -> str:
    lon, lat = point
    return f"{abs(lat):.6f} deg {'N' if lat >= 0 else 'S'}, {abs(lon):.6f} deg {'E' if lon >= 0 else 'W'}"


def render(document: dict[str, Any], *, concise: bool = False) -> bytes:
    if "locations" in document:
        return render_packet(document)
    font_root = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("BriefSans", str(font_root / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("BriefSansBold", str(font_root / "VeraBd.ttf")))
    pdfmetrics.registerFontFamily("BriefSans", normal="BriefSans", bold="BriefSansBold",
                                  italic="BriefSans", boldItalic="BriefSansBold")
    styles = {
        "body": ParagraphStyle("body", fontName="BriefSans", fontSize=9, leading=13, textColor=INK,
                               spaceAfter=6, splitLongWords=True),
        "small": ParagraphStyle("small", fontName="BriefSans", fontSize=7.5, leading=10.5, textColor=MUTED,
                                spaceAfter=5, splitLongWords=True),
        "title": ParagraphStyle("title", fontName="BriefSansBold", fontSize=25, leading=30, textColor=INK,
                                spaceAfter=12, splitLongWords=True),
        "section": ParagraphStyle("section", fontName="BriefSansBold", fontSize=14, leading=19, textColor=ACCENT,
                                  spaceBefore=16, spaceAfter=8, keepWithNext=True),
        "label": ParagraphStyle("label", fontName="BriefSansBold", fontSize=10, leading=14, textColor=INK,
                                spaceBefore=10, spaceAfter=5, keepWithNext=True),
    }

    def p(value: Any, style: str = "body") -> Any:
        # Plain source strings cannot introduce markup, files, links or instructions into the renderer.
        return Paragraph(escape(text(value)).replace("\n", "<br/>"), styles[style])

    def table(rows: list[list[Any]], widths: list[float], *, header: bool = False) -> Any:
        result = Table([[p(cell, "small") for cell in row] for row in rows], colWidths=widths,
                       repeatRows=1 if header else 0, hAlign="LEFT", splitInRow=1)
        commands: list[Any] = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("LINEBELOW", (0, 0), (-1, -1), .5, RULE),
        ]
        if header:
            commands.extend([("BACKGROUND", (0, 0), (-1, 0), PALE),
                             ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT)])
        result.setStyle(TableStyle(commands))
        return result

    def numeric_plot(row: dict[str, Any], width: float = WIDTH) -> Any:
        measurement, requirement = row["measurement"], row["requirement"]
        value = measurement["value"]
        values = [float(value)] + [float(requirement[k]) for k in ("lower", "upper")
                                   if requirement.get(k) is not None]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Non-finite chart value")
        low, high = min(0.0, *values), max(0.0, *values)
        span = high - low or max(abs(high), 1.0)
        low, high = low - span * .08, high + span * .08

        def x(number: float) -> float:
            return float(18 + (number - low) / (high - low) * (width - 38))

        graphic = Drawing(width, 76)
        graphic.add(Line(18, 34, width - 20, 34, strokeColor=RULE, strokeWidth=2))
        for key in ("lower", "upper"):
            bound = requirement.get(key)
            if bound is not None:
                graphic.add(Line(x(bound), 23, x(bound), 47, strokeColor=MUTED, strokeDashArray=[3, 2]))
                graphic.add(String(x(bound), 10, format(bound, ".5g"), fontName="BriefSans", fontSize=7,
                                   fillColor=MUTED, textAnchor="middle"))
        graphic.add(Circle(x(value), 34, 4.5, fillColor=ACCENT, strokeColor=ACCENT))
        graphic.add(String(18, 61, f"Measured {format(value, '.6g')} {text(measurement['unit'])}",
                           fontName="BriefSansBold", fontSize=8, fillColor=INK))
        graphic.add(String(18, 0, "Point: registered measurement. Dashed markers: accepted bounds.",
                           fontName="BriefSans", fontSize=6, fillColor=MUTED))
        return graphic

    def site_plot(plan: dict[str, Any]) -> Any:
        """North-up coordinate schematic, not imagery or an invented field corridor."""
        west, south, east, north = plan["bbox"]
        cosine = math.cos(math.radians((south + north) / 2))
        scale = min((WIDTH - 64) / ((east - west) * cosine), 170 / (north - south))
        width, height = (east - west) * cosine * scale, (north - south) * scale
        x0, y0 = (WIDTH - width) / 2, 28

        def xy(point: list[float]) -> tuple[float, float]:
            return x0 + (point[0] - west) * cosine * scale, y0 + (point[1] - south) * scale

        graphic = Drawing(WIDTH, height + 70)
        graphic.add(Rect(x0, y0, width, height, fillColor=PALE, strokeColor=ACCENT))
        route = plan.get("route")
        if route:
            points = route["coordinates"]
            for start, finish in zip(points, points[1:], strict=False):
                a, b = xy(start), xy(finish)
                graphic.add(Line(*a, *b, strokeColor=ACCENT, strokeWidth=2))
            markers = [("Start / finish" if route["start"] == route["finish"] else "Start", route["start"])]
            if route["start"] != route["finish"]:
                markers.append(("Finish", route["finish"]))
            markers.extend((str(i + 1), item["position"]) for i, item in enumerate(route["checkpoints"]))
            for label, point in markers:
                x, y = xy(point)
                graphic.add(Circle(x, y, 3, fillColor=INK, strokeColor=colors.white))
                graphic.add(String(x + 6, y + 7, label, fontName="BriefSansBold", fontSize=7, fillColor=INK))
        else:
            x, y = xy(plan["center"])
            graphic.add(Circle(x, y, 3, fillColor=ACCENT, strokeColor=ACCENT))
        graphic.add(String(4, height + 47, "N up | WGS84 coordinate schematic | outline = assessed region",
                           fontName="BriefSans", fontSize=7, fillColor=MUTED))
        graphic.add(String(4, 7, "Line = computed raster route, when available. No field clearance is implied.",
                           fontName="BriefSans", fontSize=7, fillColor=MUTED))
        return graphic

    story: list[Any] = []
    run, mission, candidate = document["run"], document["mission"], document["candidate"]
    story.extend([p("CURRENT EVIDENCE BRIEF", "small"), p(candidate.get("name") or "Earth location", "title"),
                  p(mission.get("name") or "Accepted mission", "label"),
                  p("A location-specific view of committed evidence at the stated run revision. "
                    "This is not an assured or published Analog Passport. Missing work remains Unknown; "
                    "a completed process does not imply scientific success."),
                  table([["Run state / mode", f"{run['state']} / {run['mode']}"],
                         ["Run / snapshot revision", f"{run['run_id']} / {run['revision']}"],
                         ["Mission revision", f"Revision {text(mission['revision'])} / {mission['id']}\n"
                          f"SHA-256 {mission['content_sha256']}"],
                         ["Rover revision", (f"Revision {text(document['rover']['revision'])} / "
                          f"{document['rover']['id']}\nSHA-256 "
                          f"{document['rover']['content_sha256']}")
                          if document["rover"] else "Site-only; no rover pinned"],
                         ["Dataset lock", run.get("dataset_lock_id")]], [120, WIDTH - 120]),
                  p("Mission and location", "section"), p(mission.get("objective")),
                  table([["Planetary target", aoi_text(mission["target"])],
                         ["Earth location", aoi_text(candidate["aoi"])],
                         ["Location ID / origin", f"{candidate['id']}\n{candidate.get('origin', 'Unknown')}"],
                         ["Discovery / reference status", f"{candidate.get('discovery_method', 'Unknown')} / "
                          f"{candidate.get('novelty_status', 'Unknown')}"]], [120, WIDTH - 120]),
                  p("Search is regional: acquired source footprints and the configured search extent bound these "
                    "observations. This report does not establish global Earth coverage or a global optimum."),
                  p("Current criterion records", "section"),
                  p("Statuses below are the committed site records. Numeric plots require a compatible registered "
                    "comparison, exact accepted units/support, and this location's evidence lineage. "
                    "A recorded status may remain visible even when its numeric value cannot be verified.")])
    if document["run_reason"]:
        reason = document["run_reason"]
        story.insert(4, p(f"Run {run['state']}: {reason['code']}. {reason['message']}"))
    elif run["state"] in {"FAILED", "BLOCKED"}:
        story.insert(4, p("Terminal cause: Unknown. The saved terminal record has no supported public cause."))
    if document["search_scope"]:
        scope = document["search_scope"]
        scope_rows = [["Committed screening field", "Saved value"]]
        for key, value in scope.items():
            if key == "limitations":
                continue
            display = aoi_text(value) if key == "search_extent" and isinstance(value, dict) else text(value)
            scope_rows.append([key.replace("_", " "), display])
        story.insert(-2, table(scope_rows, [WIDTH * .3, WIDTH * .7], header=True))
        for limitation in scope.get("limitations", []):
            story.insert(-2, p(limitation, "small"))
    rows = [["Criterion", "Accepted operand", "Recorded value / support", "Status"]]
    for row in document["benchmarks"]["requirements"]:
        req, measured = row["requirement"], row["measurement"]
        operand = f"{req['operator']}\nlower {text(req.get('lower'))}\nupper {text(req.get('upper'))} {req['unit']}"
        value = "Unknown" if measured["value"] is None else (
            f"{text(measured['value'])} {measured['unit']}\n{measured['support_scale_m']} m support")
        rows.append([f"{req['id']}\n{req['label']}", operand, value, row["status"]])
    story.append(table(rows, [WIDTH * .31, WIDTH * .27, WIDTH * .28, WIDTH * .14], header=True))
    for row in document["benchmarks"]["requirements"]:
        criterion_start = len(story)
        req, measured = row["requirement"], row["measurement"]
        story.extend([p(f"{req['id']} - {req['label']} - {row['status']}", "label"),
                      p(row["explanation"]),
                      p(f"Mandatory: {req['mandatory']}; accepted weight: {req['weight']}; "
                        f"evidence scope: {req['evidence_scope']}; allowed support "
                        f"{text(req.get('minimum_support_scale_m'))} to "
                        f"{text(req.get('maximum_support_scale_m'))} m. "
                        f"Co-location group: {text(req.get('parameters', {}).get('co_location_group'))}.", "small"),
                      p("Acceptance note: " + req["acceptance_note"], "small"),
                      p("Accepted parameters: " + json.dumps(req.get("parameters", {}), ensure_ascii=False), "small")])
        if measured["value"] is None:
            story.append(p("No numeric plot: " + measured["reason"], "small"))
        story.append(p(f"Evidence support: {text(measured.get('support_scale_m'))} m. "
                       f"Critic: {text(row.get('critic_status'))}. "
                       f"Confidence: {text(row.get('confidence'))}.", "small"))
        for limitation in row.get("limitations") or []:
            story.append(p("Limitation: " + limitation, "small"))
        story.append(p(f"Qualification {text(row['qualification_id'])}; comparison "
                       f"{text(measured.get('comparison_evidence_id'))}; receipt "
                       f"{text(row.get('receipt_id'))}; attempt results "
                       f"{', '.join(row['test_result_ids']) or 'None'}", "small"))
        criterion = story[criterion_start:]
        del story[criterion_start:]
        story.extend(criterion)
    story.append(p("Registered terrain observations", "section"))
    for key, label in (("target_analysis", "Planetary target"), ("candidate_analysis", "Earth location")):
        analysis = document[key]
        heading_start = len(story) - 1 if key == "target_analysis" else len(story)
        story.append(p(label, "label"))
        if not analysis["available"]:
            story.append(p(analysis["reason"]))
            continue
        story.append(p(f"Summary evidence {analysis['evidence_id']}; receipt {analysis['receipt_id']}; "
                       f"SHA-256 {analysis['artifact_sha256']}", "small"))
        histogram = analysis.get("slope_histogram")
        if histogram:
            story.append(p(f"{histogram['metric_id'].replace('_', ' ')} distribution; "
                           f"{histogram['support_scale_m']} m support; valid area {histogram['valid_area_m2']} m2.",
                           "small"))
            hist_rows = [[f"Interval ({histogram['unit']})", "Fraction of valid area"]]
            for left, right, fraction in zip(histogram["edges"], histogram["edges"][1:],
                                             histogram["area_fraction"], strict=False):
                hist_rows.append([f"{text(left)} to {text(right)}", text(fraction)])
            if len(histogram["area_fraction"]) <= 20:
                chart = Drawing(WIDTH, 150)
                chart.add(Line(20, 30, WIDTH - 20, 30, strokeColor=RULE))
                count = len(histogram["area_fraction"])
                slot = (WIDTH - 45) / max(count, 1)
                for index, fraction in enumerate(histogram["area_fraction"]):
                    x0 = 25 + index * slot
                    chart.add(Rect(x0, 30, max(slot - 5, 1), fraction * 95,
                                   fillColor=ACCENT, strokeColor=None))
                    chart.add(String(x0 + (slot - 5) / 2, 18, str(index + 1), textAnchor="middle",
                                     fontName="BriefSans", fontSize=7, fillColor=MUTED))
                chart.add(String(20, 136, "Area fraction (0 to 1); interval numbers follow the table.",
                                 fontName="BriefSans", fontSize=8, fillColor=MUTED))
                story.append(chart)
            # Keep the subject, support and graph together, rather than starting a page with an unlabelled plot.
            heading_and_chart = story[heading_start:]
            del story[heading_start:]
            story.append(KeepTogether(heading_and_chart))
            story.append(table(hist_rows, [WIDTH * .5, WIDTH * .5], header=True))
        metric_rows = [["Registered metric", "Value / unit", "Support (m)"]]
        for metric in analysis["metrics"]:
            metric_rows.append([metric["metric_id"],
                                f"{text(metric.get('value'))} {text(metric.get('unit'))}",
                                text(metric.get("support_scale_m"))])
        if len(metric_rows) > 1:
            story.append(table(metric_rows, [WIDTH * .5, WIDTH * .3, WIDTH * .2], header=True))
        for limitation in analysis.get("limitations", []):
            story.append(p("Limitation: " + limitation, "small"))
        for dimension in analysis.get("unavailable_dimensions", []):
            story.append(p("Unavailable dimension: " + json.dumps(dimension, ensure_ascii=False), "small"))
    story.append(p("Registered site views", "section"))
    for note in document["display_notes"]:
        story.append(p(note, "small"))
    for asset in document["images"]:
        image_start = len(story)
        story.append(p(f"{asset['subject']} - {asset['kind']} ({asset['unit']}); "
                       f"{asset['support_scale_m']} m analysis support", "label"))
        image = Image(io.BytesIO(base64.b64decode(asset["png"], validate=True)))
        image._restrictSize(WIDTH, 140)
        story.append(image)
        story.append(p("Display pixels add no analysis resolution. Registered legend:", "small"))
        legend_rows = [["Display interval", "Lower bound", "Upper bound"]]
        for entry in asset["legend"]:
            legend_rows.append([entry["label"], text(entry.get("lower")), text(entry.get("upper"))])
        story.append(table(legend_rows, [WIDTH * .5, WIDTH * .25, WIDTH * .25], header=True))
        story.append(p(f"Manifest {asset['manifest_id']}; SHA-256 {asset['sha256']}; source evidence "
                       + ", ".join(asset["source_evidence_ids"]), "small"))
        image_with_caption = story[image_start:]
        del story[image_start:]
        story.append(KeepTogether(image_with_caption))
        story.extend(p(value, "small") for value in [*asset["attribution"], *asset["limitations"]])
    story.append(p("Route attempts at this location", "section"))
    if not document["attempts"]:
        story.append(p("No committed route verification result is pinned for this location. "
                       "Terrain observations do not establish rover traversability."))
    for attempt in document["attempts"]:
        story.append(p(f"{attempt['outcome']} / {text(attempt.get('failure_category'))}", "label"))
        story.append(p(f"Test {attempt['test_id']}; result {attempt['id']}; verified route "
                       f"{text(attempt.get('verified_route_sha256'))}", "small"))
        for limitation in attempt.get("limitations") or []:
            story.append(p(limitation, "small"))
    story.append(p("Technical terminology", "section"))
    story.append(table([
        ["Term", "Meaning in this brief"],
        ["Analog", "An Earth location assessed against specific planetary mission requirements. "
         "A useful terrain analog need not reproduce every planetary condition."],
        ["AOI / coordinate frame", "Area of interest. Its bounds, planetary body, latitude type and longitude "
         "convention identify where a measurement applies."],
        ["Comparison support", "The spatial scale at which registered measurements may be compared. "
         "Enlarging an image does not improve this analysis scale."],
        ["Slope distribution / Wasserstein-1", "A distribution describes the fraction of valid terrain in each "
         "slope interval. Wasserstein-1 measures the separation between two distributions in their stated units; "
         "it is not a success probability."],
        ["Qualification / critic", "A saved criterion verdict and its review state. A PASS is not physical rover "
         "validation, and it does not by itself authorize publication."],
        ["Evidence receipt / provenance", "A record connecting an operation to its inputs, outputs and hashes. "
         "These references support traceability; they do not create missing observations."],
        ["UNKNOWN / GAP", "Missing or unsupported evidence remains UNKNOWN. A GAP records a declared limit "
         "to what an Earth analog can reproduce. Neither means zero."],
    ], [WIDTH * .28, WIDTH * .72], header=True))
    story.append(p("Limits and provenance", "section"))
    for limitation in [*(candidate.get("limitations") or []), *document["search_limitations"]]:
        story.append(p(limitation))
    for assumption in mission.get("assumptions") or []:
        story.append(p("Accepted assumption (not measured evidence): " + text(assumption), "small"))
    story.extend([p(document["context_note"]), p("No source was acquired, simulation run, criterion qualified, "
                  "or scientific conclusion recomputed while creating this download. Later run revisions can "
                  "contain different evidence; this PDF identifies only the snapshot below.", "small"),
                  p("Private snapshot SHA-256: " + document["snapshot_sha256"], "small")])
    # One concise reading path, followed by the complete technical appendix.
    # This is presentation of pinned evidence; it neither ranks sites nor changes verdicts.
    requirements = document["benchmarks"]["requirements"]
    statuses = {status: sum(row["status"] == status for row in requirements)
                for status in ("PASS", "FAIL", "PARTIAL", "UNKNOWN", "GAP")}
    label = readable_site(candidate)
    plan = document["test_plan"]
    route = plan.get("route")
    state = readable_state(run["state"])
    counts = (f"{statuses['PASS']} met; {statuses['FAIL']} unmet; {statuses['PARTIAL']} partly met; "
              f"{statuses['UNKNOWN']} need evidence; {statuses['GAP']} Earth limitations")
    front = [p("CURRENT EVIDENCE BRIEF", "small"), p("Executive summary", "title"),
             p(label, "section"), p(mission.get("name") or "Accepted mission", "label"),
             p("This is a current evidence snapshot, not an assured or published Analog Passport. "
               "It identifies what to rehearse at this Earth location and which accepted criteria are supported."),
             table([["Investigation", state + " / " + run["mode"]],
                    ["Recorded criteria", counts],
                    ["Earth reference centre", position(plan["center"])],
                    ["Rover", document["rover"].get("name") if document["rover"]
                     else "No rover supplied - site evidence only"],
                    ["Planetary target", mission["target"]["body"]]], [125, WIDTH - 125]),
             p("What the results mean", "section"),
             p("Met means a saved measurement satisfies an accepted criterion. Unmet means it does not. "
               "Missing measurements remain unknown; natural Earth limitations remain separate. A dataset match "
               "does not establish hardware reliability or guarantee success on Mars or the Moon.")]
    if document["run_reason"]:
        front.append(p(document["run_reason"]["message"]))
    front.append(p("Next step: " + ("Inspect the stored route and checkpoints below, then survey and approve the "
                    "corridor before field execution." if route else
                    "Run the selected location’s rover model to establish a route when available. Without a "
                    "compatible recorded route, start and finish remain unestablished.")))
    if concise:
        front = [p("LOCATION / FIELD PLAN", "small"), p(label, "title"),
                 p(position(plan["center"]), "label"), p(counts),
                 p("Reference centre only. " + state + ". " + (document["rover"].get("name")
                   if document["rover"] else "No rover supplied") + ". " + mission["target"]["body"], "small")]
    if not concise:
        front.append(PageBreak())
    front.extend([p("Simplified overview", "section" if concise else "title"), p(mission.get("objective")),
                  p("Accepted benchmarks at this location", "section")])
    overview_rows = [["Test / accepted benchmark", "Recorded evidence", "Assessment"]]
    for row in requirements:
        req, measured = row["requirement"], row["measurement"]
        value = (simple_quantity(measured["value"], measured["unit"]) if measured["value"] is not None
                 else "Not established")
        support = f" at {text(measured.get('support_scale_m'))} m support" if measured["value"] is not None else ""
        overview_rows.append([f"{criterion_name(req)}\n{accepted_rule(req)}", value + support,
                              readable_status(row["status"])])
    front.append(table(overview_rows, [WIDTH * .49, WIDTH * .32, WIDTH * .19], header=True))
    if not concise:
        measured_rows = [row for row in requirements if row["measurement"]["value"] is not None]
        for index in range(0, len(measured_rows), 2):
            cells = [[p(criterion_name(row["requirement"]), "label"), numeric_plot(row, WIDTH / 2 - 14)]
                     for row in measured_rows[index:index + 2]]
            if len(cells) == 1:
                cells.append([])
            plots = Table([cells], colWidths=[WIDTH / 2, WIDTH / 2], hAlign="LEFT")
            plots.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                      ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                      ("RIGHTPADDING", (0, 0), (-1, -1), 14)]))
            front.append(plots)
    if concise:
        scope = document.get("search_scope") or {}
        front.extend([p("How this location was found", "section"),
                      p(f"Discovery: {candidate.get('discovery_method') or 'not recorded'}. "
                        f"Screened windows: {scope.get('screened_count', 'Unknown')}. "
                        "Accepted planetary and Earth terrain were compared at compatible support.", "small"),
                      p(aoi_text(candidate["aoi"]), "small"), p("Site reference: " + candidate["id"], "small")])
    else:
        front.extend([p("How this location was found", "section"),
                      p("Accepted planetary conditions were compared with registered Earth observations at compatible "
                        "support. The rows above show the recorded results; this is a regional search, "
                        "not a global optimum."),
                      table([["Discovery", candidate.get("discovery_method") or "Not recorded"],
                             ["Windows screened", (document.get("search_scope") or {}).get(
                                 "screened_count", "Unknown")],
                             ["Final Earth region", aoi_text(candidate["aoi"])],
                             ["Site reference", candidate["id"]]], [125, WIDTH - 125]),
                      p("Region centres and printed coordinates are references, not approved route starts. "
                        "Display digits do not establish survey accuracy.", "small"),
    ])
    front.extend([p("Location test plan", "section" if concise else "title"), p(plan["route_note"])])
    if route:
        front.extend([site_plot(plan),
                      table([["Start", position(route["start"])], ["Finish", position(route["finish"])],
                             ["Model outcome", readable_status(route["outcome"]) + " - raster feasibility only"],
                             ["Route analysis support", f"{route['support_scale_m']} m"]], [125, WIDTH - 125])])
        checkpoint_rows = [["Stop / coordinates", "Activity / capability", "Recorded design"]]
        for i, item in enumerate(route["checkpoints"]):
            checkpoint_rows.append([f"{i + 1}. {item['id']}\n{position(item['position'])}",
                                   f"{text(item['activity']).replace('_', ' ').capitalize()}\n"
                                   f"{item.get('capability') or 'No specific capability recorded'}",
                                   f"Dwell {item['dwell_s']} s; tolerance {item['tolerance_m']} m\n"
                                   f"Requirements: {', '.join(item['requirement_ids']) or 'None assigned'}"])
        if len(checkpoint_rows) > 1:
            front.append(table(checkpoint_rows, [WIDTH * .36, WIDTH * .32, WIDTH * .32], header=True))
        if not concise:
            front.append(p("Recorded route assumptions - not new accepted criteria", "label"))
            front.extend(p(item, "small") for item in route["assumptions"])
    else:
        front.append(table([["Start / finish: not established", "No compatible geographic route is recorded. "
                            "The assessed region is not a driving corridor. Compute and verify a route, then "
                            "survey and approve its endpoints before a field trial."]], [WIDTH * .34, WIDTH * .66]))
    front.append(p("What to test and how to perform it", "section"))
    for row in requirements:
        req = row["requirement"]
        if req["operator"] == "NOT_NATURALLY_REPRODUCIBLE" or (concise and not req["mandatory"]):
            continue
        guide = field_guidance(req)
        front.extend([p(criterion_name(req), "label"),
                      p(guide["focus"] + ". " + guide["method"]),
                      p("Benchmark: " + accepted_rule(req) + ". Current evidence: "
                        + readable_status(row["status"]), "small")])
        if not concise:
            front.append(p("Record: " + guide["record"], "small"))
    gaps = [criterion_name(row["requirement"]) for row in requirements
            if row["requirement"]["operator"] == "NOT_NATURALLY_REPRODUCIBLE"]
    if gaps:
        front.append(p("Separate planetary validation: " + "; ".join(gaps) +
                       ". These conditions cannot be passed by selecting a natural Earth location."))
    if route:
        checks = [["Modeled route rule", "Recorded value / margin", "Assessment"]]
        for item in route["benchmark_rows"]:
            checks.append([item["rule"], f"{text(item.get('measured'))} {text(item.get('unit'))}\n"
                           f"Margin {text(item.get('margin'))}", readable_status(item["status"])])
        if not concise:
            story.extend([p("Independent route checks", "section"),
                          table(checks, [WIDTH * .47, WIDTH * .34, WIDTH * .19], header=True)])
        front.append(p("Independent route checks: " + "; ".join(
            f"{readable_status(status)} {sum(item['status'] == status for item in route['benchmark_rows'])}"
            for status in dict.fromkeys(item["status"] for item in route["benchmark_rows"]))
            + ". Exact checks and margins remain in the individual technical appendix.", "small"))
    front.append(p("Before field execution", "section"))
    front.append(p("Confirm access and permits; survey hazards at rover scale; approve the route and recovery "
                   "plan; retain calibrated telemetry and task observations. " + plan["field_readiness"]))
    if not concise:
        story.append(p("Field execution checklist", "section"))
        story.extend(p(f"{index + 1}. {step}") for index, step in enumerate(plan["steps"]))
    front.extend([p("Earth testing reduces uncertainty; it does not assure planetary mission success. "
                    "Missing observations stay unknown. No simulation or new qualification occurs while rendering."),
                  p("AnalogForge - independent project; no NASA endorsement.", "small")])
    if concise:
        story = front
    else:
        story[:2] = [p("Technical details", "title")]
        story = front + [PageBreak()] + story
    output = io.BytesIO()
    doc = BriefDoc(output, pagesize=A4, rightMargin=44, leftMargin=44, topMargin=55, bottomMargin=48,
                            title="AnalogForge - Current evidence brief", author="AnalogForge", pageCompression=1)

    def page(canvas: Any, _doc: Any) -> None:
        if canvas.getPageNumber() > 40:
            raise ValueError("PDF page bound exceeded")
        canvas.saveState()
        canvas.setFont("BriefSansBold", 8)
        canvas.setFillColor(ACCENT)
        canvas.drawString(44, A4[1] - 31, "ANALOGFORGE  /  CURRENT EVIDENCE")
        canvas.setStrokeColor(RULE)
        canvas.line(44, A4[1] - 39, A4[0] - 44, A4[1] - 39)
        canvas.setFont("BriefSans", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(44, 28, f"Unassured snapshot {document['snapshot_sha256'][:12]} / {run['mode']}")
        canvas.drawRightString(A4[0] - 44, 28, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page, onLaterPages=page)
    result = output.getvalue()
    if len(result) > 8 * 1024 * 1024:
        raise ValueError("PDF byte bound exceeded")
    return result


def render_packet(document: dict[str, Any]) -> bytes:
    """One concise, bookmarked dossier; full audit appendices stay in the per-site downloads."""
    locations = document["locations"]
    if not 1 <= len(locations) <= 8:
        raise ValueError("Location count exceeds packet bound")
    parts = [render(location, concise=True) for location in locations]
    output = io.BytesIO()
    style = ParagraphStyle("index", fontName="BriefSans", fontSize=9, leading=13, textColor=INK, spaceAfter=8)
    title = ParagraphStyle("title", parent=style, fontName="BriefSansBold", fontSize=25, leading=31, spaceAfter=12)
    section = ParagraphStyle("section", parent=style, fontName="BriefSansBold", fontSize=14, leading=19,
                             textColor=ACCENT, spaceBefore=14, spaceAfter=9, keepWithNext=True)
    small = ParagraphStyle("matrix", parent=style, fontSize=7.5, leading=10.5, spaceAfter=4)

    def p(value: Any, selected: Any = style) -> Any:
        return Paragraph(escape(text(value)).replace("\n", "<br/>"), selected)

    def matrix(rows: list[list[Any]], widths: list[float]) -> Any:
        result = Table([[p(cell, small) for cell in row] for row in rows], colWidths=widths,
                       repeatRows=1, hAlign="LEFT", splitInRow=1)
        result.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PALE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT), ("LINEBELOW", (0, 1), (-1, -1), .5, RULE),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        return result

    story = [p("MISSION / EARTH REHEARSAL", small), p("Mission field test brief", title),
             p(locations[0]["mission"].get("name"), section),
             p("Executive summary: a separate location for each supported rehearsal. The directory below connects "
               "coordinates, test purpose, recorded benchmarks, and the next action. These are planning references, "
               "not approved driving instructions or a guarantee of planetary mission success."),
             p("Location directory - WGS84 reference centres", section)]
    rows = [["Location / reference centre", "What this site supports", "Saved criteria / next test"]]
    for index, location in enumerate(locations):
        requirements = location["benchmarks"]["requirements"]
        statuses = [row["status"] for row in requirements]
        supported = [criterion_name(row["requirement"]) + ": " + accepted_rule(row["requirement"])
                     + (" (partial evidence)" if row["status"] == "PARTIAL" else "")
                     for row in requirements if row["status"] in {"PASS", "PARTIAL"}]
        next_step = ("Inspect recorded route and checkpoints; survey before a field trial."
                     if location["test_plan"].get("route")
                     else "Compute a compatible rover route; endpoints not established.")
        rows.append([f"{index + 1}. {readable_site(location['candidate'])}\n"
                     + position(location["test_plan"]["center"]),
                     "\n".join(supported) or "No supported rehearsal established yet.",
                     f"{statuses.count('PASS')} met; {statuses.count('FAIL')} unmet; "
                     f"{statuses.count('PARTIAL')} partly met; {statuses.count('UNKNOWN')} need evidence; "
                     f"{statuses.count('GAP')} Earth limitations.\n"
                     + next_step])
    story.append(matrix(rows, [WIDTH * .29, WIDTH * .41, WIDTH * .30]))
    coverage = [["Mission benchmark", "Locations with a recorded match"]]
    for row in locations[0]["benchmarks"]["requirements"]:
        req = row["requirement"]
        matches = [str(index + 1) for index, location in enumerate(locations)
                   if any(item["requirement"]["id"] == req["id"] and item["status"] == "PASS"
                          for item in location["benchmarks"]["requirements"])]
        coverage.append([criterion_name(req) + "\n" + accepted_rule(req),
                         ", ".join("Location " + index for index in matches) or
                         ("Cannot be reproduced naturally on Earth" if req["operator"] == "NOT_NATURALLY_REPRODUCIBLE"
                          else "No matching evidence yet")])
    story.extend([p("Which location supports each benchmark", section),
                  matrix(coverage, [WIDTH * .65, WIDTH * .35]),
                  p("Use the PDF bookmarks for each site's exact region, route when available, and test instructions. "
                    "Unsuccessful candidates remain included. Full registered raster images, source receipts and "
                    "audit tables remain in the individual current-evidence PDFs.", small),
                  p(f"Run {document['run']['run_id']} / revision {document['run']['revision']}", small),
                  p("Combined snapshot SHA-256: " + document["snapshot_sha256"], small)])

    def cover_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(ACCENT)
        canvas.setFont("BriefSansBold", 8)
        canvas.drawString(44, A4[1] - 31, "ANALOGFORGE / MISSION FIELD BRIEF")
        canvas.setStrokeColor(RULE)
        canvas.line(44, A4[1] - 39, A4[0] - 44, A4[1] - 39)
        canvas.setFillColor(MUTED)
        canvas.setFont("BriefSans", 7)
        canvas.drawString(44, 28, "Current evidence - no NASA endorsement")
        canvas.drawRightString(A4[0] - 44, 28, f"Directory {doc.page}")
        canvas.restoreState()

    BriefDoc(output, pagesize=A4, leftMargin=44, rightMargin=44, topMargin=55, bottomMargin=48,
             title="AnalogForge - Mission field test brief").build(
                 story, onFirstPage=cover_page, onLaterPages=cover_page)
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(output.getvalue())), outline_item="Location directory")
    for index, (location, content) in enumerate(zip(locations, parts, strict=True)):
        writer.append(PdfReader(io.BytesIO(content)),
                      outline_item=f"{index + 1}. {readable_site(location['candidate'])}")
    # The dossier combines up to eight separately bounded site sections. Keep a
    # distinct total bound; one site's 40-page appendix limit is not a packet limit.
    if len(writer.pages) > 120:
        raise ValueError("Combined PDF page bound exceeded")
    writer.add_metadata({"/Title": "AnalogForge - Mission field test brief", "/Author": "AnalogForge"})
    result = io.BytesIO()
    writer.write(result)
    return result.getvalue()


def main() -> None:
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    source = sys.stdin.buffer.read(8 * 1024 * 1024 + 1)
    if len(source) > 8 * 1024 * 1024:
        raise ValueError("PDF input byte bound exceeded")
    sys.stdout.buffer.write(render(json.loads(source)))


if __name__ == "__main__":
    main()

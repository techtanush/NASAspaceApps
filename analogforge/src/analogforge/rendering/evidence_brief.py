"""Offline current-evidence PDF layout. Receives authorized data, never database or network access."""

from __future__ import annotations

import base64
import io
import json
import math
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

INK, MUTED, ACCENT = colors.HexColor("#17283A"), colors.HexColor("#48586A"), colors.HexColor("#126B78")
PALE, RULE = colors.HexColor("#EDF4F6"), colors.HexColor("#D7E0E7")
WIDTH = A4[0] - 88


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
        return f"At most {simple_quantity(upper, unit)}"
    if requirement["operator"] == "GTE":
        return f"At least {simple_quantity(lower, unit)}"
    if requirement["operator"] == "BETWEEN":
        return f"Between {simple_quantity(lower, unit)} and {simple_quantity(upper, unit)}"
    if requirement["operator"] == "EQUALS":
        return f"Equal to {simple_quantity(lower if lower is not None else upper, unit)}"
    if requirement["operator"] == "PRESENT":
        return "The accepted feature must be present"
    if requirement["operator"] == "NOT_NATURALLY_REPRODUCIBLE":
        return "This planetary condition cannot be naturally reproduced on Earth"
    return f"{requirement['operator']} {unit}".strip()


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
            ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LINEBELOW", (0, 0), (-1, -1), .5, RULE),
        ]
        if header:
            commands.extend([("BACKGROUND", (0, 0), (-1, 0), PALE),
                             ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT)])
        result.setStyle(TableStyle(commands))
        return result

    def numeric_plot(row: dict[str, Any]) -> Any:
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
            return float(18 + (number - low) / (high - low) * (WIDTH - 38))

        graphic = Drawing(WIDTH, 76)
        graphic.add(Line(18, 34, WIDTH - 20, 34, strokeColor=RULE, strokeWidth=2))
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
                           fontName="BriefSans", fontSize=7, fillColor=MUTED))
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
        if measured["value"] is not None:
            story.append(numeric_plot(row))
        else:
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
        story.append(KeepTogether(criterion))
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
        image._restrictSize(WIDTH, 260)
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
    # Plain-language presentation of the same pinned records precedes the complete technical evidence.
    # Counting saved verdicts here introduces no new qualification, ranking, threshold or scientific score.
    requirements = document["benchmarks"]["requirements"]
    statuses = {status: sum(row["status"] == status for row in requirements)
                for status in ("PASS", "FAIL", "UNKNOWN", "GAP")}
    front = [p("CURRENT EVIDENCE BRIEF", "small"),
             p("Executive summary", "title"),
             p(candidate.get("name") or "Earth location", "section"),
             p(mission.get("name") or "Accepted mission", "label"),
             p("This brief explains what this Earth location can be evaluated against, what the saved "
               "measurements show, and what still needs work. It is a current evidence snapshot, "
               "not an assured or published Analog Passport."),
             table([["Research workflow", f"{run['state']} / {run['mode']}"],
                    ["Mission criteria", f"{statuses['PASS']} PASS; {statuses['FAIL']} FAIL; "
                     f"{statuses['UNKNOWN']} UNKNOWN; {statuses['GAP']} GAP"],
                    ["Rover", document["rover"].get("name") if document["rover"]
                     else "No rover supplied - site evidence checks only"],
                    ["Planetary target", mission["target"]["body"]],
                    ["Research scope", "The acquired regional terrain and screened candidate windows"]],
                   [120, WIDTH - 120]),
             p("What this means", "section")]
    if document["run_reason"]:
        front.append(p(document["run_reason"]["message"]))
    elif run["state"] not in {"COMPLETED", "AWAITING_REVIEW"}:
        front.append(p(f"The investigation is {run['state'].lower().replace('_', ' ')}. "
                       "Its available evidence is retained; unfinished work remains Unknown."))
    front.append(p("PASS means the saved measurement meets an accepted mission criterion; FAIL means it "
                   "does not. These dataset comparisons are separate from the software research-workflow "
                   "status above. They do not establish physical rover performance or publication assurance."))
    for row in requirements:
        req = row["requirement"]
        measured = row["measurement"]
        measured_text = (f" Measured {simple_quantity(measured['value'], measured['unit'])} "
                         f"at {text(measured.get('support_scale_m'))} m support."
                         if measured["value"] is not None else " Measurement not established.")
        front.append(p(f"{row['status']} - {req['label']} "
                       f"({'required' if req['mandatory'] else 'optional'}). {accepted_rule(req)}."
                       + measured_text))
    front.extend([p("How to use this brief", "section"),
                  p("Use the next section to plan the location's tests and read the graphs. "
                    "Use Technical details for exact values, accepted parameters, methods and source records. "
                    "The same evidence and limitations apply throughout."),
                  p("AnalogForge is not a NASA product; no NASA endorsement is implied.", "small"),
                  PageBreak(), p("How this location was found", "title"),
                  p("01 / From mission to Earth evidence", "section"),
                  p("The accepted mission defines the conditions to match. Registered planetary and Earth "
                    "terrain observations are compared at compatible spatial support; the saved comparisons "
                    "below determine which criteria this location meets. No new search is performed for this PDF."),
                  table([["Target region", aoi_text(mission["target"])],
                         ["Discovery method", candidate.get("discovery_method") or "Not recorded"],
                         ["Dataset lock", run.get("dataset_lock_id")],
                         ["Windows screened", (document.get("search_scope") or {}).get("screened_count", "Unknown")],
                         ["Earth analysis support", str((document["candidate_analysis"].get("slope_histogram")
                          or {}).get("support_scale_m", "Unknown")) + " m"],
                         ["Target analysis support", str((document["target_analysis"].get("slope_histogram")
                          or {}).get("support_scale_m", "Unknown")) + " m"]], [140, WIDTH - 140]),
                  p("A criterion's exact measurement, units and accepted limit appear in Simplified overview. "
                    "This is a regional comparison, not a global optimum. A terrain comparison is not a "
                    "physical test of wheels, suspension, instruments or sampling equipment."),
                  p("02 / Final Earth location", "section"),
                  p(position(document["test_plan"]["center"]), "label"),
                  p("Region centre only - not a landing point, access point or approved route start."),
                  p("Coordinate digits are display precision, not survey accuracy; terrain support remains as stated.",
                    "small"),
                  table([["Assessed region", aoi_text(candidate["aoi"])],
                         ["Site identity", candidate["id"]]], [140, WIDTH - 140]),
                  PageBreak(), p("Location test plan", "title"),
                  p(candidate.get("name") or "Earth location", "section"),
                  p(document["test_plan"]["route_note"]), site_plot(document["test_plan"])])
    plan = document["test_plan"]
    route = plan.get("route")
    if route:
        front.extend([table([["Start", position(route["start"])], ["Finish", position(route["finish"])],
                            ["Model outcome", route["outcome"] + " - raster feasibility only"],
                            ["Route analysis cells", f"{route['support_scale_m']} m"]], [140, WIDTH - 140]),
                      p("Follow the numbered checkpoints in order only after the route is surveyed and approved. "
                        "A return to the same coordinate is a loop. Checkpoint coordinates do not establish material "
                        "presence or wheel-scale traversability."),
                      p("Checkpoints and activities", "label")])
        checkpoint_rows = [["Stop / coordinates", "Activity / capability", "Recorded design"]]
        for i, item in enumerate(route["checkpoints"]):
            checkpoint_rows.append([f"{i + 1}. {item['id']}\n{position(item['position'])}",
                f"{item['activity']}\n{item.get('capability') or 'No specific hardware capability recorded'}",
                f"Dwell {item['dwell_s']} s; tolerance {item['tolerance_m']} m\n"
                f"Origin {item['origin']}; requirements {', '.join(item['requirement_ids']) or 'None assigned'}"])
        if len(checkpoint_rows) > 1:
            front.append(table(checkpoint_rows, [WIDTH * .38, WIDTH * .27, WIDTH * .35], header=True))
        front.append(p("Recorded route assumptions - these are not additional accepted mission criteria", "label"))
        front.extend(p(item, "small") for item in route["assumptions"])
    else:
        front.append(p("Start / finish: not established. Select field endpoints after survey, then compute and "
                       "independently verify a route for this site. No neighbouring site's path is substituted."))
    front.extend([p("What to test and which benchmark applies", "section"),
                  p("Each row below retains the mission's own criterion. A subsystem-level physical acceptance "
                    "test must be separately specified when only regional terrain criteria were accepted.")])
    for row in requirements:
        req = row["requirement"]
        front.append(KeepTogether([p(f"{req['label']} ({req['id']})", "label"),
            table([["Test focus", f"{req.get('dimension', 'Unspecified')} / {req.get('observable', 'Unspecified')}"],
                   ["Benchmark to meet", accepted_rule(req)],
                   ["Current evidence", row["status"] + " - " + row["explanation"]],
                   ["Field task", "Measure the named observable with calibrated instruments at the accepted support. "
                    "For a terrain-only criterion, this checks site suitability; a drive cannot substitute for "
                    "the terrain comparison or establish hardware reliability."]], [140, WIDTH - 140])]))
    if route:
        front.append(p("Modeled route checks - separate from mission terrain criteria", "section"))
        checks = [["Recorded rule", "Measurement / margin", "Model status"]]
        for item in route["benchmark_rows"]:
            checks.append([item["rule"], f"{text(item.get('measured'))} {text(item.get('unit'))}\n"
                           f"Margin {text(item.get('margin'))}", item["status"]])
        front.append(table(checks, [WIDTH * .48, WIDTH * .35, WIDTH * .17], header=True))
    front.append(p("Field sequence and evidence to collect", "section"))
    front.extend(p(f"{index + 1}. {step}") for index, step in enumerate(plan["steps"]))
    front.extend([p(plan["field_readiness"], "label"),
                  p("Success here supports only the accepted, measured capability. Mars/Moon gravity, atmosphere, "
                    "temperature, dust and radiation need separate transfer analysis and validation. "
                    "No probability of mission success is estimated."),
                  PageBreak(), p("Simplified overview", "title"),
                  p("The mission", "section"), p(mission.get("objective")),
                  p("What to test at this location", "section")])
    for row in requirements:
        req, measured = row["requirement"], row["measurement"]
        block = [p(f"{req['label']} - {row['status']}", "label"), p(accepted_rule(req)),
                 p(row["explanation"])]
        if measured["value"] is not None:
            block.extend([p(f"Measured {simple_quantity(measured['value'], measured['unit'])}; "
                            f"compared at {text(measured.get('support_scale_m'))} m terrain support."),
                          numeric_plot(row)])
        else:
            block.append(p("Not yet established: " + measured["reason"]))
        front.append(KeepTogether(block))
    front.extend([p("Limits to keep in mind", "section"),
                  p("These are comparisons of the measured terrain covered by this investigation. "
                    "They do not establish a globally best Earth location or reproduce every planetary "
                    "condition. Graphs show registered measurements, not physical rover test results."),
                  p("No committed rover verification at this location." if not document["attempts"]
                    else f"{len(document['attempts'])} committed rover result(s) are recorded in Technical details."),
                  PageBreak()])
    story[:2] = [p("Technical details", "title")]
    story = front[:-1] if concise else front + story
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
    style = ParagraphStyle("index", fontName="BriefSans", fontSize=10, leading=15, textColor=INK)
    title = ParagraphStyle("index-title", parent=style, fontName="BriefSansBold", fontSize=25, leading=32)

    def p(value: Any) -> Any:
        return Paragraph(escape(text(value)).replace("\n", "<br/>"), style)

    story = [Paragraph("Mission field test brief", title), p(locations[0]["mission"].get("name")),
             p("All investigated Earth locations. Use the PDF bookmarks to open a site's methods, coordinates, "
               "test plan and benchmark graphs. These are planning references, not approved driving instructions."),
             p("Location directory - WGS84 reference centres")]
    for index, location in enumerate(locations):
        statuses = [row["status"] for row in location["benchmarks"]["requirements"]]
        story.extend([p(f"{index + 1}. {location['candidate'].get('name') or 'Earth location'}"),
                      p(position(location["test_plan"]["center"])),
                      p(f"{statuses.count('PASS')} criterion matches; {statuses.count('FAIL')} unmet; "
                        f"{statuses.count('UNKNOWN')} unknown. " + location["test_plan"]["route_note"])])
    story.extend([p("The directory includes unsuccessful candidates so a failed benchmark remains visible. "
                    "Full evidence receipts, registered raster images and technical terminology are available "
                    "in each location's current evidence PDF."),
                  p(f"Run {document['run']['run_id']} / revision {document['run']['revision']}"),
                  p("Combined snapshot SHA-256: " + document["snapshot_sha256"]),
                  p("AnalogForge - no NASA endorsement. Earth testing reduces uncertainty; it does not assure "
                    "Mars or Moon mission success.")])
    SimpleDocTemplate(output, pagesize=A4, leftMargin=44, rightMargin=44,
                      topMargin=55, bottomMargin=48, title="AnalogForge - Mission field test brief").build(story)
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(output.getvalue())), outline_item="Location directory")
    for index, (location, content) in enumerate(zip(locations, parts, strict=True)):
        writer.append(PdfReader(io.BytesIO(content)),
                      outline_item=f"{index + 1}. {location['candidate'].get('name') or 'Earth location'}")
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

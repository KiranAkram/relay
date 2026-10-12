"""Render an evaluation summary (built by run_evals) as Markdown and as one
self-contained HTML page. Pure functions; no external libraries in the page,
so it opens offline from evals/out/report.html."""

import html
from typing import Any

# (row label, how to show it): ("rate", numerator, denominator) or ("total", count)
CONFIG_ROWS: list[tuple[str, tuple[str, ...]]] = [
    ("Patients found", ("rate", "patients_found", "patients_expected")),
    ("Extra patient cards", ("total", "patients_extra")),
    ("Match status correct", ("rate", "match_correct", "patients_found")),
    ("Severity correct", ("rate", "severity_correct", "patients_found")),
    ("Contingency count correct", ("rate", "contingencies_correct", "patients_found")),
    ("Pending-result count correct", ("rate", "pending_correct", "patients_found")),
    ("Action items found", ("rate", "actions_found", "actions_expected")),
    ("Extra action items", ("total", "actions_extra")),
    ("Due time correct", ("rate", "due_correct", "actions_found")),
    ("Priority correct", ("rate", "priority_correct", "actions_found")),
    ("Text not in transcript", ("total", "hallucinations")),
    ("Duplicate cards", ("total", "duplicates")),
    ("Must-not breaches", ("total", "must_not_violations")),
    ("Failed model calls", ("total", "errors")),
]
SCRIPT_COLUMNS: list[tuple[str, tuple[str, ...]]] = [
    ("Patients found", ("rate", "patients_found", "patients_expected")),
    ("Extra cards", ("total", "patients_extra")),
    ("Actions found", ("rate", "actions_found", "actions_expected")),
    ("Extra actions", ("total", "actions_extra")),
    ("Due correct", ("rate", "due_correct", "actions_found")),
    ("Must-not", ("total", "must_not_violations")),
    ("Not in transcript", ("total", "hallucinations")),
]


def render_markdown(summary: dict[str, Any]) -> str:
    configs = summary["configurations"]
    lines = [
        "# Extraction evaluation",
        "",
        f"{summary['generated_at']} · provider {summary['provider']} · "
        f"{len(summary['cases'])} cases × {summary['repeat']} repeats",
        "",
        "## Configurations",
        "",
        _md_row(["Metric", *(c["name"] for c in configs)]),
        _md_row(["---"] * (len(configs) + 1)),
    ]
    for label, cells in _config_table(configs):
        lines.append(_md_row([label, *cells]))
    if configs:
        first = configs[0]
        lines += [
            "",
            f"## Per script ({first['name']})",
            "",
            _md_row(["Script", "Runs passed", *(c for c, _ in SCRIPT_COLUMNS)]),
            _md_row(["---"] * (len(SCRIPT_COLUMNS) + 2)),
        ]
        for name, case in first["cases"].items():
            agg = case["aggregate"]
            lines.append(
                _md_row(
                    [
                        name,
                        f"{agg['passed']}/{agg['runs']}",
                        *(_cell(agg["counts"], spec) for _, spec in SCRIPT_COLUMNS),
                    ]
                )
            )
    return "\n".join(lines) + "\n"


def render_html(summary: dict[str, Any], transcripts: dict[str, str]) -> str:
    configs = summary["configurations"]
    head = "".join(f"<th>{_e(c['name'])}</th>" for c in configs)
    config_rows = "".join(
        f"<tr><th scope=row>{_e(label)}</th>"
        + "".join(f"<td>{_e(cell)}</td>" for cell in cells)
        + "</tr>"
        for label, cells in _config_table(configs)
    )

    grid_rows = []
    for name in summary["cases"]:
        cells = []
        for c in configs:
            agg = c["cases"][name]["aggregate"]
            tone = _tone(agg["passed"], agg["runs"])
            cells.append(
                f'<td class="{tone}"><a href="#{_anchor(c["name"], name)}">'
                f"{agg['passed']}/{agg['runs']}</a></td>"
            )
        grid_rows.append(f"<tr><th scope=row>{_e(name)}</th>{''.join(cells)}</tr>")

    details = []
    for c in configs:
        for name, case in c["cases"].items():
            agg = case["aggregate"]
            runs = "".join(
                f"<li><b>Run {run['run']}: {'pass' if run['passed'] else 'fail'}</b>"
                + (
                    "<ul>"
                    + "".join(f"<li>{_e(d)}</li>" for d in run["diffs"])
                    + "</ul>"
                    if run["diffs"]
                    else ""
                )
                + "</li>"
                for run in case["runs"]
            )
            details.append(
                f'<details id="{_anchor(c["name"], name)}" class="case">'
                f"<summary>{_e(name)} · {_e(c['name'])} · "
                f"{agg['passed']}/{agg['runs']} passed</summary>"
                f"<ul class=runs>{runs}</ul>"
                f"<details class=transcript><summary>Transcript</summary>"
                f"<pre>{_e(transcripts.get(name, ''))}</pre></details></details>"
            )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Extraction evaluation</title>
<style>
:root {{ --bg: #fff; --fg: #1a1a1a; --muted: #666; --line: #ddd;
  --pass: #d8f0dc; --some: #fbecc4; --fail: #f7d4d0; --link: #0b5cad; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #16181b; --fg: #e8e8e8; --muted: #9a9a9a; --line: #33363b;
    --pass: #1f4a2a; --some: #574416; --fail: #5c2421; --link: #7fb6f0; }}
}}
body {{ margin: 0 auto; max-width: 1100px; padding: 24px 16px; background: var(--bg);
  color: var(--fg); font: 14px/1.5 system-ui, sans-serif; }}
h1 {{ margin: 0 0 4px; font-size: 22px; }}
h2 {{ margin: 32px 0 8px; font-size: 17px; }}
.meta {{ color: var(--muted); margin: 0; }}
.scroll {{ overflow-x: auto; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid var(--line); padding: 6px 10px; text-align: left;
  white-space: nowrap; }}
td {{ font-variant-numeric: tabular-nums; }}
td.pass {{ background: var(--pass); }} td.some {{ background: var(--some); }}
td.fail {{ background: var(--fail); }}
a {{ color: var(--link); }}
details.case {{ border: 1px solid var(--line); border-radius: 6px; padding: 8px 12px;
  margin: 8px 0; }}
details.case > summary {{ cursor: pointer; font-weight: 600; }}
details.case:target {{ outline: 2px solid var(--link); }}
ul.runs {{ padding-left: 18px; }}
pre {{ white-space: pre-wrap; color: var(--muted); }}
</style>
</head>
<body>
<h1>Extraction evaluation</h1>
<p class="meta">{_e(summary["generated_at"])} · provider {_e(summary["provider"])} ·
{len(summary["cases"])} cases × {summary["repeat"]} repeats.
A run passes only when every count is perfect.</p>
<h2>Configurations</h2>
<div class="scroll"><table><thead><tr><th>Metric</th>{head}</tr></thead>
<tbody>{config_rows}</tbody></table></div>
<h2>Runs passed per script</h2>
<p class="meta">Click a cell for the differences of each run.</p>
<div class="scroll"><table><thead><tr><th>Script</th>{head}</tr></thead>
<tbody>{"".join(grid_rows)}</tbody></table></div>
<h2>Details</h2>
{"".join(details)}
</body>
</html>
"""


def _config_table(configs: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = [
        (
            "Runs passed",
            [
                _fraction(c["aggregate"]["passed"], c["aggregate"]["runs"])
                for c in configs
            ],
        ),
        (
            "Cases with the same result every repeat",
            [
                f"{c['aggregate']['consistent_cases']}/{c['aggregate']['cases']}"
                for c in configs
            ],
        ),
        ("Pass rate spread across repeats", [_spread(c["aggregate"]) for c in configs]),
    ]
    rows += [
        (label, [_cell(c["aggregate"]["counts"], spec) for c in configs])
        for label, spec in CONFIG_ROWS
    ]
    return rows


def _cell(counts: dict[str, int], spec: tuple[str, ...]) -> str:
    if spec[0] == "rate":
        return _fraction(counts[spec[1]], counts[spec[2]])
    return str(counts[spec[1]])


def _fraction(num: int, den: int) -> str:
    return f"{num}/{den} ({100 * num / den:.0f}%)" if den else "–"


def _spread(agg: dict[str, Any]) -> str:
    spread = agg["pass_rate_spread"]
    if not spread:
        return "–"
    low, high = spread
    return f"{100 * low:.0f}%–{100 * high:.0f}%"


def _tone(passed: int, runs: int) -> str:
    if runs and passed == runs:
        return "pass"
    return "some" if passed else "fail"


def _anchor(config: str, case: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in f"{config}--{case}")


def _md_row(cells: list[str]) -> str:
    return "| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |"


def _e(text: object) -> str:
    return html.escape(str(text))

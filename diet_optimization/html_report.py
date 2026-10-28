"""Conversão simples do relatório Markdown em HTML autocontido."""

from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
from pathlib import Path


def _inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        text,
    )
    text = text.replace("−", "&minus;")
    return text


def _table_html(rows: list[str]) -> str:
    if len(rows) < 2:
        return ""
    header = [cell.strip() for cell in rows[0].strip().strip("|").split("|")]
    separator = [cell.strip() for cell in rows[1].strip().strip("|").split("|")]
    aligns = []
    for cell in separator:
        if cell.endswith(":") and cell.startswith(":"):
            aligns.append("center")
        elif cell.endswith(":"):
            aligns.append("right")
        else:
            aligns.append("left")
    body_rows = rows[2:]
    out = ["<table>", "<thead><tr>"]
    for idx, cell in enumerate(header):
        align = aligns[idx] if idx < len(aligns) else "left"
        out.append(f'<th style="text-align:{align}">{_inline(cell)}</th>')
    out.append("</tr></thead><tbody>")
    for row in body_rows:
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        out.append("<tr>")
        for idx, cell in enumerate(cells):
            align = aligns[idx] if idx < len(aligns) else "left"
            out.append(f'<td style="text-align:{align}">{_inline(cell)}</td>')
        out.append("</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


def _anchor(title: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")


def markdown_to_html(markdown: str, title: str = "Relatório") -> str:  # noqa: C901
    lines = markdown.splitlines()
    body: list[str] = []
    in_code = False
    code_buffer: list[str] = []
    table_buffer: list[str] = []
    list_type: str | None = None

    def flush_table() -> None:
        nonlocal table_buffer
        if table_buffer:
            body.append(_table_html(table_buffer))
            table_buffer = []

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            body.append(f"</{list_type}>")
            list_type = None

    for line in lines:
        if line.startswith("```"):
            flush_table()
            close_list()
            if in_code:
                body.append("<pre><code>" + html.escape("\n".join(code_buffer)) + "</code></pre>")
                code_buffer = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buffer.append(line)
            continue

        if line.startswith("|"):
            close_list()
            table_buffer.append(line)
            continue
        flush_table()

        stripped = line.strip()
        if not stripped:
            close_list()
            continue

        if stripped.startswith("#"):
            close_list()
            level = len(stripped) - len(stripped.lstrip("#"))
            title_text = stripped[level:].strip()
            body.append(f'<h{level} id="{_anchor(title_text)}">{_inline(title_text)}</h{level}>')
            continue

        image_match = re.match(r"!\[([^\]]*)\]\(([^\)]+)\)", stripped)
        if image_match:
            close_list()
            alt, src = image_match.groups()
            body.append(
                f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}">'
                f"<figcaption>{_inline(alt)}</figcaption></figure>"
            )
            continue

        if stripped.startswith("> "):
            close_list()
            body.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if bullet or numbered:
            desired = "ul" if bullet else "ol"
            if list_type != desired:
                close_list()
                body.append(f"<{desired}>")
                list_type = desired
            content = bullet.group(1) if bullet else numbered.group(1)
            body.append(f"<li>{_inline(content)}</li>")
            continue

        if stripped == "---":
            close_list()
            body.append("<hr>")
            continue

        close_list()
        body.append(f"<p>{_inline(stripped)}</p>")

    flush_table()
    close_list()
    if in_code and code_buffer:
        body.append("<pre><code>" + html.escape("\n".join(code_buffer)) + "</code></pre>")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ --ink:#1d2733; --muted:#5b6775; --accent:#1f8a70; --line:#d9e0e7; --bg:#f7f9fb; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font-family: "Segoe UI", "DejaVu Sans", Arial, sans-serif;
         line-height:1.55; font-size:15px; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 42px 34px 70px; background:white;
          box-shadow: 0 8px 30px rgba(20,40,60,.08); }}
  h1 {{ font-size: 30px; line-height:1.2; margin: 0 0 8px; color:#123c33; }}
  h2 {{ font-size: 23px; margin: 38px 0 12px; padding-bottom:6px; border-bottom:2px solid var(--line); color:#123c33; }}
  h3 {{ font-size: 18px; margin: 26px 0 10px; color:#1f5f52; }}
  h4 {{ font-size: 16px; margin: 20px 0 8px; }}
  p {{ margin: 10px 0; }}
  strong {{ color:#102a24; }}
  a {{ color:#1f6f9f; }}
  code {{ background:#eef3f6; padding:1px 4px; border-radius:4px; font-size:.92em; }}
  pre {{ background:#102a24; color:#e8f5f0; padding:14px 16px; border-radius:8px; overflow-x:auto; }}
  pre code {{ background:none; color:inherit; padding:0; }}
  ul, ol {{ margin: 8px 0 8px 22px; padding:0; }}
  li {{ margin: 4px 0; }}
  blockquote {{ margin: 16px 0; padding: 12px 16px; border-left:4px solid var(--accent);
                background:#f1f8f5; color:#25443b; border-radius:0 6px 6px 0; }}
  table {{ width:100%; border-collapse:collapse; margin: 14px 0 20px; font-size:13.5px; }}
  th {{ background:#eaf3f0; color:#123c33; font-weight:600; padding:8px 9px; border-bottom:2px solid #c9ddd7; }}
  td {{ padding:7px 9px; border-bottom:1px solid var(--line); vertical-align:top; }}
  tbody tr:nth-child(even) td {{ background:#f8fbfa; }}
  figure {{ margin: 18px 0 24px; text-align:center; }}
  figure img {{ max-width:100%; height:auto; border:1px solid var(--line); border-radius:8px; background:white; }}
  figcaption {{ color:var(--muted); font-size:12.5px; margin-top:6px; }}
  hr {{ border:0; border-top:1px solid var(--line); margin: 26px 0; }}
  nav.toc {{ position: fixed; top: 24px; left: 24px; width: 230px; max-height: 90vh; overflow:auto;
             background:white; border:1px solid var(--line); border-radius:10px; padding:14px 16px;
             box-shadow:0 6px 20px rgba(20,40,60,.08); font-size:12.5px; }}
  nav.toc h2 {{ font-size:14px; margin:0 0 8px; border:0; padding:0; }}
  nav.toc ul {{ list-style:none; margin:0; padding:0; }}
  nav.toc li {{ margin:4px 0; }}
  nav.toc a {{ text-decoration:none; color:#345; }}
  nav.toc a:hover {{ color:var(--accent); }}
  @media (max-width: 1450px) {{ nav.toc {{ display:none; }} }}
  @media print {{ body {{ background:white; }} main {{ box-shadow:none; padding:0; }} nav.toc {{ display:none; }} }}
</style>
</head>
<body>
<nav class="toc"><h2>Sumário</h2>{_toc_inner(markdown)}</nav>
<main>
{chr(10).join(body)}
</main>
</body>
</html>
"""


def _toc_inner(markdown: str) -> str:
    items = []
    for line in markdown.splitlines():
        if line.startswith("## "):
            title = line[3:].strip()
            items.append(f'<li><a href="#{_anchor(title)}">{_inline(title)}</a></li>')
    return "<ul>" + "".join(items) + "</ul>" if items else ""


def write_html_report(markdown_path: str | Path, output_path: str | Path | None = None) -> Path:
    markdown_path = Path(markdown_path)
    markdown = markdown_path.read_text(encoding="utf-8")
    output = Path(output_path) if output_path is not None else markdown_path.with_suffix(".html")
    output.write_text(markdown_to_html(markdown, title=markdown.splitlines()[0].lstrip("# ")), encoding="utf-8")
    return output


def write_pdf_report(html_path: str | Path, output_path: str | Path | None = None) -> Path | None:
    """Tenta gerar um PDF a partir do HTML usando Edge/Chrome headless.

    É uma etapa opcional: se nenhum navegador compatível estiver instalado, a
    função retorna None sem interromper a análise.
    """
    html_path = Path(html_path).resolve()
    pdf_path = Path(output_path) if output_path is not None else html_path.with_suffix(".pdf")
    candidates = [
        os.environ.get("EDGE_PATH"),
        os.environ.get("CHROME_PATH"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("msedge"),
        shutil.which("google-chrome"),
        shutil.which("chrome"),
        shutil.which("chromium"),
    ]
    for browser in candidates:
        if not browser or not Path(browser).exists():
            continue
        try:
            subprocess.run(
                [
                    browser,
                    "--headless=new",
                    "--disable-gpu",
                    "--no-sandbox",
                    f"--print-to-pdf={pdf_path}",
                    "--no-pdf-header-footer",
                    html_path.as_uri(),
                ],
                check=False,
                timeout=120,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if pdf_path.exists() and pdf_path.stat().st_size > 0:
            return pdf_path
    return None

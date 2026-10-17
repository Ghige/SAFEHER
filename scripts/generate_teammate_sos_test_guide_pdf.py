"""Generate docs/SafeHer_Teammate_Setup_and_SOS_Test_Guide.pdf from Markdown."""
from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
MD = ROOT / "docs" / "SafeHer_Teammate_Setup_and_SOS_Test_Guide.md"
OUT = ROOT / "docs" / "SafeHer_Teammate_Setup_and_SOS_Test_Guide.pdf"


def ascii_safe(text: str) -> str:
    replacements = {
        "\u2014": "--",
        "\u2013": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u00a0": " ",
        "\u2192": "->",
        "\u2713": "[x]",
        "\u2610": "[ ]",
        "\u2611": "[x]",
        "\u2264": "<=",
        "\u2265": ">=",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def strip_md_inline(text: str) -> str:
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return ascii_safe(text.strip())


class GuidePDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 40, 70)
        self.cell(
            0,
            7,
            "SafeHer - Teammate Setup and SOS/UI Test Guide",
            align="L",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_draw_color(200, 160, 170)
        y = self.get_y()
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.set_xy(self.l_margin, y + 5)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            8,
            ascii_safe(
                f"Page {self.page_no()}/{{nb}}  |  No secrets  |  "
                "sos-ui-teammate-share c3bb710  |  https://github.com/Ghige/SAFEHER"
            ),
            align="C",
        )

    def h1(self, text: str):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(90, 20, 50)
        self.multi_cell(0, 7, ascii_safe(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h2(self, text: str):
        self.ln(2)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(110, 30, 60)
        self.multi_cell(0, 6.5, ascii_safe(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def h3(self, text: str):
        self.ln(1)
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(80, 50, 70)
        self.multi_cell(0, 6, ascii_safe(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.5)

    def body(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.2, ascii_safe(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.6)

    def bullet(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5.2, ascii_safe(f"- {text}"), new_x="LMARGIN", new_y="NEXT")

    def code(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Courier", "", 8)
        self.set_text_color(20, 20, 20)
        self.set_fill_color(245, 240, 242)
        wrapped = []
        for raw_line in ascii_safe(text).splitlines() or [" "]:
            while len(raw_line) > 92:
                wrapped.append(raw_line[:92])
                raw_line = raw_line[92:]
            wrapped.append(raw_line if raw_line else " ")
        self.multi_cell(0, 4.4, "\n".join(wrapped), fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def warn(self, text: str):
        self.set_x(self.l_margin)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(140, 40, 20)
        self.multi_cell(0, 5.2, ascii_safe(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)


def parse_table_row(line: str) -> list[str]:
    return [p.strip() for p in line.strip().strip("|").split("|")]


def render_markdown(pdf: GuidePDF, md: str) -> None:
    lines = md.splitlines()
    i = 0
    in_code = False
    code_buf: list[str] = []
    skipped_title = False

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()

        if line.startswith("```"):
            if in_code:
                pdf.code("\n".join(code_buf) if code_buf else " ")
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if not skipped_title and line.startswith("# "):
            skipped_title = True
            i += 1
            continue

        if line.startswith("#### "):
            pdf.h3(strip_md_inline(line[5:]))
            i += 1
            continue
        if line.startswith("### "):
            pdf.h3(strip_md_inline(line[4:]))
            i += 1
            continue
        if line.startswith("## "):
            pdf.h2(strip_md_inline(line[3:]))
            i += 1
            continue
        if line.startswith("# "):
            pdf.h1(strip_md_inline(line[2:]))
            i += 1
            continue

        if line.startswith("|") and i + 1 < len(lines) and set(lines[i + 1].replace("|", "").strip()) <= set("-: "):
            headers = parse_table_row(line)
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(parse_table_row(lines[i]))
                i += 1
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(30, 30, 30)
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(
                0,
                5,
                ascii_safe("Table: " + " / ".join(strip_md_inline(h) for h in headers if h)),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.set_font("Helvetica", "", 9)
            for row in rows:
                cells = [(row[j] if j < len(row) else "") for j in range(len(headers))]
                parts = []
                for h, c in zip(headers, cells):
                    hv = strip_md_inline(h)
                    cv = strip_md_inline(c)
                    if hv or cv:
                        parts.append(f"{hv}: {cv}" if len(headers) > 3 else cv)
                out = " -- ".join(parts) if len(headers) > 3 else " | ".join(strip_md_inline(c) for c in cells)
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(0, 4.8, ascii_safe(out), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
            continue

        if line.startswith("---"):
            i += 1
            continue

        if line.startswith("- [ ] ") or line.startswith("- [x] ") or line.startswith("- [X] "):
            pdf.bullet(strip_md_inline(line[6:]))
            i += 1
            continue

        if line.startswith("- "):
            pdf.bullet(strip_md_inline(line[2:]))
            i += 1
            continue

        if line.startswith("|"):
            pdf.body(strip_md_inline(line))
            i += 1
            continue

        if not line.strip():
            pdf.ln(1)
            i += 1
            continue

        pdf.body(strip_md_inline(line))
        i += 1


def title_page(pdf: GuidePDF) -> None:
    pdf.add_page()
    pdf.set_xy(pdf.l_margin, 36)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(90, 20, 50)
    pdf.multi_cell(0, 14, "SafeHer", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(
        0,
        9,
        "Teammate Setup and SOS/UI Test Guide",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)
    pdf.set_draw_color(180, 80, 110)
    pdf.set_line_width(0.6)
    y = pdf.get_y()
    pdf.line(50, y, 160, y)
    pdf.set_xy(pdf.l_margin, y + 10)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(40, 40, 40)
    pdf.multi_cell(
        0,
        7,
        ascii_safe(
            "Download the isolated SOS/UI branch, configure a debug build,\n"
            "install it on a physical Android phone, and record all 13 test cases."
        ),
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, "Repository: https://github.com/Ghige/SAFEHER", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(0, 6, "Branch: sos-ui-teammate-share", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(
        0,
        6,
        "Commit: c3bb710c8bf5dda90c0b5c2bb9ecfdd83a285679",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.multi_cell(0, 6, "Document date: 2026-10-10", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(140, 40, 20)
    pdf.multi_cell(0, 6, "NO SECRETS IN THIS DOCUMENT", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.multi_cell(
        0,
        6,
        "DO NOT SEND A REAL EMERGENCY DURING TESTING",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(70, 70, 70)
    pdf.ln(6)
    pdf.multi_cell(
        0,
        5.5,
        ascii_safe(
            "These are behaviors to test. They are not claimed as verified on a physical device.\n"
            "Unit tests do not make this stage production-ready.\n"
            "Do not commit .env, local.properties, google-services.json, or keystores.\n"
            "If you already have a dirty local clone, use a separate clean clone."
        ),
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )


def build() -> None:
    if not MD.exists():
        raise SystemExit(f"Missing {MD}")
    md = MD.read_text(encoding="utf-8")
    pdf = GuidePDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_left_margin(14)
    pdf.set_right_margin(14)
    title_page(pdf)
    pdf.add_page()
    render_markdown(pdf, md)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(f"Wrote {OUT}")
    print(f"pages={pdf.page_no()}")


if __name__ == "__main__":
    build()

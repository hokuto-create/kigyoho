import html, subprocess, pathlib, shutil

import csv
BASE = pathlib.Path(__file__).parent

def load():
    rows = []
    with open(BASE / "questions.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["type"] in ("h1", "h2"):
                rows.append((r["type"], r["question"]))
            else:
                rows.append((r["no"], r["page"], r["question"], r["answer"]))
    return rows

CSS = """
@page { size: A4; margin: 14mm 12mm 14mm 12mm;
  @bottom-center { content: counter(page); } }
body { font-family: 'Noto Sans CJK JP'; font-size: 10.5pt; color: #222; }
h1.title { font-size: 17pt; margin: 0 0 2mm; letter-spacing: .05em; }
.sub { font-size: 9pt; color: #777; margin-bottom: 5mm; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
thead th { background: #2f4a6d; color: #fff; font-weight: 500; font-size: 9pt;
  padding: 2mm 1.5mm; }
td { border-bottom: .3mm solid #c8ced6; padding: 2.2mm 1.5mm; vertical-align: top; }
tr { break-inside: avoid; }
td.no { text-align: right; font-weight: 700; color: #2f4a6d; }
td.pg { color: #888; font-size: 9pt; }
td.ans { border-left: .3mm dashed #c8ced6; color: #c0392b; height: 13mm; font-size: 9pt; line-height: 1.55; }
td.ans b { color: #a31515; }
td.chk { text-align: center; white-space: nowrap; }
.box { display: inline-block; width: 4mm; height: 4mm; border: .3mm solid #888;
  margin: 0 .6mm; border-radius: .6mm; }
tr.h1 td { background: #e8edf3; font-weight: 700; font-size: 12pt;
  color: #2f4a6d; padding: 2mm 2mm; border-bottom: none; }
tr.h2 td { font-weight: 700; color: #2f4a6d; padding: 3mm 2mm 1.5mm;
  border-bottom: .5mm solid #2f4a6d; }
"""

def render(with_answers=True):
    rows = []
    for r in load():
        if r[0] in ("h1", "h2"):
            rows.append(f'<tr class="{r[0]}"><td colspan="5">{html.escape(r[1])}</td></tr>')
        else:
            n, pg, q, a = r
            ans = a if with_answers else ""
            rows.append(
                f'<tr><td class="chk"><span class="box"></span><span class="box"></span><span class="box"></span></td><td class="no">{n}</td><td class="pg">{pg}</td>'
                f'<td>{html.escape(q)}</td><td class="ans">{ans}</td>'
                '</tr>')
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<h1 class="title">企業法　一問一答</h1>
<div class="sub">答えは右列。隠して解き、間違えたら□に印。3回連続正解で卒業。</div>
<table><colgroup><col style="width:19mm"><col style="width:8mm"><col style="width:11mm"><col style="width:38%"><col></colgroup>
<thead><tr><th>チェック</th><th>No</th><th>頁</th><th>問題</th><th>答え</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""

FONT = "Noto Sans CJK JP"

def check_font():
    # フォントがないと Chrome が黙って別のフォントで印刷してしまうので、先に止める
    if not shutil.which("fc-list"):
        print(f"注意: fc-list がないため {FONT} の有無を確認できません")
        return
    found = subprocess.run(["fc-list", f":family={FONT}"], capture_output=True, text=True).stdout
    if not found.strip():
        raise SystemExit(f"エラー: フォント {FONT} が見つかりません。\n"
                         "  Linux: apt-get install -y fonts-noto-cjk を実行してから、もう一度実行してください。")

check_font()
out = BASE
(out / "kigyoho.html").write_text(render(), encoding="utf-8")
chrome = next(c for c in ["google-chrome","chromium","chromium-browser","/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"] if shutil.which(c) or pathlib.Path(c).exists())
subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                "--no-pdf-header-footer", f"--print-to-pdf={out/'企業法_一問一答.pdf'}",
                (out / "kigyoho.html").as_uri()], check=True, capture_output=True)
print("ok")

import csv, html, json, subprocess, pathlib, shutil

BASE = pathlib.Path(__file__).parent
PDF_DIR = BASE / "pdf"
FONT = "Noto Sans CJK JP"


def load():
    """CSV を授業（lesson 行）ごとに分ける。戻り値は [(授業名, 行のリスト), ...]"""
    lessons = []
    h1 = h2 = None  # 授業をまたいで続く編・章の見出し
    with open(BASE / "questions.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["type"]
            if t == "lesson":
                lessons.append((r["question"], []))
                continue
            if not lessons:
                raise SystemExit("エラー: questions.csv の先頭に lesson 行（例: lesson,,,第1回,）が必要です")
            rows = lessons[-1][1]
            if t == "h1":
                h1, h2 = r["question"], None
                rows.append(("h1", h1))
            elif t == "h2":
                h2 = r["question"]
                rows.append(("h2", h2))
            else:
                # 授業が編・章の途中から始まるときは、見出しを繰り返して載せる
                if not rows:
                    if h1: rows.append(("h1", h1))
                    if h2: rows.append(("h2", h2))
                rows.append((r["no"], r["page"], r["question"], r["answer"], (r.get("level") or "").strip() == "上"))
    for _, rows in lessons:
        # 回の末尾に問題のない見出しが残っていたら外す（次の回の頭に繰り返して載る）
        while rows and rows[-1][0] in ("h1", "h2"):
            rows.pop()
    return lessons


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
td.no { text-align: right; font-weight: 700; color: #2f4a6d; white-space: nowrap; }
.adv { display: inline-block; vertical-align: .2mm; margin-right: 1mm; white-space: nowrap; }
.adv span { display: inline-block; width: 3.8mm; height: 3.8mm; line-height: 3.8mm;
  border-radius: 50%; background: #111; color: #fff; font-size: 6.8pt; font-weight: 700;
  text-align: center; margin-left: .3mm; }
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


ADV_MARK = '<span class="adv"><span>上</span><span>級</span></span>'


def render(name, data):
    rows = []
    for r in data:
        if r[0] in ("h1", "h2"):
            rows.append(f'<tr class="{r[0]}"><td colspan="5">{html.escape(r[1])}</td></tr>')
        else:
            n, pg, q, a, adv = r
            mark = ADV_MARK if adv else ""
            rows.append(
                f'<tr><td class="chk"><span class="box"></span><span class="box"></span><span class="box"></span></td><td class="no">{mark}{n}</td><td class="pg">{pg}</td>'
                f'<td>{html.escape(q)}</td><td class="ans">{a}</td>'
                '</tr>')
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<h1 class="title">企業法　一問一答　{html.escape(name)}</h1>
<div class="sub">答えは右列。隠して解き、間違えたら□に印。3回連続正解で卒業。{ADV_MARK}＝上級の範囲。</div>
<table><colgroup><col style="width:19mm"><col style="width:15mm"><col style="width:11mm"><col style="width:38%"><col></colgroup>
<thead><tr><th>チェック</th><th>No</th><th>頁</th><th>問題</th><th>答え</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""


INDEX = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache">
<title>企業法 一問一答</title>
<style>
  body { font-family: -apple-system, "Hiragino Sans", "Noto Sans CJK JP", sans-serif;
    margin: 0; padding: 24px 16px; background: #f4f6f9; color: #222; }
  h1 { font-size: 22px; color: #2f4a6d; margin: 0 0 4px; }
  p.sub { font-size: 13px; color: #777; margin: 0 0 20px; }
  ul { list-style: none; padding: 0; margin: 0 auto; max-width: 520px; display: grid; gap: 10px; }
  a { display: flex; justify-content: space-between; align-items: center;
    background: #fff; border: 1px solid #c8ced6; border-radius: 12px;
    padding: 16px 18px; text-decoration: none; color: #2f4a6d; font-size: 18px; font-weight: 700; }
  a:active { background: #e8edf3; }
  a span { font-size: 13px; color: #888; font-weight: 400; }
  .wrap { max-width: 520px; margin: 0 auto; }
</style>
</head>
<body>
<div class="wrap">
  <h1>企業法 一問一答</h1>
  <p class="sub">授業の回を選ぶと PDF が開きます</p>
</div>
<ul>
__ITEMS__
</ul>
<script>
  // 毎回ちがう ?v= を付けて、キャッシュではなく最新の PDF を取りに行く
  document.querySelectorAll("a[data-pdf]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      location.href = a.getAttribute("href") + "?v=" + Date.now();
    });
  });
</script>
</body>
</html>
"""


def check_font():
    # フォントがないと Chrome が黙って別のフォントで印刷してしまうので、先に止める
    if not shutil.which("fc-list"):
        print(f"注意: fc-list がないため {FONT} の有無を確認できません")
        return
    found = subprocess.run(["fc-list", f":family={FONT}"], capture_output=True, text=True).stdout
    if not found.strip():
        raise SystemExit(f"エラー: フォント {FONT} が見つかりません。\n"
                         "  Linux: apt-get install -y fonts-noto-cjk を実行してから、もう一度実行してください。")


def main():
    check_font()
    chrome = next(c for c in ["google-chrome", "chromium", "chromium-browser",
                              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
                  if shutil.which(c) or pathlib.Path(c).exists())
    lessons = load()
    if PDF_DIR.exists():
        shutil.rmtree(PDF_DIR)  # 消した回の PDF が残らないように作り直す
    PDF_DIR.mkdir()
    tmp = BASE / "kigyoho.html"
    items = []
    for name, data in lessons:
        fname = f"企業法_{name}.pdf"
        tmp.write_text(render(name, data), encoding="utf-8")
        subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer", f"--print-to-pdf={PDF_DIR / fname}",
                        tmp.as_uri()], check=True, capture_output=True)
        nq = sum(1 for r in data if r[0] not in ("h1", "h2"))
        items.append(f'  <li><a data-pdf href="pdf/{html.escape(fname)}">{html.escape(name)}<span>{nq}問</span></a></li>')
        print(f"{name}: {nq}問 → pdf/{fname}")
    tmp.unlink()
    (BASE / "index.html").write_text(INDEX.replace("__ITEMS__", "\n".join(items)), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()

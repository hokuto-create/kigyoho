import csv, html, json, re, subprocess, pathlib, shutil

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
/* 見出しと直後の問題を同じ tbody にまとめ、見出しだけがページ末尾に残らないようにする */
tbody.keep { break-inside: avoid; }
td.no { text-align: center; font-weight: 700; color: #2f4a6d; white-space: nowrap; }
td.no .adv { display: block; margin-top: 1mm; }
.adv { display: inline-block; white-space: nowrap; }
.adv span { display: inline-block; width: 3.8mm; height: 3.8mm; line-height: 3.8mm;
  border-radius: 50%; background: #111; color: #fff; font-size: 6.8pt; font-weight: 700;
  text-align: center; margin: 0 .15mm; }
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


def render(name, data, start=0):
    """start: この回より前の回のページ数の合計（ページ番号を全体の通し番号にする）"""
    # 見出しの連続とその直後の問題1問を1つの tbody（keep）にまとめる
    bodies, pending = [], []
    for r in data:
        if r[0] in ("h1", "h2"):
            pending.append(f'<tr class="{r[0]}"><td colspan="5">{html.escape(r[1])}</td></tr>')
        else:
            n, pg, q, a, adv = r
            mark = ADV_MARK if adv else ""
            tr = (f'<tr><td class="chk"><span class="box"></span><span class="box"></span><span class="box"></span></td><td class="no">{n}{mark}</td><td class="pg">{pg}</td>'
                  f'<td>{html.escape(q)}</td><td class="ans">{a}</td>'
                  '</tr>')
            if pending:
                bodies.append('<tbody class="keep">' + "".join(pending) + tr + '</tbody>')
                pending = []
            else:
                bodies.append('<tbody>' + tr + '</tbody>')
    if pending:
        bodies.append('<tbody>' + "".join(pending) + '</tbody>')
    return f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}
html {{ counter-reset: page {start}; }}</style></head><body>
<h1 class="title">企業法　一問一答　{html.escape(name)}</h1>
<div class="sub">答えは右列。隠して解き、間違えたら□に印。3回連続正解で卒業。{ADV_MARK}＝上級の範囲。</div>
<table><colgroup><col style="width:19mm"><col style="width:11mm"><col style="width:11mm"><col style="width:38%"><col></colgroup>
<thead><tr><th>チェック</th><th>No</th><th>頁</th><th>問題</th><th>答え</th></tr></thead>
{''.join(bodies)}</table></body></html>"""


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
  ul.toc { margin-bottom: 20px; }
  ul.toc a { background: #2f4a6d; border-color: #2f4a6d; color: #fff; }
  ul.toc a span { color: #c9d4e2; }
</style>
</head>
<body>
<div class="wrap">
  <h1>企業法 一問一答</h1>
  <p class="sub">授業の回を選ぶと PDF が開きます</p>
</div>
__TOC__<ul>
__ITEMS__
</ul>
<script>
  // 毎回ちがう ?v= を付けて、キャッシュではなく最新の PDF を取りに行く
  document.querySelectorAll("a[data-pdf], a[data-fresh]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      location.href = a.getAttribute("href") + "?v=" + Date.now();
    });
  });
  // 入口ページ自体が古いキャッシュでも、問題数は毎回最新の counts.json から表示し直す
  function refreshCounts() {
    fetch("counts.json?v=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (counts) {
        document.querySelectorAll("a[data-pdf]").forEach(function (a) {
          var name = a.getAttribute("data-name");
          if (name in counts) a.querySelector("span").textContent = counts[name] + "問";
        });
      })
      .catch(function () {});
  }
  refreshCounts();
  window.addEventListener("pageshow", refreshCounts);
</script>
</body>
</html>
"""


# ---------- 見出し復習（toc.csv） ----------
# type: h1＝編、h2＝章、h3＝節、h4＝項、h5＝さらに下の見出し、m＝覚えるべき事項（直前の見出しの下に入る）
TOC_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5}


def load_toc():
    """toc.csv を木にする。ノードは {"title", "page", "memo": [...], "children": [...]}"""
    root = {"title": "", "page": "", "memo": [], "children": [], "level": 0}
    stack = [root]
    path = BASE / "toc.csv"
    if not path.exists():
        return root
    with open(path, encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f), start=2):
            t = (r["type"] or "").strip()
            if t == "m":
                if len(stack) == 1:
                    raise SystemExit(f"エラー: toc.csv {i}行目の m の前に見出しがありません")
                stack[-1]["memo"].append(r["title"])
                continue
            if t not in TOC_LEVELS:
                raise SystemExit(f"エラー: toc.csv {i}行目の type「{t}」は h1〜h5 か m にしてください")
            lv = TOC_LEVELS[t]
            while stack[-1]["level"] >= lv:
                stack.pop()
            node = {"title": r["title"], "page": (r["page"] or "").strip(), "memo": [], "children": [], "level": lv}
            stack[-1]["children"].append(node)
            stack.append(node)
    return root


def toc_page(node):
    return f'<span class="pg">p.{html.escape(node["page"])}</span>' if node["page"] else ""


def toc_html_nodes(nodes, path=""):
    out = []
    for k, n in enumerate(nodes):
        key = f"{path}{k}."
        memo = "".join(f"<li>{m}</li>" for m in n["memo"])
        inner = (f'<ul class="memo">{memo}</ul>' if memo else "") + toc_html_nodes(n["children"], key)
        title = f'<span class="t">{html.escape(n["title"])}</span>{toc_page(n)}'
        if inner:
            out.append(f'<details class="lv{n["level"]}" data-key="{key}"><summary>{title}</summary>'
                       f'<div class="in">{inner}</div></details>')
        else:
            out.append(f'<div class="leaf lv{n["level"]}">{title}</div>')
    return "".join(out)


TOC_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache">
<title>企業法 見出し復習</title>
<style>
  body { font-family: -apple-system, "Hiragino Sans", "Noto Sans CJK JP", sans-serif;
    margin: 0; padding: 24px 16px 48px; background: #f4f6f9; color: #222; }
  .wrap { max-width: 720px; margin: 0 auto; }
  h1 { font-size: 22px; color: #2f4a6d; margin: 0 0 4px; }
  .bar { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0 16px; }
  .bar a, .bar button { font: inherit; font-size: 14px; padding: 8px 14px; border-radius: 10px;
    border: 1px solid #c8ced6; background: #fff; color: #2f4a6d; text-decoration: none; cursor: pointer; }
  summary, .leaf { display: flex; align-items: baseline; gap: 8px; padding: 10px 12px; cursor: pointer;
    list-style: none; color: #2f4a6d; }
  summary::-webkit-details-marker { display: none; }
  summary::before { content: "▸"; color: #8a97a8; font-size: 12px; width: 12px; flex: none;
    transition: transform .15s; }
  details[open] > summary::before { transform: rotate(90deg); }
  .leaf { cursor: default; }
  .leaf::before { content: ""; width: 12px; flex: none; }
  .t { flex: 1; }
  .pg { color: #888; font-size: 12px; font-weight: 400; white-space: nowrap; }
  details.lv1 { background: #fff; border: 1px solid #c8ced6; border-radius: 12px; margin-bottom: 10px; overflow: hidden; }
  .lv1 > summary, .leaf.lv1 { font-size: 17px; font-weight: 700; }
  .leaf.lv1 { background: #fff; border: 1px solid #c8ced6; border-radius: 12px; margin-bottom: 10px; }
  .lv1 > .in { border-top: 1px solid #e3e7ec; padding: 4px 0 6px; }
  .lv2 > summary, .leaf.lv2 { font-weight: 700; font-size: 16px; }
  .in .in { margin-left: 16px; border-left: 2px solid #e3e7ec; }
  .lv3 > summary, .leaf.lv3, .lv4 > summary, .leaf.lv4, .lv5 > summary, .leaf.lv5 { font-size: 15px; }
  ul.memo { margin: 2px 12px 8px 32px; padding: 8px 12px 8px 28px; background: #fdf3f2;
    border-radius: 8px; color: #c0392b; font-size: 14px; line-height: 1.6; }
  ul.memo b { color: #a31515; }
</style>
</head>
<body>
<div class="wrap">
  <h1>企業法 見出し復習</h1>
  <div class="bar">
    <a href="./">← 戻る</a>
    <button id="openAll">すべて開く</button>
    <button id="closeAll">すべて閉じる</button>
    <a data-fresh href="pdf/企業法_見出し復習.pdf">PDF</a>
  </div>
__TREE__
</div>
<script>
  var KEY = "kigyoho-toc-open";
  function save() {
    var keys = [];
    document.querySelectorAll("details[open]").forEach(function (d) { keys.push(d.dataset.key); });
    try { localStorage.setItem(KEY, JSON.stringify(keys)); } catch (e) {}
  }
  try {
    (JSON.parse(localStorage.getItem(KEY)) || []).forEach(function (k) {
      var d = document.querySelector('details[data-key="' + k + '"]');
      if (d) d.open = true;
    });
  } catch (e) {}
  document.querySelectorAll("details").forEach(function (d) { d.addEventListener("toggle", save); });
  document.getElementById("openAll").onclick = function () {
    document.querySelectorAll("details").forEach(function (d) { d.open = true; });
  };
  document.getElementById("closeAll").onclick = function () {
    document.querySelectorAll("details").forEach(function (d) { d.open = false; });
  };
  document.querySelectorAll("a[data-fresh]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      location.href = a.getAttribute("href") + "?v=" + Date.now();
    });
  });
</script>
</body>
</html>
"""


TOC_CSS = """
@page { size: A4; margin: 14mm 14mm 14mm 14mm;
  @bottom-center { content: counter(page); } }
body { font-family: 'Noto Sans CJK JP'; font-size: 10.5pt; color: #222; }
h1.title { font-size: 17pt; margin: 0 0 5mm; letter-spacing: .05em; }
.row { display: flex; align-items: baseline; gap: 3mm; padding: 1.2mm 0; break-inside: avoid; }
.row .t { flex: 1; }
.row .pg { color: #888; font-size: 9pt; white-space: nowrap; }
.lv1 { background: #e8edf3; font-weight: 700; font-size: 12.5pt; color: #2f4a6d;
  padding: 2mm 2mm; margin-top: 4mm; break-after: avoid; }
.lv2 { font-weight: 700; color: #2f4a6d; border-bottom: .4mm solid #2f4a6d;
  margin: 2.5mm 0 1mm 4mm; break-after: avoid; }
.lv3 { margin-left: 9mm; font-weight: 700; }
.lv4 { margin-left: 14mm; }
.lv5 { margin-left: 19mm; font-size: 10pt; }
ul.memo { margin: .5mm 0 1.5mm; padding-left: 5mm; color: #c0392b; font-size: 9pt; line-height: 1.55; }
ul.memo b { color: #a31515; }
"""

TOC_INDENT = {1: 2, 2: 6, 3: 11, 4: 16, 5: 21}


def toc_pdf_rows(nodes):
    out = []
    for n in nodes:
        out.append(f'<div class="row lv{n["level"]}"><span class="t">{html.escape(n["title"])}</span>{toc_page(n)}</div>')
        if n["memo"]:
            out.append(f'<ul class="memo" style="margin-left:{TOC_INDENT[n["level"]] + 3}mm">'
                       + "".join(f"<li>{m}</li>" for m in n["memo"]) + "</ul>")
        out.append(toc_pdf_rows(n["children"]))
    return "".join(out)


def build_toc(chrome):
    root = load_toc()
    if not root["children"]:
        return False
    (BASE / "toc.html").write_text(TOC_HTML.replace("__TREE__", toc_html_nodes(root["children"])), encoding="utf-8")
    tmp = BASE / "kigyoho_toc.html"
    tmp.write_text(f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>{TOC_CSS}</style></head>
<body><h1 class="title">企業法　見出し復習</h1>{toc_pdf_rows(root["children"])}</body></html>""", encoding="utf-8")
    subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                    "--no-pdf-header-footer", f"--print-to-pdf={PDF_DIR / '企業法_見出し復習.pdf'}",
                    tmp.as_uri()], check=True, capture_output=True)
    tmp.unlink()
    print("見出し復習 → toc.html, pdf/企業法_見出し復習.pdf")
    return True


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
    counts = {}
    pages = 0  # ここまでの回のページ数の合計
    for name, data in lessons:
        fname = f"企業法_{name}.pdf"
        tmp.write_text(render(name, data, pages), encoding="utf-8")
        subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer", f"--print-to-pdf={PDF_DIR / fname}",
                        tmp.as_uri()], check=True, capture_output=True)
        pages += len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", (PDF_DIR / fname).read_bytes()))
        nq = sum(1 for r in data if r[0] not in ("h1", "h2"))
        items.append(f'  <li><a data-pdf data-name="{html.escape(name)}" href="pdf/{html.escape(fname)}">{html.escape(name)}<span>{nq}問</span></a></li>')
        counts[name] = nq
        print(f"{name}: {nq}問 → pdf/{fname}")
    tmp.unlink()
    toc = ""
    if build_toc(chrome):
        toc = ('<ul class="toc">\n'
               '  <li><a data-fresh href="toc.html">見出し復習<span>タップで開く</span></a></li>\n'
               '  <li><a data-fresh href="pdf/企業法_見出し復習.pdf">見出し復習（PDF）<span>印刷用</span></a></li>\n'
               '</ul>\n')
    elif (BASE / "toc.html").exists():
        (BASE / "toc.html").unlink()
    (BASE / "index.html").write_text(INDEX.replace("__TOC__", toc).replace("__ITEMS__", "\n".join(items)), encoding="utf-8")
    (BASE / "counts.json").write_text(json.dumps(counts, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()

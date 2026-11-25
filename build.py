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


# ---------- web確認問題（toc.csv） ----------
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
            node = {"title": r["title"], "page": (r["page"] or "").strip(), "memo": [], "children": [], "level": lv,
                    "id": stack[-1].get("id", "") + "／" + r["title"]}
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
        if n["memo"]:
            # 覚える事項がある見出し＝1問。チェック□□□（タップで 空→×→○→空）
            title = (f'<span class="ck" data-id="{html.escape(n["id"])}">'
                     + '<i></i>' * 3 + '</span>' + title)
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
<title>企業法 web確認問題</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;700&family=Klee+One:wght@400;600&family=Zen+Old+Mincho:wght@400;700&family=Cormorant+Garamond:ital,wght@1,500&display=swap">
<script>
  // 文字の設定（タイトル・問題部分それぞれ a/c/d）を、描画の前に反映する
  try {
    document.documentElement.dataset.tf = localStorage.getItem("kigyoho-font-title") || "a";
    document.documentElement.dataset.qf = localStorage.getItem("kigyoho-font-q") || "a";
  } catch (e) { document.documentElement.dataset.tf = document.documentElement.dataset.qf = "a"; }
</script>
<style>
  body { font-family: -apple-system, "Hiragino Sans", "Noto Sans CJK JP", sans-serif;
    margin: 0; padding: 24px 16px 48px; background: #f4f6f9; color: #222; }
  .wrap { max-width: 720px; margin: 0 auto; }
  h1 { font-size: 30px; font-weight: 700; color: #2f4a6d; margin: 0 0 4px; letter-spacing: .06em; line-height: 1.3; }
  h1 em { font-family: "Cormorant Garamond", serif; font-style: italic; font-weight: 500; font-size: 1.15em;
    letter-spacing: 0; margin-right: .08em; }
  h1 .eb { display: block; font-family: "Cormorant Garamond", serif; font-style: italic; font-weight: 500;
    font-size: 15px; letter-spacing: .12em; color: #8a97a8; }
  /* 文字の設定：s＝標準（端末のゴシック）、a＝上品な明朝、c＝手書き風、d＝クラシックな明朝 */
  [data-tf=a] h1 { font-family: "Shippori Mincho", serif; }
  [data-tf=c] h1 { font-family: "Klee One", serif; font-weight: 600; }
  [data-tf=d] h1 { font-family: "Zen Old Mincho", serif; }
  [data-qf=a] #tree { font-family: "Shippori Mincho", serif; font-weight: 500; }
  [data-qf=c] #tree { font-family: "Klee One", serif; }
  [data-qf=d] #tree { font-family: "Zen Old Mincho", serif; }
  #tree summary .t, #tree .leaf .t, #tree b { font-weight: 700; }
  [data-qf=c] #tree summary .t, [data-qf=c] #tree .leaf .t, [data-qf=c] #tree b { font-weight: 600; }
  .wrap { position: relative; }
  #setBtn { position: absolute; top: 0; right: 0; width: 44px; height: 44px; border-radius: 50%;
    border: 1px solid #c8ced6; background: #fff; color: #2f4a6d; cursor: pointer;
    display: flex; align-items: center; justify-content: center; padding: 0; }
  h1 { padding-right: 52px; }
  #setting { position: fixed; inset: 0; background: rgba(20, 30, 45, .35); z-index: 10;
    display: flex; align-items: flex-start; justify-content: center; padding: 60px 16px; }
  #setting[hidden] { display: none; }
  .sheet { background: #fff; border-radius: 16px; width: 100%; max-width: 520px; padding: 6px 18px 18px;
    box-shadow: 0 10px 40px rgba(0, 0, 0, .2); }
  .sh { display: flex; align-items: center; justify-content: space-between; font-size: 18px; font-weight: 700;
    color: #2f4a6d; padding: 8px 0 4px; }
  #setClose { font-size: 26px; line-height: 1; border: 0; background: none; color: #8a97a8; cursor: pointer; padding: 4px 6px; }
  .sec { margin-top: 12px; }
  .sec .lb { font-size: 13px; color: #666; margin-bottom: 6px; }
  .sec button { font-size: 16px; padding: 7px 14px; border-radius: 10px; border: 1px solid #c8ced6;
    background: #fff; color: #2f4a6d; cursor: pointer; margin: 0 6px 6px 0; }
  .sec button.on { background: #2f4a6d; color: #fff; border-color: #2f4a6d; }
  .sec [data-f=s] { font-weight: 700; }
  .sec [data-f=a] { font-family: "Shippori Mincho", serif; font-weight: 700; }
  .sec [data-f=c] { font-family: "Klee One", serif; font-weight: 600; }
  .sec [data-f=d] { font-family: "Zen Old Mincho", serif; font-weight: 700; }
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
  .filter { align-items: center; margin-top: -6px; }
  .filter .lb { font-size: 13px; color: #666; }
  .filter button.on { background: #2f4a6d; color: #fff; border-color: #2f4a6d; }
  #cnt { font-size: 13px; color: #666; }
  #none { color: #888; text-align: center; }
  .hide { display: none !important; }
  #syncStatus { font-size: 12px; color: #c0392b; margin: -6px 0 12px; }
  .syncbox { background: #f4f6f9; border-radius: 10px; padding: 10px 12px; font-size: 14px; color: #333; }
  .syncbox .st { font-weight: 700; color: #1e7d4f; }
  .syncbox .st.bad { color: #c0392b; }
  .syncbox .st.wait { color: #8a97a8; }
  .syncbox .sub { font-size: 12px; color: #666; margin-top: 4px; line-height: 1.6; }
  #syncNow { margin-top: 8px; }
  .ck { display: flex; gap: 4px; flex: none; align-self: center; }
  .ck i { width: 24px; height: 24px; border: 1.5px solid #8a97a8; border-radius: 4px; background: #fff;
    font-style: normal; font-weight: 700; font-size: 17px; line-height: 21px; text-align: center; }
  .ck i.x { color: #c0392b; border-color: #c0392b; }
  .ck i.o { color: #1e7d4f; border-color: #1e7d4f; }
  .ck i.x::after { content: "×"; }
  .ck i.o::after { content: "○"; }
</style>
</head>
<body>
<div class="wrap">
  <button id="setBtn" aria-label="設定"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg></button>
  <h1><span class="eb">Corporate Law · Web Review</span>企業法 <em>web</em>確認問題</h1>
  <div class="bar">
    <a href="./">← 戻る</a>
    <button id="openAll">すべて開く</button>
    <button id="closeAll">すべて閉じる</button>
    <a data-fresh href="pdf/企業法_web確認問題.pdf">PDF</a>
  </div>
  <div class="bar filter">
    <span class="lb">絞り込み</span>
    <button data-n="0">すべて</button>
    <button data-n="1">×1つ以上</button>
    <button data-n="2">×2つ以上</button>
    <button data-n="3">×3つ</button>
    <span id="cnt"></span>
  </div>
  <p id="syncStatus" hidden></p>
  <div id="tree">
__TREE__
  </div>
  <p id="none" hidden>該当する問題はありません</p>
</div>
<div id="setting" hidden>
  <div class="sheet" role="dialog" aria-label="設定">
    <div class="sh"><span>設定</span><button id="setClose" aria-label="閉じる">×</button></div>
    <div class="sec" data-k="kigyoho-font-title" data-attr="tf"><div class="lb">タイトルの文字</div>
      <button data-f="s">標準</button><button data-f="a">上品な明朝</button><button data-f="c">手書き風</button><button data-f="d">クラシック明朝</button></div>
    <div class="sec" data-k="kigyoho-font-q" data-attr="qf"><div class="lb">問題の文字</div>
      <button data-f="s">標準</button><button data-f="a">上品な明朝</button><button data-f="c">手書き風</button><button data-f="d">クラシック明朝</button></div>
    <div class="sec"><div class="lb">□の記録の同期</div>
      <div class="syncbox"><div class="st" id="syncSt">確認中…</div><div class="sub" id="syncSub"></div></div>
      <button id="syncNow">今すぐ同期</button></div>
  </div>
</div>
<script>
  // 文字の設定（この端末に保存）
  var setting = document.getElementById("setting");
  document.getElementById("setBtn").onclick = function () { setting.hidden = false; };
  document.getElementById("syncNow").onclick = function () { sync(); };
  document.getElementById("setClose").onclick = function () { setting.hidden = true; };
  setting.addEventListener("click", function (e) { if (e.target === setting) setting.hidden = true; });
  document.querySelectorAll("#setting .sec[data-attr]").forEach(function (row) {
    var bs = row.querySelectorAll("button");
    function mark() { bs.forEach(function (b) { b.classList.toggle("on", b.dataset.f === document.documentElement.dataset[row.dataset.attr]); }); }
    bs.forEach(function (b) {
      b.onclick = function () {
        document.documentElement.dataset[row.dataset.attr] = b.dataset.f;
        try { localStorage.setItem(row.dataset.k, b.dataset.f); } catch (e) {}
        mark();
      };
    });
    mark();
  });
  var KEY = "kigyoho-toc-open";
  function save() {
    var keys = [];
    document.querySelectorAll("#tree details[open]").forEach(function (d) { keys.push(d.dataset.key); });
    try { localStorage.setItem(KEY, JSON.stringify(keys)); } catch (e) {}
  }
  try {
    (JSON.parse(localStorage.getItem(KEY)) || []).forEach(function (k) {
      var d = document.querySelector('details[data-key="' + k + '"]');
      if (d) d.open = true;
    });
  } catch (e) {}
  document.querySelectorAll("#tree details").forEach(function (d) { d.addEventListener("toggle", save); });
  document.getElementById("openAll").onclick = function () {
    document.querySelectorAll("#tree details").forEach(function (d) { d.open = true; });
  };
  document.getElementById("closeAll").onclick = function () {
    document.querySelectorAll("#tree details").forEach(function (d) { d.open = false; });
  };
  // ---- チェック□□□の記録と同期 ----
  // marks = { 問題ID: { v: ["x","o",""], t: 変更した時刻(ms) } }
  // ・消さない：□を全部空に戻しても {v:["","",""], t} として残す。見出しが無くなった問題の記録も残す
  // ・合わせ方：問題ごとに t の新しい方を採る（空の端末・古い端末と同期しても、新しい記録は消えない）
  // ・クラウド（DayFlow と同じ Supabase の表）に、本体と日付ごとのバックアップを置く。操作は不要（自動で同期）
  var CLOUD = "kigyoho:marks";   // 全端末で共通の保存先
  var MKEY = "kigyoho-toc-marks", BKEY = "kigyoho-backup-day";
  var NEXT = { "": "x", x: "o", o: "" };
  var SUPA_URL = "https://bspylkvejufqinglwfga.supabase.co";
  var SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzcHlsa3ZlanVmcWluZ2x3ZmdhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk1MDc5MTAsImV4cCI6MjA5NTA4MzkxMH0.L9yyNoOQQ_hsBPAyut32d3rdgvW1W2mGffHRK2ZaH8w";
  function norm(x) {
    if (Array.isArray(x)) return { v: x, t: 0 };       // 以前の形式
    return x && Array.isArray(x.v) ? x : null;
  }
  function merge(a, b) {          // 同じ時刻なら a を採る
    var out = {};
    [a, b].forEach(function (s) {
      Object.keys(s || {}).forEach(function (k) {
        var x = norm(s[k]);
        if (x && (!out[k] || (x.t || 0) > (out[k].t || 0))) out[k] = x;
      });
    });
    return out;
  }
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  var marks = {};
  try { marks = merge(JSON.parse(lsGet(MKEY)) || {}, {}); } catch (e) {}
  function saveLocal() { lsSet(MKEY, JSON.stringify(marks)); }
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(function () {});

  var cks = document.querySelectorAll(".ck");
  function paint() {
    cks.forEach(function (ck) {
      var m = marks[ck.dataset.id];
      ck.querySelectorAll("i").forEach(function (b, i) { b.className = (m && m.v[i]) || ""; });
    });
  }
  paint();
  var timer = null;
  cks.forEach(function (ck) {
    var id = ck.dataset.id, boxes = ck.querySelectorAll("i");
    boxes.forEach(function (b) {
      b.addEventListener("click", function (e) {
        e.preventDefault(); e.stopPropagation();   // 見出しは開閉させない
        b.className = NEXT[b.className || ""];
        var v = []; boxes.forEach(function (x) { v.push(x.className); });
        marks[id] = { v: v, t: Date.now() };
        saveLocal();
        clearTimeout(timer); timer = setTimeout(sync, 1500);
      });
    });
  });

  var stEl = document.getElementById("syncStatus");
  // 同期の状態：設定画面に詳しく出す。失敗したときだけ、問題の一覧の上にも出す
  var lastOk = 0, lastErr = "";
  function status(kind, err) {          // kind: "busy" | "ok" | "bad"
    if (kind === "ok") { lastOk = Date.now(); lastErr = ""; }
    if (kind === "bad") lastErr = err;
    var st = document.getElementById("syncSt"), sub = document.getElementById("syncSub");
    var n = Object.keys(marks).filter(function (k) { return marks[k].v.join(""); }).length;
    var when = lastOk ? "最後に同期した時刻：" + new Date(lastOk).toLocaleString("ja-JP", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "まだ同期していません";
    if (kind === "busy") { st.textContent = "同期中…"; st.className = "st wait"; }
    else if (lastErr) { st.textContent = "× 同期できていません"; st.className = "st bad"; }
    else { st.textContent = "✓ 同期できています"; st.className = "st"; }
    sub.textContent = when + "／印のある問題：" + n + "問" + (lastErr ? "／理由：" + lastErr + "（記録はこの端末に残っています。1分後に自動でやり直します）" : "");
    stEl.hidden = !lastErr;
    stEl.textContent = lastErr ? "同期できていません（記録はこの端末に残っています）。右上の設定で確認できます" : "";
  }
  function today() {
    var d = new Date();
    return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
  }
  var H = { apikey: SUPA_KEY, Authorization: "Bearer " + SUPA_KEY };
  async function cloudGet(key) {
    var res = await fetch(SUPA_URL + "/rest/v1/dayflow_data?user_email=eq." + encodeURIComponent(key) + "&select=data",
      { headers: H, cache: "no-store" });
    if (!res.ok) throw "取得 HTTP " + res.status;
    var rows = await res.json();
    return rows[0] ? rows[0].data : null;
  }
  async function cloudPut(key, data) {
    var res = await fetch(SUPA_URL + "/rest/v1/dayflow_data", {
      method: "POST",
      headers: Object.assign({ "Content-Type": "application/json", Prefer: "resolution=merge-duplicates" }, H),
      body: JSON.stringify({ user_email: key, data: data, updated_at: new Date().toISOString() })
    });
    if (!res.ok) throw "送信 HTTP " + res.status;
  }
  var busy = false, again = false, retry = null;
  async function sync() {
    if (busy) { again = true; return; }
    busy = true; clearTimeout(retry);
    status("busy");
    try {
      var cloud = await cloudGet(CLOUD);
      var remote = (cloud && cloud.marks) || {};
      var merged = merge(marks, remote);
      marks = merged; saveLocal(); paint();
      var changed = JSON.stringify(merged) !== JSON.stringify(merge(remote, {}));
      if (changed) await cloudPut(CLOUD, { marks: merged });
      var day = today();
      if (changed || lsGet(BKEY) !== day) {         // 日付ごとのバックアップ（その日の最新）
        await cloudPut("kigyoho-backup:" + day, { marks: merged });
        lsSet(BKEY, day);
      }
      status("ok");
    } catch (e) {
      status("bad", String(e));
      retry = setTimeout(sync, 60000);
    } finally {
      busy = false;
      if (again) { again = false; sync(); }
    }
  }
  document.addEventListener("visibilitychange", function () { if (!document.hidden) sync(); });
  window.addEventListener("pageshow", function (e) { if (e.persisted) sync(); });

  sync();
  // 絞り込み：×の数が n 以上の問題だけ表示（その問題を含む見出しは開く。問題そのものは開かない）
  var FKEY = "kigyoho-toc-filter";
  function nx(d) {
    var ck = d.querySelector(":scope > summary > .ck");
    return ck ? ck.querySelectorAll("i.x").length : -1;   // -1＝問題ではない見出し
  }
  function walk(el, n) {          // el の中に表示する問題があれば true
    var any = false;
    el.querySelectorAll(":scope > details, :scope > .leaf, :scope > .in > details, :scope > .in > .leaf").forEach(function (c) {
      var hit = c.tagName === "DETAILS" && nx(c) >= Math.max(n, 1);
      var sub = c.tagName === "DETAILS" ? walk(c, n) : false;
      var show = n === 0 || hit || sub;
      c.classList.toggle("hide", !show);
      // 絞り込み中、対象外の問題の答え（覚える事項）は隠す
      var memo = c.querySelector(":scope > .in > ul.memo");
      if (memo) memo.classList.toggle("hide", n > 0 && !hit);
      if (n > 0 && sub) c.open = true;
      if (n > 0 && hit) cnt++;
      any = any || hit || sub;
    });
    return any;
  }
  var cnt = 0;
  function applyFilter(n) {
    cnt = 0;
    var any = walk(document.getElementById("tree"), n);
    document.querySelectorAll(".filter button").forEach(function (b) { b.classList.toggle("on", +b.dataset.n === n); });
    document.getElementById("cnt").textContent = n > 0 ? cnt + "問" : "";
    document.getElementById("none").hidden = n === 0 || any;
    try { localStorage.setItem(FKEY, String(n)); } catch (e) {}
  }
  document.querySelectorAll(".filter button").forEach(function (b) {
    b.onclick = function () { applyFilter(+b.dataset.n); };
  });
  var f0 = 0;
  try { f0 = +(localStorage.getItem(FKEY) || 0); } catch (e) {}
  applyFilter(f0);
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
.row .ck { display: flex; gap: 1mm; flex: none; align-self: center; }
.row .ck i { width: 4mm; height: 4mm; border: .3mm solid #666; }
"""

TOC_INDENT = {1: 2, 2: 6, 3: 11, 4: 16, 5: 21}


def toc_pdf_rows(nodes):
    out = []
    for n in nodes:
        ck = '<span class="ck"><i></i><i></i><i></i></span>' if n["memo"] else ""
        out.append(f'<div class="row lv{n["level"]}">{ck}<span class="t">{html.escape(n["title"])}</span>{toc_page(n)}</div>')
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
<body><h1 class="title">企業法　web確認問題</h1>{toc_pdf_rows(root["children"])}</body></html>""", encoding="utf-8")
    subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                    "--no-pdf-header-footer", f"--print-to-pdf={PDF_DIR / '企業法_web確認問題.pdf'}",
                    tmp.as_uri()], check=True, capture_output=True)
    tmp.unlink()
    print("web確認問題 → toc.html, pdf/企業法_web確認問題.pdf")
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
               '  <li><a data-fresh href="toc.html">web確認問題<span>タップで開く</span></a></li>\n'
               '  <li><a data-fresh href="pdf/企業法_web確認問題.pdf">web確認問題（PDF）<span>印刷用</span></a></li>\n'
               '</ul>\n')
    elif (BASE / "toc.html").exists():
        (BASE / "toc.html").unlink()
    (BASE / "index.html").write_text(INDEX.replace("__TOC__", toc).replace("__ITEMS__", "\n".join(items)), encoding="utf-8")
    (BASE / "counts.json").write_text(json.dumps(counts, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()

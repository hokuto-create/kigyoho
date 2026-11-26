import csv, html, json, re, subprocess, pathlib, shutil, hashlib

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


# ---------- 更新チェック（ホーム画面のアプリなどで古い版が残らないように） ----------
# ページを開いたとき・アプリに戻ったときに公開中のページを取り直し、版が違えば新しい URL で開き直す。
# 版はページの中身のハッシュ（中身が変わったときだけ変わる）。
UPDATE_JS = """<script>
  var APP_VERSION = "__VER__";
  async function checkUpdate() {
    try {
      var r = await fetch(location.pathname + "?t=" + Date.now(), { cache: "no-store" });
      if (!r.ok) return;
      var m = (await r.text()).match(/APP_VERSION = "([0-9a-f]+)"/);
      if (m && m[1] !== APP_VERSION && location.search.indexOf("v=" + m[1]) < 0)
        location.replace(location.pathname + "?v=" + m[1] + location.hash);
    } catch (e) {}
  }
  checkUpdate();
  document.addEventListener("visibilitychange", function () { if (!document.hidden) checkUpdate(); });
</script>
"""


def with_version(page):
    """</body> の前に更新チェックを入れ、中身のハッシュを版として埋め込む"""
    ver = hashlib.sha1(page.encode("utf-8")).hexdigest()[:12]
    return page.replace("</body>", UPDATE_JS.replace("__VER__", ver) + "</body>", 1)


# ---------- web確認問題（一問一答を1問ずつ、web で） ----------
def load_web():
    """questions.csv を 編→章→問題 の木にする（回をまたいで同じ編・章はまとめる）。
    問題は {"lesson","no","page","q","a","adv"}。頁が空欄の問題は直前の問題の頁を使う。"""
    root = []
    lessons = []
    h1 = h2 = None
    page = ""
    lesson = ""
    with open(BASE / "questions.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["type"]
            if t == "lesson":
                lesson = r["question"]; lessons.append(lesson)
            elif t == "h1":
                h1 = next((n for n in root if n["title"] == r["question"]), None)
                if not h1:
                    h1 = {"title": r["question"], "children": [], "qs": []}; root.append(h1)
                h2 = None
            elif t == "h2":
                h2 = next((n for n in h1["children"] if n["title"] == r["question"]), None)
                if not h2:
                    h2 = {"title": r["question"], "children": [], "qs": []}; h1["children"].append(h2)
            elif t == "q":
                page = (r["page"] or "").strip() or page
                (h2 or h1)["qs"].append({"lesson": lesson, "no": r["no"], "page": page, "q": r["question"],
                                         "a": r["answer"], "adv": (r.get("level") or "").strip() == "上"})
    return root, lessons


def web_count(n):
    return len(n["qs"]) + sum(web_count(c) for c in n["children"])


def web_nodes(nodes, lv=1):
    out = []
    for n in nodes:
        qs = []
        for q in n["qs"]:
            adv = '<span class="adv">上級</span>' if q["adv"] else ""
            pg = f'<span class="pg">{html.escape(q["page"])}</span>' if q["page"] else ""
            qs.append(f'<details class="q" data-l="{html.escape(q["lesson"])}"><summary><div class="qm">'
                      f'<span class="ck" data-id="q:{html.escape(q["q"])}"><i></i><i></i><i></i></span>'
                      f'<span class="no">No.{html.escape(q["no"])}</span>{pg}{adv}<span class="lad"></span></div>'
                      f'<div class="qt">{html.escape(q["q"])}</div></summary><div class="ans">{q["a"]}</div></details>')
        inner = "".join(qs) + web_nodes(n["children"], lv + 1)
        out.append(f'<details class="h lv{lv}" data-key="h:{html.escape(n["title"])}"><summary class="hd">'
                   f'<span class="t">{html.escape(n["title"])}</span><span class="hcnt">{web_count(n)}問</span></summary>'
                   f'<div class="in">{inner}</div></details>')
    return "".join(out)


WEB_HTML = """<!DOCTYPE html>
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
    document.documentElement.dataset.sd = localStorage.getItem("kigyoho-show-date") || "on";
  } catch (e) {
    document.documentElement.dataset.tf = document.documentElement.dataset.qf = "a";
    document.documentElement.dataset.sd = "on";
  }
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
  #tree .hd .t, #tree .qt, #tree b { font-weight: 700; }
  [data-qf=c] #tree .hd .t, [data-qf=c] #tree .qt, [data-qf=c] #tree b { font-weight: 600; }
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
  .bar a, .bar button, .bar .oldbtn { font: inherit; font-size: 14px; padding: 8px 14px; border-radius: 10px;
    border: 1px solid #c8ced6; background: #fff; color: #2f4a6d; text-decoration: none; cursor: pointer; }
  .bar .oldbtn { display: inline-flex; align-items: center; gap: 2px; padding: 4px 10px 4px 14px; }
  .oldbtn select { font: inherit; font-weight: 700; color: inherit; background: rgba(47, 74, 109, .08);
    border: 0; border-radius: 6px; padding: 4px 6px; margin: 0 2px; cursor: pointer; }
  .filter .oldbtn.on { background: #2f4a6d; color: #fff; border-color: #2f4a6d; }
  .oldbtn.on select { background: rgba(255, 255, 255, .18); }
  .oldbtn select option { color: #222; }
  summary { list-style: none; cursor: pointer; }
  summary::-webkit-details-marker { display: none; }
  .hd { display: flex; align-items: baseline; gap: 8px; padding: 10px 12px; color: #2f4a6d; }
  .hd::before { content: "▸"; font-family: -apple-system, "Hiragino Sans", sans-serif; color: #8a97a8; font-size: 12px; width: 12px; flex: none; transition: transform .15s; }
  details[open] > .hd::before { transform: rotate(90deg); }
  .t { flex: 1; }
  .hcnt { color: #888; font-size: 12px; font-weight: 400; font-family: -apple-system, "Hiragino Sans", sans-serif; }
  details.lv1 { background: #fff; border: 1px solid #c8ced6; border-radius: 12px; margin-bottom: 10px; overflow: hidden; }
  .lv1 > .hd { font-size: 17px; }
  .lv1 > .in { border-top: 1px solid #e3e7ec; padding: 4px 0 8px; }
  .lv2 > .hd { font-size: 16px; }
  .in .in { margin-left: 16px; border-left: 2px solid #e3e7ec; }
  /* 1問 */
  details.q { margin: 6px 12px 6px 14px; border: 1px solid #e3e7ec; border-radius: 10px; background: #fbfcfd; }
  details.q[open] { background: #fff; border-color: #c8ced6; }
  details.q > summary { padding: 8px 10px; }
  .qm { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-family: -apple-system, "Hiragino Sans", sans-serif; }
  .no { font-weight: 700; color: #2f4a6d; font-size: 13px; }
  .pg { color: #888; font-size: 12px; }
  .adv { font-size: 11px; color: #fff; background: #111; border-radius: 9px; padding: 1px 7px; }
  .lad { margin-left: auto; font-size: 12px; font-weight: 700; border-radius: 9px; padding: 2px 8px; white-space: nowrap; }
  .lad:empty { display: none; }
  .lad.s1 { color: #c0392b; background: #fdecea; }
  .lad.s2 { color: #a66a00; background: #fff4d6; }
  .lad.s3 { color: #2563a8; background: #e6f0fb; }
  .lad.s4 { color: #1e7d4f; background: #e3f4ea; }
  .lad.due { color: #fff; background: #c0392b; }
  .qt { margin-top: 6px; color: #2f4a6d; font-size: 15px; line-height: 1.6; }
  .ans { padding: 2px 12px 12px; color: #c0392b; font-size: 14px; line-height: 1.7; border-top: 1px dashed #e3e7ec; margin: 0 10px; padding-top: 8px; }
  .ans b { color: #a31515; }
  .ans { box-sizing: border-box; overflow: hidden; }
  .in { box-sizing: border-box; display: flow-root; }
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
  .ck { display: flex; gap: 4px; flex: none; }
  .filter.les { margin-top: -8px; }
  .ck i { width: 24px; height: 24px; border: 1.5px solid #8a97a8; border-radius: 4px; background: #fff;
    font-style: normal; font-weight: 700; font-size: 17px; line-height: 21px; text-align: center; }
  .ck i.x { color: #c0392b; border-color: #c0392b; }
  .ck i.o { color: #1e7d4f; border-color: #1e7d4f; }
  .ck i.x::after { content: "×"; }
  .ck i.o::after { content: "○"; }
  /* ○を付けた日（設定で表示・非表示） */
  .ck i { position: relative; }
  [data-sd=on] .ck i.o[data-d]::before { content: attr(data-d); position: absolute; top: 100%; left: 50%;
    transform: translateX(-50%); margin-top: 2px; font-size: 10px; font-weight: 400; line-height: 1;
    color: #1e7d4f; white-space: nowrap; font-family: -apple-system, "Hiragino Sans", sans-serif; }
  [data-sd=on] .ck.hasd { margin-bottom: 13px; }
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
  </div>
  <div class="bar filter">
    <span class="lb">絞り込み</span>
    <button data-m="all">すべて</button>
    <button data-m="today">今日の復習</button>
    <button data-m="x1">×1つ以上</button>
    <button data-m="x2">×2つ以上</button>
    <button data-m="x3">×3つ</button>
    <label class="oldbtn" data-m="old">最終復習が
      <select id="oldPer" aria-label="期間">
        <option value="d3">3日</option><option value="d7">1週間</option><option value="d14">2週間</option>
        <option value="m1" selected>1ヶ月</option><option value="m2">2ヶ月</option><option value="m3">3ヶ月</option>
      </select>以上前</label>
    <span id="cnt"></span>
  </div>
  <div class="bar filter les">
    <span class="lb">回</span>
    <button data-l="">全回</button>
__LESSONS__
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
    <div class="sec" data-k="kigyoho-show-date" data-attr="sd"><div class="lb">○を付けた日</div>
      <button data-f="on">表示する</button><button data-f="off">表示しない</button></div>
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
  // 答え・編・章はヌルッと開閉する（端末の「視差効果を減らす」がオンなら、すぐ開閉する）
  var reduceMotion = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  document.querySelectorAll("details.q > summary, details.h > summary").forEach(function (sm) {
    sm.addEventListener("click", function (e) {
      var d = sm.parentNode, a = d.querySelector(":scope > .ans, :scope > .in");
      if (reduceMotion || !a.animate) return;
      e.preventDefault();
      if (d._anim) { d._anim.cancel(); d._done(); }   // 動いている途中なら、その場で終わらせる
      var cs = getComputedStyle(a);
      var shut = { height: "0px", paddingTop: "0px", paddingBottom: "0px", opacity: 0 };
      var opening = !d.open;
      if (opening) d.open = true;
      var h = a.offsetHeight;
      var full = { height: h + "px", paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom, opacity: 1 };
      var ms = Math.min(750, 460 + h / 5);         // 中身が多いほど少しゆっくり
      a.style.overflow = "hidden";
      d._anim = a.animate(opening ? [shut, full] : [full, shut],
        { duration: opening ? ms : ms * 0.7, easing: "cubic-bezier(.25, .8, .25, 1)" });
      d._done = function () {
        d._anim = null;
        a.style.overflow = "";
        if (!opening) d.open = false;
      };
      d._anim.onfinish = function () { if (d._anim) d._done(); };
    });
  });
  var KEY = "kigyoho-web-open";
  function save() {
    var keys = [];
    document.querySelectorAll("#tree details.h[open]").forEach(function (d) { keys.push(d.dataset.key); });
    try { localStorage.setItem(KEY, JSON.stringify(keys)); } catch (e) {}
  }
  try {
    (JSON.parse(localStorage.getItem(KEY)) || []).forEach(function (k) {
      var d = document.querySelector('details[data-key="' + k + '"]');
      if (d) d.open = true;
    });
  } catch (e) {}
  document.querySelectorAll("#tree details.h").forEach(function (d) { d.addEventListener("toggle", save); });
  document.getElementById("openAll").onclick = function () {
    document.querySelectorAll("#tree details.h").forEach(function (d) { d.open = true; });
  };
  document.getElementById("closeAll").onclick = function () {
    document.querySelectorAll("#tree details.h").forEach(function (d) { d.open = false; });
  };
  // ---- チェック□□□の記録と同期 ----
  // marks = { 問題ID: { v: ["x","o",""], d: ["2026-11-25","2026-11-26",""], t: 変更した時刻(ms) } }
  //   v＝□の印（左から順に、その回の結果）、d＝その印を付けた日
  // ・消さない：□を全部空に戻しても {v:["","",""], t} として残す。見出しが無くなった問題の記録も残す
  // ・合わせ方：問題ごとに t の新しい方を採る（空の端末・古い端末と同期しても、新しい記録は消えない）
  // ・クラウド（DayFlow と同じ Supabase の表）に、本体と日付ごとのバックアップを置く。操作は不要（自動で同期）
  var CLOUD = "kigyoho:marks";   // 全端末で共通の保存先
  var MKEY = "kigyoho-toc-marks", BKEY = "kigyoho-backup-day";
  var NEXT = { "": "x", x: "o", o: "" };
  var SUPA_URL = "https://bspylkvejufqinglwfga.supabase.co";
  var SUPA_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJzcHlsa3ZlanVmcWluZ2x3ZmdhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk1MDc5MTAsImV4cCI6MjA5NTA4MzkxMH0.L9yyNoOQQ_hsBPAyut32d3rdgvW1W2mGffHRK2ZaH8w";
  function norm(x) {
    if (Array.isArray(x)) x = { v: x, t: 0 };          // 以前の形式
    if (!x || !Array.isArray(x.v)) return null;
    if (!Array.isArray(x.d)) x.d = x.v.map(function (c) { return c && x.t ? dayOf(new Date(x.t)) : ""; });
    return x;
  }
  function dayOf(d) {
    return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
  }
  function today() { return dayOf(new Date()); }
  function addDays(s, n) { var p = s.split("-"); return dayOf(new Date(+p[0], +p[1] - 1, +p[2] + n)); }
  function cutoff(per) {          // 期間（d14＝14日、m1＝1ヶ月）前の日
    return per.charAt(0) === "d" ? addDays(today(), -(+per.slice(1))) : monthsAgo(+per.slice(1));
  }
  function monthsAgo(n) {         // nヶ月前の日（3/31 の1ヶ月前は 2/28 のように月末に揃える）
    var t = new Date(), d = new Date(t.getFullYear(), t.getMonth() - n, 1);
    d.setDate(Math.min(t.getDate(), new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()));
    return dayOf(d);
  }
  function lastDay(m) {           // 最後に印を付けた日（印がなければ ""）
    var last = "";
    if (m) m.v.forEach(function (c, i) { if (c && (m.d[i] || "") > last) last = m.d[i]; });
    return last;
  }
  // 復習ラダー（DayFlow と同じ）：□の印を左から順に見て段階を決める
  //   初回○→◎（復習不要）、初回×→✖。×はどの段階からでも✖に戻る。○で1段進む（✖→△→○→◎）
  //   次の復習日：✖＝翌日、△＝3日後、○＝1週間後（最後に印を付けた日から）
  var SR_DAYS = { 1: 1, 2: 3, 3: 7 }, SR_MARK = { 1: "✕", 2: "△", 3: "○", 4: "◎" };
  function ladder(m) {
    var st = 0, last = "", n = 0;
    if (m) m.v.forEach(function (c, i) {
      if (!c) return;
      n++;
      st = st === 0 ? (c === "o" ? 4 : 1) : (c === "x" ? 1 : Math.min(st + 1, 4));
      last = m.d[i] || today();
    });
    return { stage: st, n: n, due: st >= 1 && st <= 3 ? addDays(last, SR_DAYS[st]) : null };
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
  function paintOne(ck) {
    var m = marks[ck.dataset.id], v = m ? m.v.slice() : [];
    while (v.length && !v[v.length - 1]) v.pop();     // 後ろの空は数えない
    var L = ladder(m);
    var nb = Math.max(3, v.length + (v.length >= 3 && L.stage >= 1 && L.stage <= 3 ? 1 : 0));
    while (ck.children.length < nb) ck.appendChild(document.createElement("i"));
    while (ck.children.length > nb) ck.removeChild(ck.lastChild);
    var hasd = false;
    Array.prototype.forEach.call(ck.children, function (b, i) {
      b.className = (m && m.v[i]) || "";
      var dd = b.className === "o" && m.d[i];
      if (dd) { var q = dd.split("-"); b.dataset.d = (+q[1]) + "/" + (+q[2]); hasd = true; }
      else delete b.dataset.d;
    });
    ck.classList.toggle("hasd", hasd);
    var lad = ck.parentNode.querySelector(".lad");
    if (!L.n) { lad.textContent = ""; lad.className = "lad"; }
    else if (L.stage === 4) { lad.textContent = "◎ 復習不要"; lad.className = "lad s4"; }
    else if (L.due <= today()) { lad.textContent = SR_MARK[L.stage] + " 今日の復習"; lad.className = "lad s" + L.stage + " due"; }
    else {
      var p = L.due.split("-");
      lad.textContent = SR_MARK[L.stage] + " " + (+p[1]) + "/" + (+p[2]) + " に復習";
      lad.className = "lad s" + L.stage;
    }
  }
  function paint() { cks.forEach(paintOne); }
  paint();
  var timer = null;
  cks.forEach(function (ck) {
    ck.addEventListener("click", function (e) {
      e.preventDefault(); e.stopPropagation();   // □のタップでは問題を開閉しない
      var b = e.target.closest("i");
      if (!b) return;
      var idx = Array.prototype.indexOf.call(ck.children, b), id = ck.dataset.id;
      var m = marks[id] || { v: [], d: [] };
      var v = m.v.slice(), d = m.d.slice();
      while (v.length <= idx) { v.push(""); d.push(""); }
      v[idx] = NEXT[v[idx] || ""];
      d[idx] = v[idx] ? today() : "";
      marks[id] = { v: v, d: d, t: Date.now() };
      saveLocal(); paintOne(ck);
      clearTimeout(timer); timer = setTimeout(sync, 1500);
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
  // 絞り込み：印（すべて／今日の復習／×の数）と回。該当する問題を含む見出しは開く（問題そのものは開かない）
  var FKEY = "kigyoho-web-filter", fm = "all", fl = "", per = document.getElementById("oldPer");
  function hit(q) {
    if (fl && q.dataset.l !== fl) return false;
    if (fm === "all") return true;
    var m = marks[q.querySelector(".ck").dataset.id];
    if (fm === "today") { var L = ladder(m); return L.due !== null && L.due <= today(); }
    if (fm === "old") { var ld = lastDay(m); return ld !== "" && ld <= cutoff(per.value); }
    var nx = m ? m.v.filter(function (c) { return c === "x"; }).length : 0;
    return nx >= +fm.slice(1);
  }
  var cnt = 0;
  function walk(el, on) {          // el の中に表示する問題があれば true
    var any = false;
    el.querySelectorAll(":scope > details, :scope > .in > details").forEach(function (c) {
      var show = c.classList.contains("q") ? hit(c) : walk(c, on);
      if (show && c.classList.contains("q")) cnt++;
      c.classList.toggle("hide", !show);
      if (on && show && !c.classList.contains("q")) c.open = true;
      any = any || show;
    });
    return any;
  }
  function applyFilter() {
    cnt = 0;
    var on = fm !== "all" || fl !== "";
    var any = walk(document.getElementById("tree"), on);
    document.querySelectorAll(".filter [data-m]").forEach(function (b) { b.classList.toggle("on", b.dataset.m === fm); });
    document.querySelectorAll(".filter [data-l]").forEach(function (b) { b.classList.toggle("on", b.dataset.l === fl); });
    document.getElementById("cnt").textContent = on ? cnt + "問" : "";
    document.getElementById("none").hidden = any;
    try { localStorage.setItem(FKEY, JSON.stringify({ m: fm, l: fl, p: per.value })); } catch (e) {}
  }
  document.querySelectorAll(".filter [data-m]").forEach(function (b) {
    b.onclick = function () { fm = b.dataset.m; applyFilter(); };
  });
  per.onchange = function () { fm = "old"; applyFilter(); };   // 期間を選んだら、その期間で絞り込む
  document.querySelectorAll(".filter [data-l]").forEach(function (b) {
    b.onclick = function () { fl = b.dataset.l; applyFilter(); };
  });
  try {
    var f0 = JSON.parse(localStorage.getItem(FKEY)) || {};
    if (document.querySelector('.filter [data-m="' + f0.m + '"]')) fm = f0.m;
    if (document.querySelector('.filter [data-l="' + f0.l + '"]')) fl = f0.l;
    if (per.querySelector('option[value="' + f0.p + '"]')) per.value = f0.p;
  } catch (e) {}
  applyFilter();
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


def build_web():
    root, lessons = load_web()
    les = "\n".join(f'    <button data-l="{html.escape(l)}">{html.escape(l)}</button>' for l in lessons)
    (BASE / "toc.html").write_text(with_version(WEB_HTML.replace("__TREE__", web_nodes(root)).replace("__LESSONS__", les)),
                                   encoding="utf-8")
    n = sum(web_count(x) for x in root)
    print(f"web確認問題: {n}問 → toc.html")
    return n


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
    nweb = build_web()
    toc = ('<ul class="toc">\n'
           f'  <li><a data-fresh href="toc.html">web確認問題<span>{nweb}問</span></a></li>\n'
           '</ul>\n')
    (BASE / "index.html").write_text(with_version(INDEX.replace("__TOC__", toc).replace("__ITEMS__", "\n".join(items))), encoding="utf-8")
    (BASE / "counts.json").write_text(json.dumps(counts, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()

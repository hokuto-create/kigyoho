import csv, html, json, re, subprocess, pathlib, shutil, hashlib

BASE = pathlib.Path(__file__).parent
PDF_DIR = BASE / "pdf"
FONT = "Noto Sans CJK JP"

# 科目。企業法は最初からある科目なので、ファイル名・同期の保存先は前のまま（記録を引き継ぐため変えない）。
#   csv＝問題データ、page＝web確認問題のページ、counts＝入口ページの問題数、pdf＝PDF のファイル名の頭
#   ls＝この端末の保存（localStorage）のキーの頭、cloud＝□の記録の同期の保存先、backup＝日付ごとのバックアップのキーの頭
SUBJECTS = [
    {"id": "law", "name": "企業法", "en": "Corporate Law", "csv": "questions.csv", "page": "toc.html",
     "counts": "counts.json", "pdf": "企業法", "ls": "kigyoho", "cloud": "kigyoho:marks", "backup": "kigyoho-backup"},
    {"id": "audit", "name": "監査論", "en": "Auditing", "csv": "audit_questions.csv", "page": "audit.html",
     "counts": "audit_counts.json", "pdf": "監査論", "ls": "kigyoho-audit", "cloud": "kigyoho:audit-marks",
     "backup": "kigyoho-audit-backup"},
]


def load(sub):
    """CSV を授業（lesson 行）ごとに分ける。戻り値は [(授業名, 行のリスト), ...]"""
    lessons = []
    h1 = h2 = None  # 授業をまたいで続く編・章の見出し
    with open(BASE / sub["csv"], encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["type"]
            if t == "lesson":
                lessons.append((r["question"], []))
                continue
            if not lessons:
                raise SystemExit(f"エラー: {sub['csv']} の先頭に lesson 行（例: lesson,,,第1回,）が必要です")
            rows = lessons[-1][1]
            if t == "h1":
                h1, h2 = r["question"], None
                rows.append(("h1", h1))
            elif t == "h2":
                h2 = r["question"]
                rows.append(("h2", h2))
            elif t == "h3":
                continue  # 節の見出しは web確認問題だけに出す（PDF には載せない）
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


def render(sub, name, data, start=0):
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
<h1 class="title">{sub["name"]}　web確認問題　{html.escape(name)}</h1>
<div class="sub">答えは右列。隠して解き、間違えたら□に印。3回連続正解で卒業。{ADV_MARK}＝上級の範囲。</div>
<table><colgroup><col style="width:19mm"><col style="width:11mm"><col style="width:11mm"><col style="width:38%"><col></colgroup>
<thead><tr><th>チェック</th><th>No</th><th>頁</th><th>問題</th><th>答え</th></tr></thead>
{''.join(bodies)}</table></body></html>"""


# ---------- 見た目の共通部分（入口ページと web確認問題） ----------
# 紺の表紙・生成りの紙・金のアクセント。本文は大きめ・行間広め・コントラスト 4.5:1 以上（勉強で読みやすいように）
FONTS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@500;700&family=Klee+One:wght@400;600&family=Zen+Old+Mincho:wght@400;700&family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&display=swap">"""

BASE_CSS = """  :root {
    --paper: #f5f1e8; --card: #fffdf9; --tint: #fbf6ef;
    --ink: #1d2943; --ink2: #4f576b; --mute: #6b7080;
    --line: #e9e2d4; --line2: #d9cebb;
    --navy: #1b2644; --cream: #f6efdf; --gold: #a37d45; --gold-d: #7d5f30; --gold-l: #dcc08a;
    --red: #b3332a; --red-d: #8e1f17; --green: #2c7a52; --amber: #8a5d00; --blue: #2a5d9c;
    --sans: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans CJK JP", sans-serif;
    --serif-en: "Cormorant Garamond", "Times New Roman", serif;
    --shadow: 0 1px 2px rgba(27, 38, 68, .05), 0 8px 24px rgba(27, 38, 68, .06);
  }
  html { -webkit-text-size-adjust: 100%; font-variant-numeric: lining-nums; }   /* 英字の明朝の数字も、読みやすい揃った形に */
  body { margin: 0; background: var(--paper); color: var(--ink); font-family: var(--sans); -webkit-tap-highlight-color: transparent; }
  .wrap { max-width: 720px; margin: 0 auto; padding: 0 16px; box-sizing: border-box; }
  /* 表紙（紺の帯。右上に § の透かし、下端に金の細線） */
  .cover { position: relative; overflow: hidden; color: var(--cream);
    background: radial-gradient(120% 140% at 100% 0%, rgba(62, 86, 145, .55) 0%, rgba(62, 86, 145, 0) 60%),
      linear-gradient(165deg, #22305a 0%, #1a2546 55%, #131b35 100%); }
  .cover::before { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 1px;
    background: linear-gradient(90deg, rgba(220, 192, 138, 0), rgba(220, 192, 138, .8) 50%, rgba(220, 192, 138, 0)); }
  .cover::after { content: "§"; position: absolute; right: -12px; top: -56px; font-family: var(--serif-en); font-size: 250px;
    line-height: 1; color: rgba(220, 192, 138, .08); pointer-events: none; }
  .cover .wrap { position: relative; z-index: 1; }
  .eb { font-family: var(--serif-en); font-style: italic; font-weight: 500; letter-spacing: .14em; color: var(--gold-l); }
  /* タイトルの文字（web確認問題の設定画面で選ぶ。入口ページと共通）：s＝標準、a＝上品な明朝、c＝手書き風、d＝クラシック明朝 */
  [data-tf=a] .disp { font-family: "Shippori Mincho", "Hiragino Mincho ProN", serif; }
  [data-tf=c] .disp { font-family: "Klee One", serif; font-weight: 600; }
  [data-tf=d] .disp { font-family: "Zen Old Mincho", "Hiragino Mincho ProN", serif; }"""


INDEX = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache">
<meta name="theme-color" content="#1b2644">
<title>web確認問題</title>
__FONTS__
<script>
  // タイトルの文字（web確認問題の設定画面で選ぶ。この端末に保存）と、選んでいる科目を、描画の前に反映する
  // 科目：#sub=科目のid が付いていればそれ、なければこの端末で前に選んだ科目（最初は企業法）
  (function () {
    var de = document.documentElement, ids = __SUBIDS__, h = location.hash.match(/^#sub=(\\w+)$/), sub = null;
    try { de.dataset.tf = localStorage.getItem("kigyoho-font-title") || "a"; sub = localStorage.getItem("kigyoho-subject"); }
    catch (e) { de.dataset.tf = "a"; }
    if (h) sub = h[1];
    de.dataset.sub = ids.indexOf(sub) >= 0 ? sub : ids[0];
  })();
</script>
<style>
__BASE__
  .wrap { max-width: 600px; }
  .cover { padding: 22px 0 70px; }
  .cover .top { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .cover .eb { font-size: 16px; }
  .date { font-family: var(--serif-en); font-size: 15px; font-weight: 500; letter-spacing: .1em; color: rgba(246, 239, 223, .75); }
  h1 { margin: 14px 0 8px; font-size: 36px; font-weight: 700; letter-spacing: .08em; line-height: 1.25; color: #f8f2e4; }
  h1 small { display: inline-block; margin-left: .35em; font-size: .62em; letter-spacing: .14em; color: var(--gold-l); }
  .lead { margin: 0; font-size: 13px; letter-spacing: .24em; color: rgba(246, 239, 223, .78); }
  /* 科目の切り替え（表紙の中。選んでいる科目は金色） */
  .subj { display: inline-flex; gap: 4px; margin-top: 18px; padding: 4px; border-radius: 999px;
    background: rgba(255, 255, 255, .06); border: 1px solid rgba(220, 192, 138, .32); }
  .subj button { font: inherit; font-size: 15px; font-weight: 700; letter-spacing: .1em; color: rgba(246, 239, 223, .82);
    background: none; border: 0; border-radius: 999px; padding: 8px 20px; min-height: 38px; cursor: pointer; }
__SUBCSS__
  main.wrap { position: relative; margin-top: -44px; padding-bottom: 48px; }
  /* web確認問題（表紙に少し重ねる） */
  .feat { position: relative; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 2px 16px;
    padding: 18px 18px 18px 24px; border-radius: 18px; text-decoration: none; color: var(--ink);
    background: var(--card); border: 1px solid rgba(176, 138, 79, .35); overflow: hidden;
    box-shadow: 0 2px 4px rgba(27, 38, 68, .06), 0 16px 36px rgba(27, 38, 68, .14); }
  .feat::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
    background: linear-gradient(180deg, #e7cd94, #b38a4b); }
  .feat .fe { grid-column: 1; font-family: var(--serif-en); font-style: italic; font-size: 15px; letter-spacing: .14em; color: var(--gold-d); }
  .feat .ft { grid-column: 1; font-size: 23px; font-weight: 700; letter-spacing: .06em; line-height: 1.4; }
  .feat .ft em { font-family: var(--serif-en); font-style: italic; font-weight: 500; font-size: 1.15em; letter-spacing: 0;
    margin-right: .06em; color: var(--gold-d); }
  .feat .fd { grid-column: 1; font-size: 13px; color: var(--ink2); margin-top: 2px; }
  .feat .fn { grid-column: 2; grid-row: 1 / span 3; display: flex; flex-direction: column; align-items: center; justify-content: center;
    width: 66px; height: 66px; border-radius: 50%; background: var(--navy); color: var(--cream); font-size: 11px;
    box-shadow: inset 0 0 0 1px rgba(220, 192, 138, .55), inset 0 0 0 4px var(--navy), inset 0 0 0 5px rgba(220, 192, 138, .3); }
  .feat .fn b { font-family: var(--serif-en); font-size: 26px; font-weight: 600; line-height: 1; }
  .feat:active { transform: scale(.99); }
  /* 授業の回 */
  .lh { display: flex; align-items: baseline; gap: 10px; margin: 30px 2px 12px; font-size: 16px; font-weight: 700;
    color: var(--ink); letter-spacing: .06em; }
  .lh .eb { font-size: 16px; color: var(--gold-d); letter-spacing: .12em; }
  .lh small { margin-left: auto; font-size: 12px; font-weight: 400; color: var(--mute); letter-spacing: .02em; }
  ul.les { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
  @media (min-width: 560px) { ul.les { grid-template-columns: 1fr 1fr; } }
  /* 回のカード：左（数字・回の名前）を押すとその回の web確認問題、右端の PDF を押すとその回の PDF */
  .les li { display: flex; align-items: stretch; border-radius: 14px; overflow: hidden;
    background: var(--card); border: 1px solid var(--line); box-shadow: var(--shadow); }
  .les a { text-decoration: none; color: var(--ink); }
  .les a:active { background: var(--tint); }
  .lm { flex: 1; min-width: 0; display: flex; align-items: center; gap: 14px; padding: 14px 0 14px 16px; }
  .lpw { flex: none; display: flex; align-items: center; padding: 0 16px 0 12px; }   /* PDF はカードの高さいっぱいが押せる範囲 */
  .ln { flex: none; width: 46px; padding-right: 12px; border-right: 1px solid var(--line); text-align: center;
    font-family: var(--serif-en); font-size: 32px; font-weight: 600; line-height: 1; color: var(--gold); }
  .lt { flex: 1; display: flex; flex-direction: column; gap: 2px; }
  .lname { font-size: 19px; font-weight: 700; letter-spacing: .06em; }
  .les .n { font-size: 12.5px; color: var(--mute); }
  .empty { margin: 0; padding: 22px 16px; border-radius: 14px; border: 1px dashed var(--line2); text-align: center;
    font-size: 14px; color: var(--ink2); background: var(--card); }
  .lp { flex: none; font-size: 11px; font-weight: 700; letter-spacing: .08em; color: var(--gold-d);
    border: 1px solid rgba(163, 125, 69, .5); border-radius: 999px; padding: 3px 9px; }
</style>
</head>
<body>
<header class="cover">
  <div class="wrap">
    <div class="top">__SUBEN__<span class="date" id="date"></span></div>
    <h1 class="disp">__SUBNAME__<small>web確認問題</small></h1>
    <p class="lead">公認会計士試験</p>
    <nav class="subj" aria-label="科目">__TABS__</nav>
  </div>
</header>
<main class="wrap">
__SECTIONS__</main>
<script>
  // 今日の日付（表紙の右上）
  (function () {
    var d = new Date(), W = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    document.getElementById("date").textContent = d.getFullYear() + "." + (d.getMonth() + 1) + "." + d.getDate() + " " + W[d.getDay()];
  })();
  // 毎回ちがう ?v= を付けて、キャッシュではなく最新の PDF・web確認問題を取りに行く。
  // web確認問題へは #les=回の名前 を付ける（回のカード＝その回だけ、web確認問題のカード＝#les= で全回）
  document.querySelectorAll("a[data-pdf], a[data-fresh]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      var les = a.getAttribute("data-les");
      location.href = a.getAttribute("href") + "?v=" + Date.now() + (les === null ? "" : "#les=" + encodeURIComponent(les));
    });
  });
  // 科目の切り替え（この端末に保存）。#sub= は読んだら URL から消す
  document.querySelectorAll(".subj button").forEach(function (b) {
    b.addEventListener("click", function () {
      document.documentElement.dataset.sub = b.dataset.sub;
      try { localStorage.setItem("kigyoho-subject", b.dataset.sub); } catch (e) {}
    });
  });
  if (/^#sub=/.test(location.hash)) {
    try { localStorage.setItem("kigyoho-subject", document.documentElement.dataset.sub); } catch (e) {}
    history.replaceState(null, "", location.pathname + location.search);
  }
  // 入口ページ自体が古いキャッシュでも、問題数は毎回最新の counts.json（科目ごと）から表示し直す
  function refreshCounts() {
    document.querySelectorAll("section[data-counts]").forEach(function (sec) {
      fetch(sec.getAttribute("data-counts") + "?v=" + Date.now(), { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (counts) {
          sec.querySelectorAll("li[data-name]").forEach(function (li) {
            var name = li.getAttribute("data-name");
            if (name in counts) li.querySelector(".n").textContent = counts[name] + "問";
          });
        })
        .catch(function () {});
    });
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
def load_web(sub):
    """問題データ（questions.csv など）を 編→章→節→問題 の木にする（回をまたいで同じ編・章・節はまとめる）。
    問題は {"lesson","no","page","q","a","adv"}。頁が空欄の問題は直前の問題の頁を使う。"""
    root = []
    lessons = []
    h1 = h2 = h3 = None
    page = ""
    lesson = ""
    with open(BASE / sub["csv"], encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["type"]
            if t == "lesson":
                lesson = r["question"]; lessons.append(lesson)
            elif t == "h1":
                h1 = next((n for n in root if n["title"] == r["question"]), None)
                if not h1:
                    h1 = {"title": r["question"], "children": [], "qs": []}; root.append(h1)
                h2 = h3 = None
            elif t == "h2":
                h2 = next((n for n in h1["children"] if n["title"] == r["question"]), None)
                if not h2:
                    h2 = {"title": r["question"], "children": [], "qs": []}; h1["children"].append(h2)
                h3 = None
            elif t == "h3":
                par = h2 or h1
                h3 = next((n for n in par["children"] if n["title"] == r["question"]), None)
                if not h3:
                    h3 = {"title": r["question"], "children": [], "qs": []}; par["children"].append(h3)
            elif t == "q":
                page = (r["page"] or "").strip() or page
                (h3 or h2 or h1)["qs"].append({"lesson": lesson, "no": r["no"], "page": page, "q": r["question"],
                                         "a": r["answer"], "adv": (r.get("level") or "").strip() == "上"})
    return root, lessons


def web_count(n):
    return len(n["qs"]) + sum(web_count(c) for c in n["children"])


def web_nodes(nodes, lv=1, parent=""):
    """lv1＝編、lv2＝章、lv3＝節。parent は1つ上の見出し（節の data-key を章ごとに分けるため）"""
    out = []
    for n in nodes:
        qs = []
        for q in n["qs"]:
            adv = '<span class="adv">上級</span>' if q["adv"] else ""
            pg = f'<span class="pg">{html.escape(q["page"])}</span>' if q["page"] else ""
            qs.append(f'<details class="q" data-l="{html.escape(q["lesson"])}"><summary><div class="qm">'
                      f'<span class="ck" data-id="q:{html.escape(q["q"])}"><i></i><i></i><i></i></span>'
                      f'<span class="no">No.{html.escape(q["no"])}</span>{pg}{adv}<span class="lad"></span></div>'
                      f'<div class="qt">{html.escape(q["q"])}</div></summary><div class="ans"><div class="atext">{q["a"]}</div>'
                      '<div class="judge"><button class="jo" data-r="o">○ できた</button>'
                      '<button class="jx" data-r="x">× できなかった</button>'
                      '<button class="jundo" data-r="">最後の印を消す</button></div></div></details>')
        inner = "".join(qs) + web_nodes(n["children"], lv + 1, n["title"])
        # 「第0編　入門生の…」の「第0編」は金色にする（狭い画面では全角スペースのところで折り返す）
        num, sp, rest = n["title"].partition("　")
        title = f'<span class="tn">{html.escape(num)}</span>{sp}{html.escape(rest)}' if sp else html.escape(n["title"])
        # .hm＝その編・章の◎の数、.hbar＝編の◎の割合の金の線（どちらも画面側で入れる）
        bar = '<i class="hbar"></i>' if lv == 1 else ''
        # 開いている見出しの記録用のキー（節は「1.　総説」のような同じ名前が別の章にも出うるので、章の名前も付ける）
        key = n["title"] if lv <= 2 else f'{parent}/{n["title"]}'
        out.append(f'<details class="h lv{lv}" data-key="h:{html.escape(key)}"><summary class="hd">'
                   f'<span class="t">{title}</span><span class="hcnt"><span class="hm"></span><span class="hn">{web_count(n)}</span>問</span>{bar}</summary>'
                   f'<div class="in">{inner}</div></details>')
    return "".join(out)


WEB_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache">
<meta name="theme-color" content="#1b2644">
<title>__NAME__ web確認問題</title>
__FONTS__
<script>
  // 文字の設定（タイトル・問題部分それぞれ s/a/c/d）と○の日付の表示を、描画の前に反映する
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
__BASE__
  body { padding-bottom: 56px; }
  /* ---- 表紙：戻る・設定・タイトル・進み具合 ---- */
  .cover { padding: 12px 0 18px; }
  .top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
  .back { display: inline-flex; align-items: center; color: var(--cream); text-decoration: none; font-size: 14px;
    padding: 8px 14px; border-radius: 999px; border: 1px solid rgba(246, 239, 223, .3); background: rgba(255, 255, 255, .05); }
  #setBtn { width: 40px; height: 40px; border-radius: 50%; border: 1px solid rgba(246, 239, 223, .3);
    background: rgba(255, 255, 255, .05); color: var(--cream); cursor: pointer;
    display: flex; align-items: center; justify-content: center; padding: 0; }
  h1 { font-size: 29px; font-weight: 700; color: #f8f2e4; margin: 0; letter-spacing: .06em; line-height: 1.3; }
  h1 em { font-family: var(--serif-en); font-style: italic; font-weight: 500; font-size: 1.15em;
    letter-spacing: 0; margin-right: .08em; color: var(--gold-l); }
  h1 .eb { display: block; font-size: 15px; margin-bottom: 2px; }
  .prog { margin-top: 16px; display: grid; grid-template-columns: 74px 1fr; grid-template-areas: "ring pm" "pa pa";
    gap: 14px 14px; align-items: center; padding: 14px 14px 12px; border-radius: 16px;
    background: rgba(255, 255, 255, .055); border: 1px solid rgba(220, 192, 138, .25); }
  .ring { grid-area: ring; position: relative; width: 74px; height: 74px; }
  .ring svg { display: block; width: 100%; height: 100%; transform: rotate(-90deg); }
  .ring circle { fill: none; stroke-width: 6; }
  .ring .tr { stroke: rgba(255, 255, 255, .13); }
  .ring .fg { stroke: url(#gold); stroke-linecap: round; stroke-dasharray: 169.65; stroke-dashoffset: 169.65;
    transition: stroke-dashoffset .9s cubic-bezier(.25, .8, .25, 1); }
  .pct { position: absolute; inset: 0; display: grid; place-items: center;
    font-family: var(--serif-en); font-weight: 600; font-size: 14px; color: #f8f2e4; }
  .pct b { font-size: 27px; font-weight: 600; line-height: 1; }
  .pm { grid-area: pm; min-width: 0; }
  .pt { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0 8px; font-size: 13px; color: rgba(246, 239, 223, .82); }
  .pt b { font-family: var(--serif-en); font-size: 30px; font-weight: 600; color: #f8f2e4; line-height: 1; }
  .seg { display: flex; height: 7px; border-radius: 4px; background: rgba(255, 255, 255, .13); overflow: hidden; margin: 9px 0 8px; }
  .seg i { display: block; height: 100%; width: 0; transition: width .7s cubic-bezier(.25, .8, .25, 1); }
  .seg .s4 { background: #6fc79a; } .seg .s3 { background: #86aee6; } .seg .s2 { background: #e6bb5e; } .seg .s1 { background: #ec8676; }
  .lg { display: flex; flex-wrap: wrap; gap: 2px 12px; font-size: 12px; color: rgba(246, 239, 223, .78); }
  .lg span { white-space: nowrap; }
  .lg b { font-weight: 700; color: #f8f2e4; margin-left: 3px; }
  .lg .s4 { color: #92d9b3; } .lg .s3 { color: #a6c4ee; } .lg .s2 { color: #efcb7f; } .lg .s1 { color: #f2a397; }
  .pa { grid-area: pa; display: flex; align-items: center; gap: 14px; }
  .today { flex: 1; display: flex; align-items: center; justify-content: space-between; gap: 10px; cursor: pointer;
    font: inherit; color: var(--cream); background: rgba(255, 255, 255, .04); border: 1px solid rgba(220, 192, 138, .55);
    border-radius: 12px; padding: 9px 14px; min-height: 46px; text-align: left; }
  .today .tl { font-size: 14px; font-weight: 700; letter-spacing: .04em; }
  .today .tv { font-size: 13px; font-weight: 700; white-space: nowrap; }
  .today .tv b { font-family: var(--serif-en); font-size: 25px; font-weight: 600; line-height: 1; margin-right: 2px; }
  .today.has { color: #1b2644; border-color: transparent; background: linear-gradient(135deg, #efd8a2 0%, #d0a865 100%);
    box-shadow: 0 6px 18px rgba(0, 0, 0, .18); }
  .today[aria-pressed=true] { outline: 2px solid #f8f2e4; outline-offset: 2px; }
  .today:disabled { cursor: default; color: var(--cream); opacity: 1; }
  .today.done .tv { color: var(--gold-l); }
  .solved { font-size: 12px; color: rgba(246, 239, 223, .78); white-space: nowrap; text-align: center; line-height: 1.3; }
  .solved b { display: block; font-family: var(--serif-en); font-size: 25px; font-weight: 600; color: #f8f2e4; line-height: 1; }
  @media (min-width: 640px) {
    .cover { padding-bottom: 22px; }
    h1 { font-size: 34px; }
    .prog { grid-template-columns: 82px 1fr 240px; grid-template-areas: "ring pm pa"; gap: 18px; padding: 16px 18px; }
    .ring { width: 82px; height: 82px; }
  }
  /* ---- 絞り込み・回・すべて開く ---- */
  .tools { padding: 16px 0 4px; }
  .frow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  .frow .lb { font-size: 13px; color: var(--ink2); min-width: 4.5em; letter-spacing: .04em; }
  .sel { position: relative; display: inline-block; }
  .sel select { -webkit-appearance: none; appearance: none; font: inherit; font-size: 15px; font-weight: 700;
    color: var(--ink); background: var(--card); border: 1px solid var(--line2); border-radius: 999px;
    padding: 8px 34px 8px 16px; cursor: pointer; box-shadow: 0 1px 2px rgba(27, 38, 68, .05); }
  .sel::after { content: "▾"; position: absolute; right: 14px; top: 50%; transform: translateY(-50%);
    color: var(--gold); pointer-events: none; font-size: 13px; }
  .sel.on select { background: var(--navy); color: var(--cream); border-color: var(--navy); }
  .sel.on::after { color: var(--gold-l); }
  .perw { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; color: var(--ink); }
  .perw[hidden] { display: none; }
  #cnt { font-size: 13px; font-weight: 700; color: var(--gold-d); }
  #cnt:empty { display: none; }
  .oc { margin-left: auto; display: flex; gap: 6px; }
  .oc button { font: inherit; font-size: 13px; padding: 7px 10px; border-radius: 999px; cursor: pointer;
    border: 1px solid var(--line2); background: transparent; color: var(--ink2); }
  /* ---- 編・章 ---- */
  summary { list-style: none; cursor: pointer; }
  summary::-webkit-details-marker { display: none; }
  .hd { position: relative; display: flex; align-items: baseline; gap: 10px; padding: 12px 14px; color: var(--ink); }
  .hd::before { content: "▸"; font-family: var(--sans); color: var(--gold); font-size: 12px; width: 12px; flex: none; transition: transform .15s; }
  details[open] > .hd::before { transform: rotate(90deg); }
  .t { flex: 1; letter-spacing: .04em; line-height: 1.5; }
  .lv1 > .hd .t, .lv2 > .hd .t { word-break: keep-all; overflow-wrap: anywhere; }   /* 編・章は全角スペースのところで折り返す */
  .tn { color: var(--gold-d); }
  .hcnt { color: var(--mute); font-size: 12px; font-weight: 400; font-family: var(--sans); white-space: nowrap; }
  .hm { color: var(--green); font-weight: 700; }
  .hbar { position: absolute; left: 0; bottom: 0; height: 2px; width: 0; border-radius: 0 2px 2px 0;
    background: linear-gradient(90deg, #e3c88f, #b8904f); transition: width .7s cubic-bezier(.25, .8, .25, 1); }
  details.lv1 { background: var(--card); border: 1px solid var(--line); border-radius: 16px; margin-bottom: 14px;
    overflow: hidden; box-shadow: var(--shadow); }
  .lv1 > .hd { font-size: 17px; padding: 15px 16px; }
  .lv1 > .in { border-top: 1px solid var(--line); padding: 6px 0 10px; }
  .lv2 > .hd { font-size: 16px; padding: 13px 14px 7px; }
  .lv3 > .hd { font-size: 15px; padding: 11px 12px 6px; gap: 8px; }   /* 節（1. 機関総説 など） */
  .lv3 > .hd::before { font-size: 11px; width: 11px; }
  .in .in { margin-left: 12px; border-left: 1px solid var(--line2); }
  /* ---- 1問 ---- */
  details.q { margin: 8px 10px; border: 1px solid var(--line); border-radius: 12px; background: #fff;
    transition: border-color .2s, box-shadow .2s; }
  details.q[open] { border-color: var(--line2); box-shadow: 0 6px 22px rgba(27, 38, 68, .08); }
  details.q > summary { padding: 10px 12px 12px; }
  .qm { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-family: var(--sans); }
  .no { font-weight: 700; color: var(--ink); font-size: 13px; letter-spacing: .02em; }
  .pg { color: var(--mute); font-size: 12px; }
  .adv { font-size: 11px; color: var(--cream); background: var(--ink); border-radius: 9px; padding: 1px 8px; letter-spacing: .06em; }
  .lad { margin-left: auto; font-size: 12px; font-weight: 700; border-radius: 999px; padding: 3px 10px; white-space: nowrap; }
  .lad:empty { display: none; }
  .lad.s1 { color: var(--red); background: #fbeae7; }
  .lad.s2 { color: var(--amber); background: #faf0d5; }
  .lad.s3 { color: var(--blue); background: #e7eff9; }
  .lad.s4 { color: var(--green); background: #e4f2ea; }
  .lad.due { color: #fff; background: linear-gradient(135deg, #c8473b, #a82b22); }
  .qt { margin-top: 9px; color: var(--ink); font-size: 16px; line-height: 1.75; letter-spacing: .02em; }
  .ans { padding: 0 10px 14px; }
  .atext { color: var(--red); font-size: 15px; line-height: 1.9; letter-spacing: .02em; background: var(--tint);
    border-radius: 10px; padding: 12px 12px 12px 13px; border-left: 3px solid rgba(179, 51, 42, .35); }
  .atext b { color: var(--red-d); background: linear-gradient(transparent 64%, rgba(240, 196, 92, .34) 64%); }
  @media (min-width: 640px) {
    .lv1 > .hd { font-size: 19px; padding: 16px 20px; }
    .lv2 > .hd { font-size: 17px; }
    .lv3 > .hd { font-size: 16px; }
    .in .in { margin-left: 16px; }
    details.q { margin: 10px 16px; }
    .ans { padding: 0 12px 14px; }
    .qt { font-size: 17px; }
    .atext { font-size: 16px; padding: 14px 18px; }
  }
  /* 判定ボタン（印はここでだけ付ける。□は表示だけ） */
  .judge { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; font-family: var(--sans); }
  .judge button { font: inherit; font-size: 15px; font-weight: 700; min-height: 46px; border-radius: 12px;
    cursor: pointer; border: 1.5px solid; transition: transform .1s; }
  .judge button:active { transform: scale(.97); }
  .judge .jo { color: var(--green); border-color: rgba(44, 122, 82, .5); background: #f0f8f3; }
  .judge .jx { color: var(--red); border-color: rgba(179, 51, 42, .45); background: #fdf1ef; }
  .judge .jundo { grid-column: 1 / -1; justify-self: end; min-height: 0; font-size: 12px; font-weight: 400;
    color: var(--mute); border: 0; background: none; padding: 4px 2px; text-decoration: underline; }
  .judge .jundo[hidden] { display: none; }
  @media (min-width: 640px) { .judge { grid-template-columns: 180px 180px 1fr; } .judge .jundo { grid-column: auto; } }
  .ans { box-sizing: border-box; overflow: hidden; }
  .in { box-sizing: border-box; overflow: hidden; }   /* overflow で中の余白の計算を開閉アニメと揃える */
  /* 閉じている編・章・問題の中身は確実に消す（Safari で閉じた中身が場所だけ取るのを防ぐ） */
  details:not([open]) > .in, details:not([open]) > .ans { display: none; }
  #none { color: var(--mute); text-align: center; padding: 28px 0; letter-spacing: .06em; }
  #none::before, #none::after { content: "—"; color: var(--gold); margin: 0 .6em; }
  .hide { display: none !important; }
  #syncStatus { font-size: 12px; color: var(--red); margin: 0 0 12px; }
  /* チェック□□□ */
  .ck { display: flex; gap: 4px; flex: none; }
  .ck i { position: relative; width: 24px; height: 24px; box-sizing: border-box; border: 1.5px solid #bdb5a6; border-radius: 6px;
    background: #fff; font-style: normal; font-weight: 700; font-size: 16px; line-height: 21px; text-align: center; }
  .ck i.x { color: var(--red); border-color: var(--red); background: #fcefed; }
  .ck i.o { color: var(--green); border-color: var(--green); background: #eef7f2; }
  .ck i.x::after { content: "×"; }
  .ck i.o::after { content: "○"; }
  /* ○を付けた日（設定で表示・非表示） */
  [data-sd=on] .ck i.o[data-d]::before { content: attr(data-d); position: absolute; top: 100%; left: 50%;
    transform: translateX(-50%); margin-top: 3px; font-size: 10px; font-weight: 400; line-height: 1;
    color: var(--green); white-space: nowrap; font-family: var(--sans); }
  [data-sd=on] .ck.hasd { margin-bottom: 13px; }
  /* 印を付けたときの小さな動き（「視差効果を減らす」がオンなら動かさない） */
  @keyframes pop { 0% { transform: scale(.5); } 55% { transform: scale(1.22); } 100% { transform: scale(1); } }
  @keyframes glow { 0% { box-shadow: 0 0 0 0 rgba(220, 192, 138, 0); } 25% { box-shadow: 0 0 0 5px rgba(220, 192, 138, .6); }
    100% { box-shadow: 0 0 0 14px rgba(220, 192, 138, 0); } }
  .pop { animation: pop .45s cubic-bezier(.3, 1.4, .5, 1); }
  details.q.glow { animation: glow 1.1s ease-out; }
  @media (prefers-reduced-motion: reduce) {
    .pop, details.q.glow { animation: none; }
    .ring .fg, .seg i, .hbar { transition: none; }
  }
  /* 文字の設定（問題部分）：s＝標準（端末のゴシック）、a＝上品な明朝、c＝手書き風、d＝クラシックな明朝 */
  [data-qf=a] #tree { font-family: "Shippori Mincho", "Hiragino Mincho ProN", serif; font-weight: 500; }
  [data-qf=c] #tree { font-family: "Klee One", serif; }
  [data-qf=d] #tree { font-family: "Zen Old Mincho", "Hiragino Mincho ProN", serif; }
  #tree .hd .t, #tree .qt, #tree b { font-weight: 700; }
  [data-qf=c] #tree .hd .t, [data-qf=c] #tree .qt, [data-qf=c] #tree b { font-weight: 600; }
  /* ---- 設定画面 ---- */
  #setting { position: fixed; inset: 0; background: rgba(16, 23, 44, .45); z-index: 10;
    display: flex; align-items: flex-start; justify-content: center; padding: 56px 16px; overflow-y: auto; }
  #setting[hidden] { display: none; }
  .sheet { background: var(--card); border-radius: 18px; width: 100%; max-width: 520px; padding: 6px 20px 20px;
    box-shadow: 0 20px 60px rgba(10, 16, 34, .35); border: 1px solid var(--line); box-sizing: border-box; }
  .sh { display: flex; align-items: center; justify-content: space-between; font-size: 20px; font-weight: 700;
    color: var(--ink); padding: 12px 0 10px; border-bottom: 1px solid var(--line); letter-spacing: .08em; }
  #setClose { font-size: 26px; line-height: 1; border: 0; background: none; color: var(--mute); cursor: pointer; padding: 4px 6px; }
  .sec { margin-top: 16px; }
  .sec .lb { font-size: 13px; color: var(--ink2); margin-bottom: 8px; letter-spacing: .04em; }
  .sec button { font-size: 16px; padding: 8px 15px; border-radius: 999px; border: 1px solid var(--line2);
    background: #fff; color: var(--ink); cursor: pointer; margin: 0 6px 8px 0; }
  .sec button.on { background: var(--navy); color: var(--cream); border-color: var(--navy); }
  .sec [data-f=s] { font-weight: 700; }
  .sec [data-f=a] { font-family: "Shippori Mincho", serif; font-weight: 700; }
  .sec [data-f=c] { font-family: "Klee One", serif; font-weight: 600; }
  .sec [data-f=d] { font-family: "Zen Old Mincho", serif; font-weight: 700; }
  .syncbox { background: var(--tint); border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px; font-size: 14px; color: var(--ink); }
  .syncbox .st { font-weight: 700; color: var(--green); }
  .syncbox .st.bad { color: var(--red); }
  .syncbox .st.wait { color: var(--mute); }
  .syncbox .sub { font-size: 12px; color: var(--ink2); margin-top: 4px; line-height: 1.6; }
  #syncNow { margin-top: 10px; }
</style>
</head>
<body>
<header class="cover">
  <div class="wrap">
    <div class="top">
      <a class="back" href="./">‹ 戻る</a>
      <button id="setBtn" aria-label="設定"><svg viewBox="0 0 24 24" width="21" height="21" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg></button>
    </div>
    <h1 class="disp"><span class="eb">__EN__ · Web Review</span>__NAME__ <em>web</em>確認問題</h1>
    <section class="prog" aria-label="進み具合">
      <div class="ring" aria-hidden="true">
        <svg viewBox="0 0 64 64"><defs><linearGradient id="gold" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f0d9a3"/><stop offset="1" stop-color="#b98f4e"/></linearGradient></defs>
          <circle class="tr" cx="32" cy="32" r="27"/><circle class="fg" id="pgRing" cx="32" cy="32" r="27"/></svg>
        <span class="pct"><span><b id="pgPct">0</b>%</span></span>
      </div>
      <div class="pm">
        <div class="pt"><span><span id="pgScope">全回</span>の習得（◎）</span><span><b id="pgDone">0</b> / <span id="pgAll">0</span>問</span></div>
        <div class="seg" aria-hidden="true"><i class="s4"></i><i class="s3"></i><i class="s2"></i><i class="s1"></i></div>
        <div class="lg" id="pgLg"><span class="s4">◎<b>0</b></span><span class="s3">○<b>0</b></span><span class="s2">△<b>0</b></span><span class="s1">✕<b>0</b></span><span>未着手<b>0</b></span></div>
      </div>
      <div class="pa">
        <button class="today" id="pgToday" aria-pressed="false"><span class="tl">今日の復習</span><span class="tv" id="pgDue"></span></button>
        <div class="solved">今日解いた<b id="pgSolved">0</b></div>
      </div>
    </section>
  </div>
</header>
<main class="wrap">
  <div class="tools" id="tools">
    <div class="frow">
      <span class="lb">絞り込み</span>
      <span class="sel"><select id="fMode" aria-label="絞り込み">
        <option value="all">すべて</option><option value="today">今日の復習</option>
        <option value="x1">×1つ以上</option><option value="x2">×2つ以上</option><option value="x3">×3つ以上</option>
        <option value="old">最終復習が…</option>
      </select></span>
      <span id="perWrap" class="perw" hidden>
        <span class="sel"><select id="oldPer" aria-label="期間">
          <option value="d3">3日</option><option value="d7">1週間</option><option value="d14">2週間</option>
          <option value="m1" selected>1ヶ月</option><option value="m2">2ヶ月</option><option value="m3">3ヶ月</option>
        </select></span>以上前</span>
    </div>
    <div class="frow">
      <span class="lb">回</span>
      <span class="sel"><select id="fLes" aria-label="回">
        <option value="">全回</option>
__LESSONS__
      </select></span>
      <span id="cnt"></span>
      <span class="oc"><button id="openAll">すべて開く</button><button id="closeAll">すべて閉じる</button></span>
    </div>
  </div>
  <p id="syncStatus" hidden></p>
  <div id="tree">
__TREE__
  </div>
  <p id="none" hidden>該当する問題はありません</p>
</main>
<div id="setting" hidden>
  <div class="sheet" role="dialog" aria-label="設定">
    <div class="sh"><span class="disp">設定</span><button id="setClose" aria-label="閉じる">×</button></div>
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
  function toggle(d) {
    var a = d.querySelector(":scope > .ans, :scope > .in");
    if (reduceMotion || !a.animate) { d.open = !d.open; return; }
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
  }
  document.querySelectorAll("details.q > summary, details.h > summary").forEach(function (sm) {
    sm.addEventListener("click", function (e) { e.preventDefault(); toggle(sm.parentNode); });
  });
  var KEY = "__LS__-web-open";
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
  var CLOUD = "__CLOUD__";   // 全端末で共通の保存先
  var MKEY = "__LS__-toc-marks", BKEY = "__LS__-backup-day";
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
    var undo = ck.closest("details.q").querySelector(".jundo");
    if (undo) undo.hidden = !v.length;
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
  // 進み具合（表紙）：選んでいる回の問題の、復習ラダーの段階ごとの数・今日の復習・今日解いた数。
  // 編・章の見出しにも、その中の◎の数（編は◎の割合の金の線も）を出す
  var RING = 2 * Math.PI * 27;
  function paintProgress() {
    var n = [0, 0, 0, 0, 0], due = 0, solved = 0, t = today(), scope = fl || "";
    document.querySelectorAll("#tree details.q").forEach(function (q) {
      var m = marks[q.querySelector(".ck").dataset.id], L = ladder(m);
      q._st = L.stage;
      if (scope && q.dataset.l !== scope) return;
      n[L.stage]++;
      if (L.due !== null && L.due <= t) due++;
      if (m && m.v.some(function (c, i) { return c && m.d[i] === t; })) solved++;
    });
    var all = n[0] + n[1] + n[2] + n[3] + n[4], r = all ? n[4] / all : 0;
    document.getElementById("pgScope").textContent = scope || "全回";
    document.getElementById("pgDone").textContent = n[4];
    document.getElementById("pgAll").textContent = all;
    document.getElementById("pgPct").textContent = Math.round(r * 100);
    var ring = document.getElementById("pgRing");
    ring.style.strokeDashoffset = RING * (1 - r);
    ring.style.opacity = r ? 1 : 0;             // 0% のときに丸い端だけが点で残らないように
    [4, 3, 2, 1].forEach(function (k) {
      document.querySelector(".seg .s" + k).style.width = (all ? n[k] / all * 100 : 0) + "%";
    });
    var lg = document.querySelectorAll("#pgLg b");
    [4, 3, 2, 1, 0].forEach(function (k, i) { lg[i].textContent = n[k]; });
    var tb = document.getElementById("pgToday");
    tb.classList.toggle("has", due > 0);
    tb.classList.toggle("done", !due && solved > 0);
    tb.setAttribute("aria-pressed", String(fm === "today"));
    tb.disabled = !due && fm !== "today";        // 復習がない日は押しても空の一覧になるだけなので押せなくする
    document.getElementById("pgDue").innerHTML = due ? "<b>" + due + "</b>問 ›" : (solved ? "完了 ✓" : "なし");
    document.getElementById("pgSolved").textContent = solved;
    document.querySelectorAll("#tree details.h").forEach(function (h) {
      // 問題数・◎の数は選んでいる回の問題だけで数える（全回なら全部）
      var qs = Array.prototype.filter.call(h.querySelectorAll("details.q"), function (q) { return !fl || q.dataset.l === fl; }), k = 0;
      qs.forEach(function (q) { if (q._st === 4) k++; });
      h.querySelector(":scope > summary .hm").textContent = k ? "◎" + k + " / " : "";
      h.querySelector(":scope > summary .hn").textContent = qs.length;
      var bar = h.querySelector(":scope > summary .hbar");
      if (bar) bar.style.width = (qs.length ? k / qs.length * 100 : 0) + "%";
    });
  }
  function paint() { cks.forEach(paintOne); paintProgress(); }
  paint();
  // 印を付けたときの小さな動き（cls のアニメーションを1回だけ。「視差効果を減らす」がオンなら動かさない）
  function flash(el, cls) {
    if (!el || reduceMotion) return;
    el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls);
    el.addEventListener("animationend", function end(e) {
      if (e.target !== el) return;
      el.classList.remove(cls); el.removeEventListener("animationend", end);
    });
  }
  var timer = null;
  // 印を付ける：答えの下の「○ できた」「× できなかった」で、次の空いている□に入れる。
  // 「最後の印を消す」で一番右の印を消す。□そのものはタップしても変わらない（タップミス対策）
  function judge(q, r) {
    var ck = q.querySelector(".ck"), id = ck.dataset.id;
    var before = ladder(marks[id]).stage;
    var m = marks[id] || { v: [], d: [] };
    var v = m.v.slice(), d = m.d.slice();
    while (v.length && !v[v.length - 1]) { v.pop(); d.pop(); }   // 後ろの空は詰める
    if (r) { v.push(r); d.push(today()); }
    else if (v.length) { v.pop(); d.pop(); }
    else return;
    marks[id] = { v: v, d: d, t: Date.now() };
    saveLocal(); paintOne(ck); paintProgress();
    if (r) {
      flash(ck.children[v.length - 1], "pop");      // 入った印がポンと出る
      if (before !== 4 && ladder(marks[id]).stage === 4) {   // ◎（復習不要）になったら、問題のまわりが金色に光る
        flash(ck.parentNode.querySelector(".lad"), "pop");
        flash(q, "glow");
      }
    }
    clearTimeout(timer); timer = setTimeout(sync, 1500);
  }
  // ○×を付けたら、画面を動かして次の問題を画面の上から3割ほど（真ん中より少し上）に持ってくる。
  // 次の問題＝いま画面に出ている問題のうち、すぐ後のもの（閉じている編・章・節の中と、絞り込みで隠れた問題は飛ばす）
  function nextQ(q) {
    var all = document.querySelectorAll("#tree details.q"), i = Array.prototype.indexOf.call(all, q);
    for (var k = i + 1; k < all.length; k++) if (all[k].getClientRects().length) return all[k];
    return null;
  }
  function goNext(q) {
    var n = nextQ(q);
    if (!n) return;
    var top = window.scrollY + n.getBoundingClientRect().top - window.innerHeight * 0.3;
    if (Math.abs(top - window.scrollY) < 8) return;
    window.scrollTo({ top: Math.max(0, top), behavior: reduceMotion ? "auto" : "smooth" });
  }
  document.querySelectorAll("details.q .judge button").forEach(function (b) {
    b.addEventListener("click", function () {
      var q = b.closest("details.q");
      judge(q, b.dataset.r);                       // 判定しても答えは開いたまま
      if (b.dataset.r) setTimeout(function () { goNext(q); }, 250);   // 印が入ったのを見てから動かす（「最後の印を消す」では動かない）
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
        await cloudPut("__BACKUP__:" + day, { marks: merged });
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
  var FKEY = "__LS__-web-filter", fm = "all", fl = "", per = document.getElementById("oldPer");
  var fMode = document.getElementById("fMode"), fLes = document.getElementById("fLes");
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
    fMode.value = fm; fLes.value = fl;
    fMode.parentNode.classList.toggle("on", fm !== "all");
    fLes.parentNode.classList.toggle("on", fl !== "");
    document.getElementById("perWrap").hidden = fm !== "old";
    document.getElementById("cnt").textContent = on ? cnt + "問" : "";
    document.getElementById("none").hidden = any;
    paintProgress();                 // 進み具合は選んでいる回について出す
    try { localStorage.setItem(FKEY, JSON.stringify({ m: fm, l: fl, p: per.value })); } catch (e) {}
  }
  fMode.onchange = function () { fm = fMode.value; applyFilter(); };
  fLes.onchange = function () { fl = fLes.value; applyFilter(); };
  per.onchange = function () { applyFilter(); };
  // 表紙の「今日の復習」：絞り込みを「今日の復習」にして一覧へ（もう一度押すと「すべて」に戻す）
  document.getElementById("pgToday").onclick = function () {
    fm = fm === "today" ? "all" : "today";
    applyFilter();
    if (fm === "today") document.getElementById("tools").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  };
  try {
    var f0 = JSON.parse(localStorage.getItem(FKEY)) || {};
    if (fMode.querySelector('option[value="' + f0.m + '"]')) fm = f0.m;
    if (f0.l === "" || fLes.querySelector('option[value="' + f0.l + '"]')) fl = f0.l || "";
    if (per.querySelector('option[value="' + f0.p + '"]')) per.value = f0.p;
  } catch (e) {}
  // 入口ページのカードから開いたとき（#les=回の名前）：回のカード→その回だけ（絞り込みは「すべて」）、
  // web確認問題のカード（#les= が空）→全回（絞り込みは前のまま）。# は読んだら消す（開き直しで絞り込みが戻らないように）
  var hl = location.hash.match(/^#les=(.*)$/);
  if (hl) {
    var want = null;
    try { want = decodeURIComponent(hl[1]); } catch (e) {}
    if (want === "") fl = "";
    else if (want !== null && Array.prototype.some.call(fLes.options, function (o) { return o.value === want; })) { fl = want; fm = "all"; }
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
  }
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


def build_web(sub):
    root, lessons = load_web(sub)
    les = "\n".join(f'      <option value="{html.escape(l)}">{html.escape(l)}</option>' for l in lessons)
    page = (WEB_HTML.replace("__FONTS__", FONTS).replace("__BASE__", BASE_CSS)
            .replace("__NAME__", sub["name"]).replace("__EN__", sub["en"]).replace("__LS__", sub["ls"])
            .replace("__CLOUD__", sub["cloud"]).replace("__BACKUP__", sub["backup"])
            .replace("__TREE__", web_nodes(root)).replace("__LESSONS__", les))
    (BASE / sub["page"]).write_text(with_version(page), encoding="utf-8")
    n = sum(web_count(x) for x in root)
    print(f"{sub['name']} web確認問題: {n}問 → {sub['page']}")
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


def build_subject(sub, chrome, tmp):
    """科目ごとに、回の PDF・web確認問題のページ・問題数（counts）を作り、入口ページのその科目の部分を返す"""
    lessons = load(sub)
    items = []
    counts = {}
    pages = 0  # ここまでの回のページ数の合計
    for name, data in lessons:
        fname = f"{sub['pdf']}_{name}.pdf"
        tmp.write_text(render(sub, name, data, pages), encoding="utf-8")
        subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer", f"--print-to-pdf={PDF_DIR / fname}",
                        tmp.as_uri()], check=True, capture_output=True)
        pages += len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", (PDF_DIR / fname).read_bytes()))
        nq = sum(1 for r in data if r[0] not in ("h1", "h2"))
        num = re.search(r"\d+", name)  # 「第3回」→ 03（入口ページの金の数字）
        ln = f"{int(num.group()):02d}" if num else "·"
        # カードの左＝その回だけに絞り込んだ web確認問題、右端の PDF＝その回の PDF
        items.append(f'    <li data-name="{html.escape(name)}"><a class="lm" data-fresh data-les="{html.escape(name)}" href="{sub["page"]}">'
                     f'<span class="ln">{ln}</span><span class="lt"><span class="lname disp">{html.escape(name)}</span>'
                     f'<span class="n">{nq}問</span></span></a>'
                     f'<a class="lpw" data-pdf href="pdf/{html.escape(fname)}" aria-label="{html.escape(name)}の PDF"><span class="lp">PDF</span></a></li>')
        counts[name] = nq
        print(f"{sub['name']} {name}: {nq}問 → pdf/{fname}")
    nweb = build_web(sub)
    (BASE / sub["counts"]).write_text(json.dumps(counts, ensure_ascii=False) + "\n", encoding="utf-8")
    feat = (f'  <a class="feat" data-fresh data-les="" href="{sub["page"]}"><span class="fe">Web Review</span>'
            f'<span class="ft disp">{sub["name"]} <em>web</em>確認問題</span><span class="fd">1問ずつ答えを開いて、○×で復習</span>'
            f'<span class="fn"><b>{nweb}</b>問</span></a>\n')
    if items:
        lst = '  <ul class="les">\n' + "\n".join(items) + '\n  </ul>\n'
    else:
        lst = '  <p class="empty">まだ問題がありません</p>\n'
    return (f'<section class="only" data-sub="{sub["id"]}" data-counts="{sub["counts"]}">\n{feat}'
            '  <h2 class="lh"><span class="eb">Lessons</span><span class="disp">授業の回</span><small>選ぶと web確認問題が開きます</small></h2>\n'
            f'{lst}</section>\n')


def main():
    check_font()
    chrome = next(c for c in ["google-chrome", "chromium", "chromium-browser",
                              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
                  if shutil.which(c) or pathlib.Path(c).exists())
    if PDF_DIR.exists():
        shutil.rmtree(PDF_DIR)  # 消した回の PDF が残らないように作り直す
    PDF_DIR.mkdir()
    tmp = BASE / "kigyoho.html"
    sections = "".join(build_subject(sub, chrome, tmp) for sub in SUBJECTS)
    if tmp.exists():
        tmp.unlink()
    # 科目の切り替え：選んでいる科目（<html data-sub>）の部分だけを出し、タブを金色にする
    subcss = "".join(
        f'  html[data-sub="{x["id"]}"] .only:not([data-sub="{x["id"]}"]) {{ display: none; }}\n'
        f'  html[data-sub="{x["id"]}"] .subj button[data-sub="{x["id"]}"] {{ color: #1b2644;'
        ' background: linear-gradient(135deg, #efd8a2 0%, #d0a865 100%); box-shadow: 0 4px 12px rgba(0, 0, 0, .18); }\n'
        for x in SUBJECTS)
    tabs = "".join(f'<button class="disp" data-sub="{x["id"]}">{x["name"]}</button>' for x in SUBJECTS)
    en = "".join(f'<span class="eb only" data-sub="{x["id"]}">{x["en"]}</span>' for x in SUBJECTS)
    name = "".join(f'<span class="only" data-sub="{x["id"]}">{x["name"]}</span>' for x in SUBJECTS)
    page = (INDEX.replace("__FONTS__", FONTS).replace("__BASE__", BASE_CSS)
            .replace("__SUBIDS__", json.dumps([x["id"] for x in SUBJECTS])).replace("__SUBCSS__", subcss)
            .replace("__SUBEN__", en).replace("__SUBNAME__", name).replace("__TABS__", tabs)
            .replace("__SECTIONS__", sections))
    (BASE / "index.html").write_text(with_version(page), encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main()

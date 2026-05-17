"""budgetbook-demo を静的 HTML として吸い出し、Cloudflare Pages 公開可能な形に整える。

前提: budgetbook-demo の runserver が DEMO_MODE=1 + DEMO_AUTO_LOGIN=1 で
http://127.0.0.1:8765/ で起動していること。

セキュリティ方針:
- POST/PUT/DELETE を伴うフォームと hx-* ミューテーションを HTML 上で無効化
- 「閲覧専用ポートフォリオ」バナーを全ページ上部に挿入
- 内部リンクは相対化、外部ドメインへの絶対 URL は保持
- service worker / manifest は静的化に不要なため除外

期間切替:
- 月単位ページ (dashboard, balance-sheet, budgets) は直近 12 ヶ月分を生成
- 年単位ページ (annual, medical, insurance, tax-deductions) は直近 3 年分を生成
- 両軸ページ (expense-breakdown) は 12 ヶ月 + 3 年の十字を生成
- prev/next ?month=YYYY-MM / ?year=YYYY 形式のリンクを生成済み変種への相対パスへ書き換え
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "http://127.0.0.1:8765"
OUT = Path(__file__).resolve().parent.parent / "public"

MONTHS_BACK = 12  # 含む現在月
YEARS_BACK = 3    # 含む現在年

PAGE_DEFS = [
    {"url": "/", "out": "index.html", "period": "month"},
    {"url": "/annual/", "out": "annual/index.html", "period": "year"},
    {"url": "/balance-sheet/", "out": "balance-sheet/index.html", "period": "month"},
    {"url": "/loan-strategy/", "out": "loan-strategy/index.html", "period": None},
    {"url": "/budgets/", "out": "budgets/index.html", "period": "month"},
    {"url": "/sections/", "out": "sections/index.html", "period": None},
    {"url": "/expense-breakdown/", "out": "expense-breakdown/index.html", "period": "both"},
    {"url": "/reports/tax-deductions/", "out": "reports/tax-deductions/index.html", "period": "year"},
    {"url": "/reports/tax-deductions/v2/", "out": "reports/tax-deductions/v2/index.html", "period": "year"},
    {"url": "/medical-expenses/", "out": "medical-expenses/index.html", "period": "year"},
    {"url": "/insurance-premiums/", "out": "insurance-premiums/index.html", "period": "year"},
    {"url": "/accounting/", "out": "accounting/index.html", "period": None},
    {"url": "/settings/", "out": "settings/index.html", "period": None},
    {"url": "/settings/login-history/", "out": "settings/login-history/index.html", "period": None},
    {"url": "/settings/income-snapshots/", "out": "settings/income-snapshots/index.html", "period": None},
]

STATIC_BANNER_HTML = """
<div id="static-portfolio-banner" class="static-banner">
  📸 これは <strong>静的スナップショット (Cloudflare Pages 配信)</strong> です。閲覧専用 — 入力・編集・削除は無効化されています。<a href="https://github.com/NucoNekoSan/budgetbook-demo" class="static-banner__link">ソースコード (GitHub)</a>
</div>
"""

MSG_DEMO = "閲覧専用デモです (静的スナップショット)"
MSG_NOT_MIRRORED = "このページは静的スナップショットには含まれていません"
MSG_CSV = "CSV ダウンロードは静的版では無効です"

session = requests.Session()
session.headers.update({"User-Agent": "budgetbook-mirror/1.0"})

fetched_assets: dict[str, Path] = {}


def login_as_demo() -> None:
    """demo ユーザーで明示的にログインしてセッション cookie を確立する。

    DEMO_AUTO_LOGIN middleware に頼らずここで確実にログインしておくことで、
    その後の全 GET が認証済みリクエストとして発行される。
    middleware が動かないケース (DB タイミング / 設定漏れ / 将来の middleware 変更)
    でも mirror が壊れない保険として機能する。

    demo ユーザーは `seed_demo_data --reset` で必ず作成される (password='demo')。
    DEMO_MODE=1 + DEMO_ALLOW_WRITES=0 なので POST/PUT/DELETE は middleware で
    403 ブロックされ、書き込みは絶対に発生しない。
    """
    login_url = BASE + "/accounts/login/"
    # CSRF token を先に取得
    r = session.get(login_url, allow_redirects=False)
    if r.status_code != 200:
        raise RuntimeError(f"login page fetch failed: HTTP {r.status_code}")
    m = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', r.text)
    if not m:
        raise RuntimeError("CSRF token not found on login page")
    csrf = m.group(1)
    # ログイン POST (next=/)
    r2 = session.post(
        login_url,
        data={
            "csrfmiddlewaretoken": csrf,
            "username": "demo",
            "password": "demo",
            "next": "/",
        },
        headers={"Referer": login_url},
        allow_redirects=False,
    )
    print(f"[mirror][login] POST status={r2.status_code} location={r2.headers.get('Location', '-')}")
    print(f"[mirror][login] session cookies after POST: {list(session.cookies.keys())}")
    # 成功時は 302 (next=/) にリダイレクト
    if r2.status_code == 200:
        # フォームが再表示された = エラー (CSRF / 認証 / axes ロックアウト)
        # body から errorlist 系を広めに抽出
        errs = re.findall(r'<(?:ul|li|div|p)[^>]*(?:error|alert|warning)[^>]*>(.*?)</(?:ul|li|div|p)>', r2.text, re.IGNORECASE | re.DOTALL)
        err_text = ' | '.join(re.sub(r'\s+', ' ', e.strip())[:200] for e in errs[:5]) if errs else '(no error markup)'
        print(f"[mirror][login] BODY (first 800 chars):\n{r2.text[:800]}\n--- END BODY ---")
        raise RuntimeError(f"login POST returned 200 (form re-displayed). Errors: {err_text}")
    if r2.status_code != 302:
        raise RuntimeError(f"login POST failed: HTTP {r2.status_code}")
    # セッションが本当に確立できたか確認
    r3 = session.get(BASE + "/", allow_redirects=False)
    print(f"[mirror][login] GET / after login: status={r3.status_code} location={r3.headers.get('Location', '-')}")
    if r3.status_code == 302 and "/accounts/login" in r3.headers.get("Location", ""):
        raise RuntimeError("login did not establish session (still redirecting to /accounts/login)")
    print("[mirror] demo user logged in successfully")


def months_back_list(n: int) -> list[tuple[date, str]]:
    today = date.today()
    cur = today.replace(day=1)
    out = []
    y, m = cur.year, cur.month
    for _ in range(n):
        out.append((date(y, m, 1), f"{y:04d}-{m:02d}"))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return out


def years_back_list(n: int) -> list[tuple[int, str]]:
    today = date.today()
    return [(y, str(y)) for y in range(today.year, today.year - n, -1)]


def _suffix_into_out(base_out: str, suffix_dir: str) -> str:
    """Insert suffix_dir before /index.html or .html to form a per-variant path."""
    if base_out.endswith("/index.html"):
        return base_out[: -len("/index.html")] + "/" + suffix_dir + "/index.html"
    if base_out == "index.html":
        return suffix_dir + "/index.html"
    if base_out.endswith(".html"):
        return base_out[: -len(".html")] + "/" + suffix_dir + "/index.html"
    return base_out.rstrip("/") + "/" + suffix_dir + "/index.html"


def build_variants() -> list[dict]:
    variants: list[dict] = []
    for page in PAGE_DEFS:
        period = page["period"]
        if period is None:
            variants.append({"url": page["url"], "qs": "", "out": page["out"]})
            continue
        if period == "month":
            for i, (_, ym) in enumerate(months_back_list(MONTHS_BACK)):
                if i == 0:
                    variants.append({"url": page["url"], "qs": "", "out": page["out"]})
                else:
                    variants.append({"url": page["url"], "qs": f"month={ym}", "out": _suffix_into_out(page["out"], ym)})
            continue
        if period == "year":
            for i, (_, ys) in enumerate(years_back_list(YEARS_BACK)):
                if i == 0:
                    variants.append({"url": page["url"], "qs": "", "out": page["out"]})
                else:
                    variants.append({"url": page["url"], "qs": f"year={ys}", "out": _suffix_into_out(page["out"], ys)})
            continue
        if period == "both":
            variants.append({"url": page["url"], "qs": "", "out": page["out"]})
            for i, (_, ym) in enumerate(months_back_list(MONTHS_BACK)):
                if i == 0:
                    continue
                variants.append({"url": page["url"], "qs": f"month={ym}", "out": _suffix_into_out(page["out"], "m-" + ym)})
            for i, (_, ys) in enumerate(years_back_list(YEARS_BACK)):
                if i == 0:
                    continue
                variants.append({"url": page["url"], "qs": f"year={ys}", "out": _suffix_into_out(page["out"], "y-" + ys)})
    return variants


VARIANTS = build_variants()

# variant_index: (url_path_without_trailing_slash, key_tuple) -> out_path
#   key_tuple is None for the default variant, ("month", "YYYY-MM") or ("year", "YYYY")
variant_index: dict[tuple, str] = {}
for v in VARIANTS:
    path_key = v["url"].rstrip("/")
    if not v["qs"]:
        variant_index[(path_key, None)] = v["out"]
    else:
        k, val = v["qs"].split("=", 1)
        variant_index[(path_key, (k, val))] = v["out"]


def resolve_local_target(parsed_url) -> str | None:
    path_key = parsed_url.path.rstrip("/")
    qs = parse_qs(parsed_url.query)
    has_period = "month" in qs or "year" in qs
    if "month" in qs:
        key = (path_key, ("month", qs["month"][0]))
        if key in variant_index:
            return variant_index[key]
    if "year" in qs:
        key = (path_key, ("year", qs["year"][0]))
        if key in variant_index:
            return variant_index[key]
    # 期間パラメータが付いているのに variant が無い場合は範囲外。
    # default にフォールバックさせず、neutralize する。
    if has_period:
        return None
    key = (path_key, None)
    if key in variant_index:
        return variant_index[key]
    return None


def fetch_asset(asset_url: str, html_dir: Path) -> str | None:
    parsed = urlparse(asset_url)
    if parsed.netloc and parsed.netloc not in ("127.0.0.1:8765", "localhost:8765", ""):
        return None
    path = parsed.path
    if not path or path == "/":
        return None
    if asset_url in fetched_assets:
        target = fetched_assets[asset_url]
    else:
        full = urljoin(BASE, asset_url)
        try:
            r = session.get(full, timeout=10)
        except Exception as e:
            print(f"  asset fail {asset_url}: {e}")
            return None
        if r.status_code != 200:
            print(f"  asset {r.status_code}: {asset_url}")
            return None
        target = OUT / path.lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)
        fetched_assets[asset_url] = target
        print(f"  asset saved: {path}")
    try:
        return os.path.relpath(target, html_dir).replace("\\", "/")
    except ValueError:
        return path


def neutralize_html(html: str, html_dir: Path) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # 1. 全 form の action を無効化（インラインJSは使わず data 属性のみ）
    for form in soup.find_all("form"):
        form["action"] = "#"
        form["data-neutralize"] = MSG_DEMO
        form.attrs.pop("onsubmit", None)
        form.attrs.pop("hx-post", None)
        form.attrs.pop("hx-put", None)
        form.attrs.pop("hx-patch", None)
        form.attrs.pop("hx-delete", None)

    # 2. mutation 系 hx-* 属性を全削除 + hx-headers (CSRF token 漏洩) を除去
    for tag in soup.find_all(True):
        for attr in list(tag.attrs.keys()):
            if attr in ("hx-post", "hx-put", "hx-patch", "hx-delete", "hx-confirm", "hx-headers",
                        "hx-get", "hx-push-url", "hx-swap", "hx-target", "hx-trigger", "hx-vals",
                        "hx-include", "hx-select", "hx-boost"):
                del tag.attrs[attr]

    # 2b. CSRF トークン input を削除（静的サイトでは無効・サーバ側 SECRET_KEY 由来のノイズを除去）
    for inp in soup.find_all("input", attrs={"name": "csrfmiddlewaretoken"}):
        inp.decompose()

    # 2c. PWA / Service Worker 系を除去（静的サイトでは /sw.js が無く 404 を撒く）
    for s in soup.find_all("script", src=re.compile(r"pwa_register\.js|service.?worker", re.I)):
        s.decompose()

    # 2d. nonce 属性は CSP nonce (SECRET_KEY 由来) の漏洩。静的化後は無意味。
    for tag in soup.find_all(True):
        if tag.has_attr("nonce"):
            del tag.attrs["nonce"]

    # 2e. apple-mobile-web-app-capable は deprecated。標準名を併記して警告消去。
    apple = soup.find("meta", attrs={"name": "apple-mobile-web-app-capable"})
    if apple and not soup.find("meta", attrs={"name": "mobile-web-app-capable"}):
        std = soup.new_tag("meta")
        std["name"] = "mobile-web-app-capable"
        std["content"] = apple.get("content", "yes")
        apple.insert_after(std)

    # 3. service worker 登録スクリプトを無効化
    for script in soup.find_all("script"):
        if script.string and ("serviceWorker" in script.string or "registerServiceWorker" in script.string):
            script.string = "/* SW disabled for static snapshot */"

    # 4. PWA manifest link 削除 (静的化で意味なし)
    for link in soup.find_all("link", rel="manifest"):
        link.decompose()

    # 5. CSS / JS / 画像のローカルアセットを取得して相対参照に
    for tag, attr in [("link", "href"), ("script", "src"), ("img", "src")]:
        for el in soup.find_all(tag):
            url = el.get(attr)
            if not url:
                continue
            if url.startswith(("data:", "#", "javascript:", "mailto:", "http://", "https://")):
                if url.startswith(("http://127.0.0.1:8765", "http://localhost:8765")):
                    new = fetch_asset(url, html_dir)
                    if new:
                        el[attr] = new
                continue
            if url.startswith("/"):
                new = fetch_asset(url, html_dir)
                if new:
                    el[attr] = new

    # 6. 内部 <a href="/..."> を相対 path に書き換え (静的サイトでクリック可能に)
    #    querystring の month / year を見て、対応する variant が生成済みなら相対パスへ。
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href or not href.startswith("/"):
            continue
        parsed = urlparse(href)
        target_rel = resolve_local_target(parsed)
        if target_rel is not None:
            target_path = OUT / target_rel
            rel = os.path.relpath(target_path, html_dir).replace("\\", "/")
            a["href"] = rel
        else:
            a["href"] = "#"
            a.attrs.pop("onclick", None)
            a["data-neutralize"] = MSG_NOT_MIRRORED
            a["class"] = (a.get("class") or []) + ["is-neutralized"]

    # 7. CSV download link も無効化 (Django view が動かないので)
    for a in soup.find_all("a", href=re.compile(r"\.csv$|/transactions/export/")):
        a["href"] = "#"
        a.attrs.pop("onclick", None)
        a["data-neutralize"] = MSG_CSV

    # 8. 静的バナーを <body> の直後に挿入
    body = soup.find("body")
    if body:
        banner = BeautifulSoup(STATIC_BANNER_HTML, "html.parser")
        body.insert(0, banner)

    # 9. 中立化ハンドラの外部 JS をページ末尾で読み込む（CSP unsafe-inline 不要に）
    if body:
        rel_js = os.path.relpath(OUT / "static" / "js" / "neutralize.js", html_dir).replace("\\", "/")
        rel_css = os.path.relpath(OUT / "static" / "css" / "static-banner.css", html_dir).replace("\\", "/")
        head = soup.find("head")
        if head:
            css_link = soup.new_tag("link", rel="stylesheet", href=rel_css)
            head.append(css_link)
        script_tag = soup.new_tag("script", src=rel_js, defer="")
        body.append(script_tag)

    return str(soup)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # 全ページ取得前に demo ユーザーで明示的ログイン (中間 middleware に依存しない)
    login_as_demo()
    print(f"=== mirror to {OUT} ({len(VARIANTS)} variants) ===")
    for v in VARIANTS:
        url_path = v["url"]
        qs = v["qs"]
        out_rel = v["out"]
        full = BASE + url_path + (("?" + qs) if qs else "")
        print(f"\n[{url_path}{('?' + qs) if qs else ''}] -> {out_rel}")
        try:
            r = session.get(full, timeout=15)
        except Exception as e:
            print(f"  ERROR {e}")
            continue
        if r.status_code != 200:
            print(f"  SKIP status={r.status_code}")
            continue
        out_path = OUT / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        neutralized = neutralize_html(r.text, out_path.parent)
        out_path.write_text(neutralized, encoding="utf-8")
        print(f"  saved ({len(neutralized):,} bytes)")
        time.sleep(0.1)

    print(f"\n=== done. {len(fetched_assets)} assets, {len(VARIANTS)} variants ===")


if __name__ == "__main__":
    main()

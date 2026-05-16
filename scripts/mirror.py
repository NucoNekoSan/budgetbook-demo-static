"""budgetbook-demo を静的 HTML として吸い出し、Cloudflare Pages 公開可能な形に整える。

前提: budgetbook-demo の runserver が DEMO_MODE=1 + DEMO_AUTO_LOGIN=1 で
http://127.0.0.1:8765/ で起動していること。

セキュリティ方針:
- POST/PUT/DELETE を伴うフォームと hx-* ミューテーションを HTML 上で無効化
- 「閲覧専用ポートフォリオ」バナーを全ページ上部に挿入
- 内部リンクは相対化、外部ドメインへの絶対 URL は保持
- service worker / manifest は静的化に不要なため除外
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

BASE = "http://127.0.0.1:8765"
OUT = Path(__file__).resolve().parent.parent / "public"

# 静的化する GET ページ (curated)
PAGES = [
    ("/", "index.html"),
    ("/annual/", "annual/index.html"),
    ("/balance-sheet/", "balance-sheet/index.html"),
    ("/loan-strategy/", "loan-strategy/index.html"),
    ("/budgets/", "budgets/index.html"),
    ("/sections/", "sections/index.html"),
    ("/expense-breakdown/", "expense-breakdown/index.html"),
    ("/reports/tax-deductions/", "reports/tax-deductions/index.html"),
    ("/reports/tax-deductions/v2/", "reports/tax-deductions/v2/index.html"),
    ("/medical-expenses/", "medical-expenses/index.html"),
    ("/insurance-premiums/", "insurance-premiums/index.html"),
    ("/accounting/", "accounting/index.html"),
    ("/settings/", "settings/index.html"),
    ("/settings/login-history/", "settings/login-history/index.html"),
    ("/settings/income-snapshots/", "settings/income-snapshots/index.html"),
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


def fetch_asset(asset_url: str, html_dir: Path) -> str | None:
    """静的アセットをダウンロードし、HTML から相対参照できる pathを返す。"""
    parsed = urlparse(asset_url)
    if parsed.netloc and parsed.netloc not in ("127.0.0.1:8765", "localhost:8765", ""):
        return None  # 外部ドメインはそのまま
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
    # html_dir からの相対パスを計算
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
            if attr in ("hx-post", "hx-put", "hx-patch", "hx-delete", "hx-confirm", "hx-headers"):
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
    page_map = {p[0].rstrip("/"): p[1] for p in PAGES}
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href or not href.startswith("/"):
            continue
        # クエリやフラグメント分離
        parsed = urlparse(href)
        key = parsed.path.rstrip("/")
        if key == "":
            key = ""  # root
        if key in page_map or parsed.path == "/":
            target_file = page_map.get(key, "index.html")
            target_path = OUT / target_file
            rel = os.path.relpath(target_path, html_dir).replace("\\", "/")
            a["href"] = rel
        else:
            # 該当ページがミラー外 (例: /transactions/123/edit/) → クリック無効化
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
    print(f"=== mirror to {OUT} ===")
    for url_path, out_rel in PAGES:
        full = BASE + url_path
        print(f"\n[{url_path}] -> {out_rel}")
        r = session.get(full, timeout=15)
        if r.status_code != 200:
            print(f"  SKIP status={r.status_code}")
            continue
        out_path = OUT / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        neutralized = neutralize_html(r.text, out_path.parent)
        out_path.write_text(neutralized, encoding="utf-8")
        print(f"  saved ({len(neutralized):,} bytes)")
        time.sleep(0.2)

    print(f"\n=== done. {len(fetched_assets)} assets fetched ===")


if __name__ == "__main__":
    main()

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
OUT = Path(r"C:\dev\budgetbook-demo-static\public")

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
<div id="static-portfolio-banner" style="background:#0d6efd;color:#fff;padding:8px 16px;font-size:13px;text-align:center;font-family:system-ui,sans-serif;position:relative;z-index:9999;">
  📸 これは <strong>静的スナップショット (Cloudflare Pages 配信)</strong> です。閲覧専用 — 入力・編集・削除は無効化されています。<a href="https://github.com/NucoNekoSan/budgetbook-demo" style="color:#fff;text-decoration:underline;">ソースコード (GitHub)</a>
</div>
"""

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

    # 1. 全 form の action を無効化
    for form in soup.find_all("form"):
        form["action"] = "#"
        form["onsubmit"] = "alert('閲覧専用デモです (静的スナップショット)'); return false;"
        form.attrs.pop("hx-post", None)
        form.attrs.pop("hx-put", None)
        form.attrs.pop("hx-patch", None)
        form.attrs.pop("hx-delete", None)

    # 2. mutation 系 hx-* 属性を全削除
    for tag in soup.find_all(True):
        for attr in list(tag.attrs.keys()):
            if attr in ("hx-post", "hx-put", "hx-patch", "hx-delete", "hx-confirm"):
                del tag.attrs[attr]

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
            existing_onclick = a.get("onclick", "")
            a["onclick"] = "alert('このページは静的スナップショットには含まれていません'); return false;"
            a["style"] = (a.get("style") or "") + ";cursor:not-allowed;opacity:0.6;"

    # 7. CSV download link も無効化 (Django view が動かないので)
    for a in soup.find_all("a", href=re.compile(r"\.csv$|/transactions/export/")):
        a["href"] = "#"
        a["onclick"] = "alert('CSV ダウンロードは静的版では無効です'); return false;"

    # 8. 静的バナーを <body> の直後に挿入
    body = soup.find("body")
    if body:
        banner = BeautifulSoup(STATIC_BANNER_HTML, "html.parser")
        body.insert(0, banner)

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

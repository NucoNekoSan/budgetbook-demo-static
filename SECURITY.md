# Security Policy

`budgetbook-demo-static` は **動的バックエンドを持たない静的スナップショット** です。攻撃面を構造的にゼロへ寄せる設計のため、脅威モデルと対象範囲を以下に明示します。

## 脅威モデル (Threat Model)

### In Scope — 報告を歓迎する対象

| 領域 | 想定リスク |
|---|---|
| `public/_headers` の CSP / HSTS / COOP / CORP / X-Frame-Options 設定不備 | header bypass / clickjacking / MITM |
| `public/static/js/neutralize.js` のクリック・送信ハンドラ | event handler 逃れ、`innerHTML` inject 経由の XSS |
| `scripts/mirror.py` のサーバ間 fetch | SSRF, open redirect, 機微情報の出力 leak |
| `scripts/audit_docs_sensitive.sh` の検出パターン漏れ | PII / SECRET\_KEY 由来値 / CSRF token の混入 |
| `.github/workflows/*` の権限・サプライチェーン | excess permissions, untrusted action consumption |
| `public/_fragments/*.html` の中立化漏れ | `<script>` / `on*` / nonce / csrfmiddlewaretoken 残存 |

### Out of Scope — 対象外

- **動的バックエンドの脆弱性**: 本 repo にサーバサイドコードは存在しません。Django 本体の脆弱性は別 repo [`budgetbook-demo`](https://github.com/NucoNekoSan/budgetbook-demo) にご報告ください。
- **Cloudflare Pages / Workers 自体の脆弱性**: Cloudflare の [HackerOne プログラム](https://hackerone.com/cloudflare) へ。
- **コンテンツの体裁 / UI バグ**: GitHub Issues で OK。

## 防御の多層構造 (Defense in Depth)

| 層 | 役割 |
|---|---|
| `scripts/mirror.py` の `_scrub_security` | 生成時に `<script>` / `on*` handler / nonce / `csrfmiddlewaretoken` / pwa\_register / PWA manifest を物理削除 |
| `ALLOWED_HOSTS` + `allow_redirects=False` (mirror.py) | CI runner からの SSRF / 30x で外部ホストへの逸脱を遮断 |
| pre-commit hook (`scripts/install_git_hooks.sh`) | denylist (実値) + 構造的 PII 正規表現で commit を block |
| `.github/workflows/refresh-mirror.yml` の verify step | hook bypass されても CI で再検査 |
| `.github/workflows/codeql.yml` | Python + JavaScript を `security-extended` で週次走査 |
| `public/_headers` (CF Pages) | CSP `default-src 'self'`, `script-src 'self'`, `connect-src 'self'`, `form-action 'none'`, `frame-ancestors 'none'` + HSTS + COOP + CORP + Permissions-Policy 全絞り |
| Cloudflare edge | runtime ゼロ。RCE / SQLi / CSRF が構造的に成立しない |

## 報告方法

脆弱性を発見した場合は **public issue ではなく** GitHub の Private Vulnerability Reporting を利用してください:

1. https://github.com/NucoNekoSan/budgetbook-demo-static/security/advisories/new
2. または、 [GitHub プロフィール](https://github.com/NucoNekoSan) 記載の連絡先

報告内容に含めてほしい情報:

- 影響範囲 (どのファイル / どの header / どの workflow か)
- 再現手順
- 想定される impact (例: SECRET\_KEY 由来値の leak、SSRF、XSS、CSP bypass)

## 応答 SLA

| 項目 | 目安 |
|---|---|
| 受信確認 | 5 営業日以内 |
| 影響評価 | 14 日以内 |
| 修正 commit + redeploy | 重要度に応じ 7〜30 日 |
| 公開 (advisory) | 修正後 + 報告者の合意 |

本 repo は個人ポートフォリオ用途のため、応答は best-effort です。緊急性が高い問題は連絡時にその旨を明記してください。

## 既知の前提

- demo データはすべて `seed_demo_data` による **合成データ** で、現実の個人情報を含みません。
- `static/django_htmx`, `static/vendor` は upstream の生成済 JS を mirror したもので、本 repo では中身の改変・脆弱性対応を行いません (upstream にご連絡ください)。
- Cloudflare Workers は `.html` 拡張子を URL から strip し 307 redirect します (`/path.html` → `/path`)。動作仕様であり脆弱性ではありません。
# budgetbook-demo-static

`budgetbook-demo` の **静的スナップショット** — Cloudflare Pages で 24/7 公開する読み取り専用デモ。

- **ライブ URL**: https://budgetbook-demo-static.nuconekosan.workers.dev/
- **本体リポジトリ (動的 Django アプリ)**: https://github.com/NucoNekoSan/budgetbook-demo
- **構成**: HTML/CSS/JS の静的ファイルのみ + 編集画面表示用 HTML フラグメント。Django ランタイム不要。
- **セキュリティポリシー**: [`SECURITY.md`](SECURITY.md)

## なぜ静的化するのか

セキュリティ最優先のため:

1. **攻撃面ゼロ** — サーバサイドコードが存在しないので RCE / SQL injection / CSRF が構造的に成立しない
2. **CVE 影響なし** — Django / 依存パッケージの脆弱性が出ても無関係
3. **永続無料** — Cloudflare Pages 無料枠、規約変更耐性高
4. **常時稼働** — cold start なし、全世界 CDN edge から配信

ポートフォリオ用途では「画面遷移できる + GitHub でコードが読める」で必要十分。

## 機能

- **画面遷移**: ダッシュボード / B/S / 確定申告レポート / 予算 / 医療費 / 保険料 など 15 ページ
- **期間切替**: 月単位ページは直近 12 ヶ月、年単位ページは直近 3 年、両軸ページ (expense-breakdown) は 12 × 3 で合計 **71 variants** を生成
- **編集画面の閲覧**: 「編集」ボタンを押すと、動的版で表示される編集フォームが **モーダルで開いて実データ付きで表示** される (入力可、保存は不可)
- **削除 / 新規追加ボタン**: 押すとモーダルで「閲覧専用デモ」と説明 (操作不能)
- **テーマ**: ライト / ダーク / 自動 (システム追従)

## アーキテクチャ

```
budgetbook-demo (動的 Django, 別 repo)
        │
        │  .github/workflows/refresh-mirror.yml
        │  毎週月曜 00:00 UTC + workflow_dispatch
        ▼
  ┌─────────────────────────────────────────────┐
  │ 1. checkout budgetbook-demo                 │
  │ 2. migrate + seed_demo_data --reset         │
  │    --create-demo-users (合成データのみ)     │
  │ 3. runserver :8765                          │
  │    DEMO_MODE=1 / DEMO_ALLOW_WRITES=0        │
  │    DEMO_AUTO_LOGIN=1                        │
  │ 4. scripts/mirror.py → public/              │
  │    - 71 variants 生成 (期間切替対応)        │
  │    - 編集フォームを fragments/ に事前 fetch │
  │ 5. 構造的 PII grep verify (CI 側 2 層目)    │
  │ 6. git push (差分あれば)                    │
  └─────────────────────────────────────────────┘
        │
        ▼
  Cloudflare Pages auto-deploy (git push hook)
        │
        ▼
  https://budgetbook-demo-static.nuconekosan.workers.dev/
```

### 構成

```
public/                 Cloudflare Pages 配信ルート
  *.html                15 ページ × 期間 variants = 71 HTML ファイル
  _fragments/           編集画面 HTML (data-fragment-url から fetch される)
  static/               CSS / JS / icons / vendor
  _headers              セキュリティヘッダ (CSP / HSTS / X-Frame-Options 等)
scripts/
  mirror.py             動的 demo から静的 HTML を生成、fragment も保存
  audit_docs_sensitive.sh  pre-commit / CI から呼ばれる PII 検出
  install_git_hooks.sh  pre-commit hook をインストール
.github/workflows/
  refresh-mirror.yml    weekly + workflow_dispatch で mirror を再生成
  codeql.yml            Python + JavaScript の security-extended 走査
LICENSE                 MIT
SECURITY.md             脆弱性報告と脅威モデル
```

## セキュリティ防御の多層構造

詳細は [`SECURITY.md`](SECURITY.md) を参照。要約:

| 層 | 役割 |
|---|---|
| `_scrub_security` (mirror.py) | `<script>` / `on*` / nonce / CSRF token / pwa\_register を物理削除 |
| `ALLOWED_HOSTS` + `allow_redirects=False` | fragment fetch の SSRF / 30x 逸脱を防御 |
| pre-commit + CI verify (二層) | 実値 denylist + 構造的 PII で漏出を block |
| CodeQL | Python + JS を security-extended で週次走査 |
| `public/_headers` | CSP `default-src 'self'` / `script-src 'self'` / `connect-src 'self'` / `form-action 'none'` / `frame-ancestors 'none'` + HSTS + COOP + CORP + Permissions-Policy |
| Cloudflare edge | runtime ゼロ |

## 再生成 (mirror)

### 自動 (推奨)

[`.github/workflows/refresh-mirror.yml`](.github/workflows/refresh-mirror.yml) により以下のタイミングで自動再生成:

- **毎週月曜 00:00 UTC (09:00 JST)** — `schedule` トリガー
- **手動実行** — GitHub Actions UI または `gh workflow run refresh-mirror.yml`

Cloudflare 側は git push をフックして自動再デプロイします。

### 手動 (ローカル)

1. 別 repo [`budgetbook-demo`](https://github.com/NucoNekoSan/budgetbook-demo) で runserver を起動:
   ```bash
   DEMO_MODE=1 DEMO_ALLOW_WRITES=0 DEMO_AUTO_LOGIN=1 \
     python manage.py runserver 127.0.0.1:8765
   ```
2. 本 repo で mirror を実行:
   ```bash
   pip install requests beautifulsoup4
   python scripts/mirror.py
   ```
3. 生成物を確認 → commit & push → Cloudflare が自動再デプロイ

### pre-commit hook (任意)

```bash
bash scripts/install_git_hooks.sh
```

commit 前に `audit_docs_sensitive.sh --staged` が走り、実値 denylist + 構造的 PII を検出した場合は commit を block します。

## 脆弱性報告

[`SECURITY.md`](SECURITY.md) を参照。Public Issue ではなく [Private Vulnerability Reporting](https://github.com/NucoNekoSan/budgetbook-demo-static/security/advisories/new) を利用してください。

## ライセンス

[MIT License](LICENSE) — 本体 `budgetbook-demo` と同一条件。
# budgetbook-demo-static

`budgetbook-demo` の **静的スナップショット** — Cloudflare Pages で 24/7 公開。

- **ライブ URL**: https://budgetbook-demo-static.nuconekosan.workers.dev/
- **本体リポジトリ (動的 Django アプリ)**: https://github.com/NucoNekoSan/budgetbook-demo
- **構成**: HTML/CSS/JS の静的ファイルのみ。Django ランタイム不要。

## なぜ静的化するのか

セキュリティ最優先のため:

1. **攻撃面ゼロ** — サーバサイドコードが存在しないので RCE / SQL injection / CSRF が成立しない
2. **CVE 影響なし** — Django/依存パッケージの脆弱性が出ても無関係
3. **永続無料** — Cloudflare Pages 無料枠、規約変更耐性高
4. **常時稼働** — cold start なし、全世界 CDN edge から配信

ポートフォリオ用途では「画面遷移できる + GitHub でコードが読める」で必要十分。

## 構成

```
public/         Cloudflare Pages 配信ルート
  *.html         15 ページ (dashboard / B/S / 確定申告レポート 等)
  static/        CSS / JS / icons (601KB)
  _headers       セキュリティヘッダ (CSP / HSTS / X-Frame-Options 等)
scripts/
  mirror.py      動的 demo から静的 HTML を生成するスクリプト
```

## 再生成 (mirror)

1. `budgetbook-demo` で runserver を起動 (DEMO_MODE=1, DEMO_AUTO_LOGIN=1)
2. `python scripts/mirror.py`
3. `public/` 配下を git commit & push → Cloudflare Pages が自動再デプロイ

## ライセンス

MIT (本体 budgetbook-demo に準拠)
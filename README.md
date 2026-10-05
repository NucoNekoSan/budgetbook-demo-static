# BudgetBook 体験デモ

公開URL: **https://budgetbook-demo.nuconeko-garden.com/**  
[Worksで作品を見る](https://nuconeko-garden.com/works/)

[Django本体](https://github.com/NucoNekoSan/budgetbook-demo) の画面を静的化し、ブラウザー内で家計管理を試せるポートフォリオです。Cloudflare Workersの静的アセットから `public/` を配信し、公開環境にDjango・DB・ログイン機能はありません。

## 試せる機能

- 取引の追加・編集・削除、口座間振替、月別区分予算の変更。
- 同じ状態から月次収支・年間収支・資産負債・支出内訳・予算を再計算。
- `sessionStorage` によるタブ内保存。再読み込みと画面移動で維持し、リセットで初期化。
- 架空の4人家族のサンプル。ガイド、ライト・ダーク表示、キーボード操作。

マスター、締め・照合、ローン戦略、医療・保険・税務などは初期サンプルの閲覧専用で、変更は反映しません。CSV・外部連携・PWAは無効です。取引・振替は変更前後の締め済み月を確認します。予算0円は未設定です。

## 構成と再生成

`scripts/export_demo_data.py` は**新しい一時DB**でmigrationと `seed_demo_data` を実行し、必要なフィールドだけを `public/demo-data.json` に出力します。個人用DBは読みません。残高のために全取引・振替履歴を含め、Djangoの計算結果を検証用に添えます。

`scripts/mirror.py` はDjangoの画面と閲覧用フラグメントを静的化し、`scripts/enhance_demo.py` を通して各画面にデモのJS/CSSを付けます。再生成しても編集機能は残ります。フロントエンドは `demo-core.js`（計算・検証）と `demo-app.js`（画面・タブ内保存）に分離しています。

週次と手動の [refresh workflow](.github/workflows/refresh-mirror.yml) は、合成データの生成、mirror、計算テスト、機微パターン検査を実行し、生成物をcommitします。CloudflareのGit連携がmasterの変更を自動デプロイします。`wrangler.jsonc` はWorker `budgetbook-demo` と `public/` を指定しています。カスタムドメインはCloudflare管理画面で設定済みです。補助URLは https://budgetbook-demo.nuconekosan.workers.dev/ です。旧Worker名のworkers.dev URLは使用しません。

ローカルで生成する場合（Python環境にDjango本体のrequirementsとrequests・beautifulsoup4が必要）：

```sh
python scripts/export_demo_data.py --source ../budgetbook-demo/budgetbook
# 合成データ専用DBでDjangoを127.0.0.1:8765に起動してから実行
python scripts/mirror.py
# 既存HTMLへの適用だけの場合
python scripts/enhance_demo.py
```

## 検証

```sh
npm ci
npm test
npx playwright install chromium
npm run test:e2e
python -m unittest discover -s tests -p 'test_*.py'
```

計算テストはDjangoとの比較、振替の収支中立性、締め済み月、日付、整数金額、予算0円を確認します。画面テストはCSPを適用したローカル配信で編集・検索・画面移動・保存・リセット・レスポンシブ表示・キーボード操作と、サーバーへの書き込みがないことを確認します。

`docs/` にWorks掲載文と2000〜3000文字の開発記事を収録しています。画面テストのスクリーンショットはgit対象外の `artifacts/` に出力されます。

## セキュリティとライセンス

静的配信でもXSS・公開データ・依存パッケージ・生成工程のリスクを検証します。編集テキストはHTMLエスケープし、CSPを維持しています。タブ内保存は永続バックアップではありません。詳細と報告先は [SECURITY.md](SECURITY.md)、ライセンスは [MIT](LICENSE) です。

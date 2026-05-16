#!/usr/bin/env bash
# audit_docs_sensitive.sh — public demo-static repo 用、private 由来の機微情報が
# 誤って混入していないか走査する。本 repo は主に mirror 出力 (public/) と
# scripts/, .github/ で構成される。

set -euo pipefail

MODE="full"
VERBOSE=0
for arg in "$@"; do
  case "$arg" in
    --staged)  MODE="staged" ;;
    --verbose) VERBOSE=1 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

PATTERNS=(
  # 数値系は \b 境界で部分一致 (例: 111636 内の 11163) を防ぐ
  '\b388,?897\b' '\b99,?436\b' '\b298,?171\b' '\b34,?300\b' '\b184,?907\b' '\b1,?005,?711\b'
  '\b11,?161\b' '\b11,?163\b' '\b5,?445\b' '\b1,?243\b' '\b4,?473\b'
  '\b108,?576\b' '\b497,?473\b' '\b112,?406\b' '\b367,?081\b' '\b12,?970\b' '\b68,?910\b'
  'home\.nuconeko-garden\.com'
  '192\.168\.1\.(37|40)'
  '240d:18:7:4200'
  '北洋銀行' '札幌市'
  'クレカリボ[ABC]'
  'isonohideki@' 'risa19841013'
)

if [[ "$MODE" == "staged" ]]; then
  mapfile -t TARGETS < <(git diff --cached --name-only --diff-filter=ACMR | grep -E '\.(md|py|html|yml|txt|json)$' || true)
  if [[ ${#TARGETS[@]} -eq 0 ]]; then
    [[ $VERBOSE -eq 1 ]] && echo "[audit] no staged target files"
    exit 0
  fi
else
  mapfile -t TARGETS < <(
    find . -type f \( -name "*.md" -o -name "*.html" -o -name "*.yml" -o -name "*.txt" -o -name "*.json" -o -name "*.py" \) 2>/dev/null \
      | grep -v '\.git/' | grep -v 'node_modules'
  )
fi

PATTERN_UNION=$(IFS='|'; echo "${PATTERNS[*]}")

HITS=0
HIT_LINES=""
for f in "${TARGETS[@]}"; do
  [[ ! -f "$f" ]] && continue
  if [[ "$f" == *"scripts/audit_docs_sensitive.sh" ]]; then continue; fi
  # mirror workflow 自体は禁止語チェックを書く側のコードなので除外
  if [[ "$f" == *".github/workflows/refresh-mirror.yml" ]]; then continue; fi
  while IFS= read -r line; do
    HITS=$((HITS + 1))
    HIT_LINES="${HIT_LINES}${line}"$'\n'
  done < <(grep -EHn "$PATTERN_UNION" "$f" 2>/dev/null || true)
done

if [[ $HITS -eq 0 ]]; then
  [[ $VERBOSE -eq 1 ]] && echo "[audit] clean: 機微情報残存ゼロ (走査対象: ${#TARGETS[@]} ファイル / パターン: ${#PATTERNS[@]} 件)"
  exit 0
fi

echo "[audit] 🚨 private 由来の機微情報を検出しました (${HITS} 件):" >&2
echo "$HIT_LINES" >&2
echo "対応: redact してから commit。public repo では bypass しない。" >&2
exit 1
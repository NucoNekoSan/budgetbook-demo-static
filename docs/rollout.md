# 2026-09-29 portfolio update

- Previous static commit: `43567d3` (Cloudflare version `7db3e42f`). Existing domain was already configured and checked by the owner.
- Runtime: transactions / transfers / budgets in sessionStorage, with common aggregates; remaining reports keep initial snapshot data.
- Fixture: fresh temporary synthetic Django DB, whitelist export of all account history. No user database export.
- CMS: update existing Works BudgetBook row and existing article `budgetbook-read-only-demo`; preserve Tech and publication date 2026-09-25. Other works are unchanged.
- Local public-page backups: ignored `artifacts/works-before.html`, `artifacts/article-before.html`. Wagtail revision history also retains previous published versions.
- Recovery: restore the prior Worker version from Cloudflare deployments; restore existing page revisions from Wagtail history. Revert this commit before future mirror jobs if reverting runtime behavior.

"""Export ONLY a freshly seeded, temporary database; never open a user's database."""
import argparse
import json
import os
import sys
import tempfile
from contextlib import ExitStack
from datetime import date
import calendar
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True, help='Directory containing manage.py')
    parser.add_argument('--output', type=Path, default=Path('public/demo-data.json'))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='budgetbook-public-seed-') as directory, ExitStack() as cleanup:
        root = Path(directory)
        env = root / '.env'
        env.write_text('SECRET_KEY=isolated-synthetic-export-only\nDEBUG=False\nALLOWED_HOSTS=localhost,127.0.0.1\n', encoding='utf-8')
        os.environ.update(BUDGETBOOK_ENV_FILE=str(env), DJANGO_DB_PATH=str(root / 'seed.sqlite3'), DJANGO_SETTINGS_MODULE='config.settings')
        sys.path.insert(0, str(args.source.resolve()))
        import django
        django.setup()
        from django.db import connections
        cleanup.callback(connections.close_all)
        from django.conf import settings
        assert Path(settings.DATABASES['default']['NAME']).resolve() == (root / 'seed.sqlite3').resolve(), 'Export must use isolated database'
        from django.core.management import call_command
        call_command('migrate', verbosity=0)
        call_command('seed_demo_data', reset=True, verbosity=0)
        from ledger.models import Account, Category, Transaction, Transfer, SectionBudget, MonthlyClosing
        def rows(model, fields):
            return list(model.objects.order_by('pk').values(*fields))
        data = dict(schema=1, generated=date.today().isoformat(), provenance='fresh-synthetic-seed',
            accounts=rows(Account, ['id', 'name', 'kind', 'opening_balance', 'is_active']),
            categories=rows(Category, ['id', 'name', 'kind', 'section', 'is_active']),
            transactions=rows(Transaction, ['id', 'date', 'account_id', 'category_id', 'amount', 'description', 'memo']),
            transfers=rows(Transfer, ['id', 'date', 'from_account_id', 'to_account_id', 'amount', 'description', 'memo']),
            budgets=rows(SectionBudget, ['id', 'month', 'section', 'amount', 'notes']),
            closedMonths=[d.strftime('%Y-%m') for d in MonthlyClosing.objects.values_list('month', flat=True)],
            sections=dict(Category.Section.choices))
        from ledger.services.balance import all_account_balances, compute_month_totals
        data['references'] = []
        for year, month in ((date.today().year, date.today().month), (date.today().year - 1, 12), (date.today().year - 2, 1)):
            start = date(year, month, 1)
            end = date(year, month, calendar.monthrange(year, month)[1])
            totals = compute_month_totals(start)
            data['references'].append(dict(month=start.strftime('%Y-%m'), end=str(end), balances=all_account_balances(end), income=totals['income'], expense=totals['expense']))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=False, default=str, separators=(',', ':')), encoding='utf-8')
        print(f'Exported synthetic fixture: {len(data["transactions"])} transactions, {len(data["transfers"])} transfers')


if __name__ == '__main__':
    main()

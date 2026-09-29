"""Idempotently attach sandbox runtime to mirrored full pages."""
import os
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent / 'public'


def enhance(html, directory):
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.body or not soup.find(id='main'):
        return html
    for tag in soup.select('#static-portfolio-banner, .demo-banner, .site-nav__logout, [data-portfolio-runtime]'):
        tag.decompose()
    relative = lambda path: os.path.relpath(ROOT / path, directory).replace('\\', '/')
    # Use the mirrored path, since Django labels budgets as settings.
    parts = Path(directory).relative_to(ROOT).parts
    route = parts[0] if parts and not (len(parts[0]) == 7 and parts[0][4] == '-') else 'dashboard'
    if route in ('dashboard', 'annual', 'balance-sheet', 'expense-breakdown', 'budgets'):
        for script in soup.find_all('script', src=True):
            if Path(script['src']).name in ('dashboard_chart.js', 'budget_chart.js', 'progress_bars.js', 'keyboard_shortcuts.js'):
                script.decompose()
    for a in soup.find_all('a', href=True):
        if a['href'] != '#' and a.get('data-fragment-url'):
            a.attrs.pop('data-fragment-url', None)
            a.attrs.pop('data-fragment-title', None)
    link = soup.new_tag('link', rel='stylesheet', href=relative('static/css/demo-app.css'))
    link['data-portfolio-runtime'] = ''
    soup.head.append(link)
    canonical = soup.find('link', rel='canonical')
    if canonical: canonical.decompose()
    canonical = soup.new_tag('link', rel='canonical', href='https://budgetbook-demo.nuconeko-garden.com/' + '/'.join(parts) + ('/' if parts else ''))
    soup.head.append(canonical)
    for name in ('demo-core.js', 'demo-app.js'):
        script = soup.new_tag('script', src=relative('static/js/' + name), defer='')
        script['data-portfolio-runtime'] = ''
        if name == 'demo-app.js':
            script['data-demo-root'] = relative('.') + '/'
            script['data-demo-route'] = route
        soup.body.append(script)
    return str(soup)


def main():
    count = 0
    for path in ROOT.rglob('*.html'):
        if '_fragments' in path.parts: continue
        before = path.read_text(encoding='utf-8')
        after = enhance(before, path.parent)
        if before != after: path.write_text(after, encoding='utf-8'); count += 1
    print(f'Enhanced {count} pages')


if __name__ == '__main__':
    main()

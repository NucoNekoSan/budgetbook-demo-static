import sys
import unittest
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from enhance_demo import enhance


class GenerationTests(unittest.TestCase):
    def test_all_pages_keep_runtime_after_regeneration(self):
        count = 0
        for path in (ROOT / 'public').rglob('index.html'):
            html = path.read_text(encoding='utf-8')
            once = enhance(html, path.parent)
            self.assertEqual(once, enhance(once, path.parent), path)
            soup = BeautifulSoup(once, 'html.parser')
            self.assertFalse(soup.select('a[href*="github.com"]'), path)
            scripts = soup.select('script[data-portfolio-runtime]')
            self.assertEqual(len(scripts), 2, path)
            self.assertFalse(soup.select('.demo-banner, #static-portfolio-banner, .site-nav__logout'), path)
            for tag in scripts + soup.select('link[data-portfolio-runtime]'):
                self.assertTrue((path.parent / tag.get('src', tag.get('href'))).is_file(), path)
            loader = soup.select_one('script[data-demo-root]')
            self.assertTrue((path.parent / loader['data-demo-root'] / 'demo-data.json').is_file(), path)
            self.assertFalse(soup.select('input[name=csrfmiddlewaretoken], [nonce]'), path)
            if path.parent.name == '2026-08' and path.parent.parent == ROOT / 'public':
                self.assertEqual(loader['data-demo-route'], 'dashboard')
            count += 1
        self.assertGreater(count, 50)


if __name__ == '__main__':
    unittest.main()

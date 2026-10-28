import unittest
from backend.apps.telegram_search.parser import parse, bundle

HTML = b'''<div class="page_header"><div class="name">Example</div></div><div class="history">
<div class="message service"><div class="body">1 January 2026</div></div>
<div class="message default" id="message1"><div class="from_name">Alice</div><div class="date" title="1 January 2026, 10:20:30">edited 10:20</div><div class="text">Hello<br>world<script>evil()</script><a href="https://example.invalid">link</a></div></div>
<div class="message joined" id="message2"><div class="date" title="1 January 2026, 10:21:00"></div><div class="text">Second</div></div></div>'''

class ParserTests(unittest.TestCase):
    def test_structure_and_inert_html(self):
        result = parse(HTML)
        self.assertEqual(len(result['messages']), 3)
        message = result['messages'][1]
        self.assertEqual(message['timestamp'], '2026-01-01T10:20:30')
        self.assertIn('Hello\nworld', message['text'])
        self.assertNotIn('evil', message['text'])
        self.assertEqual(result['messages'][2]['author'], 'Alice')

    def test_unknown_and_duplicate(self):
        with self.assertRaises(ValueError): parse(b'<html>other</html>')
        with self.assertRaises(ValueError): parse(HTML.replace(b'message2', b'message1'))
        result = bundle([('a.html', HTML), ('b.html', HTML)])
        self.assertEqual(result['duplicates'], 2)

    def test_invalid_date_warns(self):
        result = parse(HTML.replace(b'1 January 2026, 10:21:00', b'invalid'))
        self.assertEqual(len(result['warnings']), 1)

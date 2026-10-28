"""Parse inert Telegram Desktop exports; never execute or fetch HTML resources."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser


@dataclass
class Node:
    tag: str = ''
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def has(self, name):
        return name in self.attrs.get('class', '').split()

    def find(self, name):
        return next((n for n in self.walk() if n.has(name)), None)

    def walk(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()

    def text(self):
        if self.tag in {'script', 'style'}:
            return ''
        if self.tag == 'br':
            return '\n'
        value = ''.join(c.text() if isinstance(c, Node) else c for c in self.children)
        return value + ('\n' if self.tag in {'p', 'blockquote', 'pre'} else '')


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack[-1].tag == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse(content: bytes):
    if len(content) > 50 * 1024 * 1024:
        raise ValueError('HTML превышает лимит 50 MiB на файл')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Ожидается UTF-8 HTML') from exc
    tree = Tree()
    tree.feed(text)
    history = tree.root.find('history')
    header = tree.root.find('page_header')
    if not history or not header:
        raise ValueError('Не распознана HTML-выгрузка Telegram Desktop')
    title_node = header.find('name') or header.find('text')
    title = title_node.text().strip() if title_node else header.text().strip()
    messages, warnings, author = [], [], None
    for node in history.children:
        if not isinstance(node, Node) or not node.has('message'):
            continue
        ordinal = len(messages)
        service = node.has('service')
        sender = node.find('from_name')
        if service or not node.has('joined'):
            author = None
        if sender:
            author = sender.text().strip() or None
        date = node.find('date')
        raw_date = date.attrs.get('title', '') if date else ''
        timestamp = None
        if raw_date:
            # English month names without dependence on process locale.
            months = {m: i for i, m in enumerate('January February March April May June July August September October November December'.split(), 1)}
            try:
                day, month, year, clock = raw_date.replace(',', '').split()
                h, minute, second = map(int, clock.split(':'))
                timestamp = datetime(int(year), months[month], int(day), h, minute, second).isoformat()
            except (ValueError, KeyError):
                warnings.append(f'Блок {ordinal + 1}: неизвестный формат даты')
        elif not service:
            warnings.append(f'Блок {ordinal + 1}: отсутствует полная дата')
        body = node.find('text') or (node.find('body') if service else None)
        forward = node.find('forwarded_from')
        reply = node.find('reply_to')
        links = [n.attrs['href'] for n in node.walk() if n.tag == 'a' and n.attrs.get('href')]
        messages.append(dict(ordinal=ordinal, message_id=node.attrs.get('id'), timestamp=timestamp,
            raw_date=raw_date, author=author, text=body.text().strip() if body else '',
            forwarded_from=forward.text().strip() if forward else '',
            reply=reply.text().strip() if reply else '', links=links,
            media=bool(node.find('media_wrap')), service=service))
    if not messages:
        raise ValueError('В истории не найдено сообщений')
    ids = [m['message_id'] for m in messages if m['message_id']]
    if len(ids) != len(set(ids)):
        raise ValueError('Повторяющиеся ID внутри страницы экспорта')
    return dict(title=title, messages=messages, warnings=warnings, sha256=hashlib.sha256(content).hexdigest())


def bundle(files):
    pages = [parse(content) for _, content in files]
    if not pages or len({p['title'] for p in pages}) != 1:
        raise ValueError('Выберите страницы одного чата')
    pages.sort(key=lambda p: next((m['timestamp'] for m in p['messages'] if m['timestamp']), ''))
    messages, seen, duplicates = [], {}, 0
    for page in pages:
        for message in page['messages']:
            mid = message['message_id']
            if mid and mid in seen:
                old = seen[mid]
                if any(old[k] != message[k] for k in ('timestamp', 'text', 'author')):
                    raise ValueError('Одинаковый ID содержит разные данные')
                duplicates += 1
                continue
            message = {**message, 'ordinal': len(messages)}
            messages.append(message)
            if mid:
                seen[mid] = message
    dates = [m['timestamp'] for m in messages if m['timestamp']]
    return dict(title=pages[0]['title'], messages=messages,
        warnings=[w for p in pages for w in p['warnings']], duplicates=duplicates,
        sha256=hashlib.sha256(''.join(sorted(p['sha256'] for p in pages)).encode()).hexdigest(),
        counts=dict(total=len(messages), service=sum(m['service'] for m in messages),
                    regular=sum(not m['service'] for m in messages),
                    missing_text=sum(not m['text'] for m in messages),
                    missing_author=sum(not m['author'] for m in messages),
                    missing_id=sum(not m['message_id'] for m in messages)),
        date_start=min(dates) if dates else None, date_end=max(dates) if dates else None)

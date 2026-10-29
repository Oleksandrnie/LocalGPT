"""Parse inert Telegram Desktop exports; never execute or fetch HTML resources."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from html.parser import HTMLParser

from backend.apps.telegram_search.links import telegram_permalink


class TelegramParseError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


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


def _parse_tree(tree, inherited_author=None, ordinal_offset=0):
    history = tree.root.find('history')
    header = tree.root.find('page_header')
    if not history:
        raise TelegramParseError('telegram_history_not_found', 'В HTML не найдена история Telegram')
    if not header:
        raise TelegramParseError('telegram_header_not_found', 'В HTML не найден заголовок Telegram')
    title_node = header.find('name') or header.find('text')
    title = title_node.text().strip() if title_node else header.text().strip()
    messages, warnings, author = [], [], inherited_author
    for node in history.children:
        if not isinstance(node, Node) or not node.has('message'):
            continue
        ordinal = len(messages) + ordinal_offset
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
                numeric = re.match(r'^(\d{1,2}\.\d{1,2}\.\d{4}) (\d{2}:\d{2}:\d{2})(?: UTC[+-]\d{2}:\d{2})?$', raw_date)
                if numeric:
                    timestamp = datetime.strptime(' '.join(numeric.groups()), '%d.%m.%Y %H:%M:%S').isoformat()
                else:
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
        # Only an explicit own date permalink establishes the message's address.
        # Links in text/forwards/replies can point to unrelated messages.
        own_urls = {telegram_permalink(n.attrs.get('href')) for n in [date, *date.walk()]} if date else set()
        own_urls.discard(None)
        message_url = next(iter(own_urls)) if len(own_urls) == 1 else None
        messages.append(dict(message_url=message_url, ordinal=ordinal, message_id=node.attrs.get('id'), timestamp=timestamp,
            raw_date=raw_date, author=author, text=body.text().strip() if body else '',
            forwarded_from=forward.text().strip() if forward else '',
            reply=reply.text().strip() if reply else '', links=links,
            media=bool(node.find('media_wrap')), service=service))
    if not messages:
        raise TelegramParseError('telegram_messages_not_found', 'В истории не найдено сообщений')
    ids = [m['message_id'] for m in messages if m['message_id']]
    if len(ids) != len(set(ids)):
        raise TelegramParseError('telegram_duplicate_message_ids', 'Повторяющиеся ID внутри страницы экспорта')
    return dict(title=title, messages=messages, warnings=warnings, sha256='')



class MessageStream(Tree):
    """Discard parsed message markup immediately; retain only normalized records."""
    def __init__(self):
        super().__init__()
        self.messages = []
        self.warnings = []
        self.author = None

    def handle_endtag(self, tag):
        closing = None
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                if self.stack[i].has('message') and self.stack[i-1].has('history'):
                    closing = self.stack[i-1]
                break
        super().handle_endtag(tag)
        if closing is not None:
            parsed = _parse_tree(self, self.author, len(self.messages))
            message = parsed['messages'][0]
            message['ordinal'] = len(self.messages)
            self.messages.append(message)
            self.warnings.extend(parsed['warnings'])
            self.author = message['author']
            closing.children.clear()


def parse_stream(stream):
    import codecs
    decoder = codecs.getincrementaldecoder('utf-8-sig')('strict')
    tree = MessageStream()
    digest = hashlib.sha256()
    try:
        while block := stream.read(64 * 1024):
            digest.update(block)
            tree.feed(decoder.decode(block))
        tree.feed(decoder.decode(b'', final=True))
        tree.close()
    except UnicodeDecodeError as exc:
        raise TelegramParseError('telegram_encoding_error', 'Ожидается UTF-8 HTML') from exc
    history = tree.root.find('history')
    header = tree.root.find('page_header')
    if not history:
        raise TelegramParseError('telegram_history_not_found', 'В HTML не найдена история Telegram')
    if not header:
        raise TelegramParseError('telegram_header_not_found', 'В HTML не найден заголовок Telegram')
    if any(isinstance(n, Node) and n.has('message') for n in history.children):
        raise TelegramParseError('telegram_incomplete_message', 'Незакрытый блок сообщения в HTML')
    if not tree.messages:
        raise TelegramParseError('telegram_messages_not_found', 'В истории не найдено сообщений')
    ids = [m['message_id'] for m in tree.messages if m['message_id']]
    if len(ids) != len(set(ids)):
        raise TelegramParseError('telegram_duplicate_message_ids', 'Повторяющиеся ID внутри страницы экспорта')
    title = header.find('name') or header.find('text')
    return dict(title=(title or header).text().strip(), messages=tree.messages,
                warnings=tree.warnings, sha256=digest.hexdigest())


def parse(content: bytes):
    from io import BytesIO
    return parse_stream(BytesIO(content))


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


def rag_message_chunks(parsed, splitter):
    """One message per chunk; repeat provenance on every part of long messages."""
    result = []
    for m in parsed['messages']:
        if m['service']:
            continue
        meta = {k: m[k] for k in ('message_id', 'ordinal', 'timestamp', 'raw_date', 'author')}
        if m.get('message_url'):
            meta['message_url'] = m['message_url']
        meta['format'] = 'telegram_html'
        meta['hashtags'] = re.findall(r'(?<!\w)#[\w]+', m['text'])
        header = (f"Telegram chat: {parsed['title']}\nMessage ID: {m['message_id'] or 'unknown'}\n"
                  f"Date: {m['timestamp'] or 'unknown'} (export time)\nOriginal date: {m['raw_date'] or 'unknown'}\n"
                  f"Author: {m['author'] or 'unknown'}\n")
        body = m['text']
        if m['forwarded_from']: body += '\n'+m['forwarded_from']
        if m['reply']: body += '\nReply: '+m['reply']
        if m['links']: body += '\nLinks: '+' '.join(m['links'])
        if m['media']: body += '\n[Media attachment; content not indexed]'
        for part in splitter(body) or ['[No text]']:
            result.append((header+part, dict(meta)))
    return result


def date_bounds(query):
    """Use current query (first line) before history, so follow-ups override dates."""
    import re
    import calendar
    for line in query.splitlines():
        dates = re.findall(r'\b(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4})\b', line)
        if dates:
            try:
                values = [datetime.strptime(d, '%Y-%m-%d' if '-' in d else '%d.%m.%Y').date().isoformat() for d in dates]
            except ValueError as exc:
                raise ValueError('Некорректная дата в запросе') from exc
            if len(values) == 1:
                # A date after an explicit boundary word denotes an open interval.
                prefix = line[:re.search(re.escape(dates[0]), line).start()].casefold().strip()
                day = datetime.fromisoformat(values[0]).date()
                try:
                    if re.search(r'не раньше\s*$', prefix):
                        return values[0], '9999-12-31'
                    if re.search(r'не позже\s*$', prefix):
                        return '0001-01-01', values[0]
                    if re.search(r'(?:после|позже)\s*$', prefix):
                        return (day + timedelta(days=1)).isoformat(), '9999-12-31'
                    if re.search(r'(?:раньше)\s*$', prefix):
                        return '0001-01-01', (day - timedelta(days=1)).isoformat()
                except OverflowError as exc:
                    raise ValueError('Дата за пределами поддерживаемого диапазона') from exc
                if re.search(r'(?:^|\s)(?:с|начиная с|не ранее)\s*$', prefix):
                    return values[0], '9999-12-31'
                if re.search(r'(?:^|\s)(?:до|по|не позднее)\s*$', prefix):
                    return '0001-01-01', values[0]
            return min(values), max(values)
        months = 'январ феврал март апрел ма июн июл август сентябр октябр ноябр декабр'.split()
        match = re.search(r'\b('+'|'.join(months)+r')\w*\s+(\d{4})\b', line.casefold())
        if match:
            month = months.index(match[1])+1; year = int(match[2])
            if not 1 <= year <= 9999: raise ValueError('Некорректный год')
            return f'{year:04d}-{month:02d}-01', f'{year:04d}-{month:02d}-{calendar.monthrange(year,month)[1]}'
    return None

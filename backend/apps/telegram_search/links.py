"""Pure validation of explicit Telegram message permalinks."""
import re
from urllib.parse import urlsplit, urlunsplit


def telegram_permalink(value: object) -> str | None:
    """Accept an explicit message URL; a chat name/invite is not a message link."""
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or parsed.hostname not in {'t.me', 'telegram.me'}:
            return None
        if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
            return None
    except ValueError:
        return None
    if not re.fullmatch(r'/(?:[A-Za-z][A-Za-z0-9_]{3,31}|c/[1-9][0-9]*)/(?:[1-9][0-9]*/)?[1-9][0-9]*', parsed.path):
        return None
    if parsed.path.split('/')[1].lower() in {'share', 'joinchat', 'addstickers', 'addemoji', 'proxy', 'socks', 'login', 'oauth', 'boost', 'invoice', 'contact', 'giftcode', 'addlist', 'addtheme', 'addstyle', 'setlanguage', 'confirmphone', 'resolve', 'web', 'call'}:
        return None
    return urlunsplit(('https', 't.me', parsed.path, '', ''))



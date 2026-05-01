from __future__ import annotations

import ast
import math
import re
from typing import Any

ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub)
CALCULATION_COMMAND_RE = re.compile(
    r"(?i)(посчитай|рассчитай|вычисл|сумм|сложи|сложить|прибав|итого|сколько\s+будет|"
    r"сколько\s+получится|умнож|процент|вычти|раздели|разделить|подели|поделить|расстел)"
)
SUM_HINT_RE = re.compile(r"(?i)(сумм|сложи|сложить|прибав|плюс|итого)")
AVERAGE_HINT_RE = re.compile(r"(?i)(средн(?:ее|яя|ий)|average|avg)")
PRODUCT_HINT_RE = re.compile(r"(?i)(произведен|произведён|перемнож|multiply\s+all)")
WORD_OPERATOR_RE = re.compile(r"(?i)(плюс|минус|мину\b|вычти|прибав|умнож|раздели|разделить|подели|поделить|расстел|дел[её]н)")
TIMEZONE_CONTEXT_RE = re.compile(r"(?i)(часов(?:ой|ых)?\s+пояс|timezone|utc|gmt|москв|мск|сеул|коре|врем[ея]|утра|вечера)")
NUMBER_TOKEN_RE = re.compile(r"(?<![\w])[-+]?(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?(?![\w])")
NUMERIC_FRACTION_RE = re.compile(r"(?<![\w])([-+]?(?:\d+(?:[.,]\d+)?))\s*/\s*((?:\d+(?:[.,]\d+)?))(?![\w])")
ARITHMETIC_OPERATOR_RE = re.compile(r"[+\-*/×]")
TIME_VALUE_RE = re.compile(
    r"(?P<value>[-+]?(?:\d{1,3}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d+)?)\s*"
    r"(?P<unit>час(?:а|ов)?|ч\.?|hour|hours|hrs?|мин(?:ута|уты|ут)?|minutes?|mins?)\b",
    re.IGNORECASE,
)
NUMBER_WORDS = {
    "ноль": 0,
    "один": 1,
    "одна": 1,
    "одно": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
}
FRACTION_DENOMINATORS = {
    "вторая": 2,
    "вторых": 2,
    "половина": 2,
    "половину": 2,
    "треть": 3,
    "трети": 3,
    "третья": 3,
    "третьих": 3,
    "четверть": 4,
    "четверти": 4,
    "четвертая": 4,
    "четвёртая": 4,
    "четвертых": 4,
    "четвёртых": 4,
    "пятая": 5,
    "пятых": 5,
    "шестая": 6,
    "шестых": 6,
    "седьмая": 7,
    "седьмых": 7,
    "восьмая": 8,
    "восьмых": 8,
    "девятая": 9,
    "девятых": 9,
    "десятая": 10,
    "десятых": 10,
}


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        try:
            parsed = float(cleaned)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _format_number(value: float) -> str:
    rounded = round(value, 6)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.6f}".rstrip("0").rstrip(".")


def _normalize_number_text(value: str) -> str:
    return re.sub(r"[ \u00a0]+", "", value.strip()).replace(",", ".")


def _decimal_places(value: str) -> int:
    normalized = _normalize_number_text(value)
    if "." not in normalized:
        return 0
    return min(6, len(normalized.rsplit(".", 1)[1]))


def _format_number_with_decimals(value: float, decimals: int) -> str:
    if decimals <= 0:
        return _format_number(value)
    return f"{round(value, decimals):.{decimals}f}"


def _plain_number_tokens(user_message: str) -> list[str]:
    return [match.group(0) for match in NUMBER_TOKEN_RE.finditer(_replace_text_numbers(user_message or ""))]


def _plain_numbers(user_message: str) -> list[float]:
    numbers: list[float] = []
    for token in _plain_number_tokens(user_message):
        value = _number(_normalize_number_text(token))
        if value is not None:
            numbers.append(value)
    return numbers


def _format_float_literal(value: float) -> str:
    return f"{value:.12f}".rstrip("0").rstrip(".")


def _replace_numeric_fraction(match: re.Match[str]) -> str:
    numerator = _number(_normalize_number_text(match.group(1)))
    denominator = _number(_normalize_number_text(match.group(2)))
    if numerator is None or denominator is None or abs(denominator) < 1e-12:
        return match.group(0)
    return _format_float_literal(numerator / denominator)


def _replace_text_numbers(value: str, *, numeric_fractions: bool = True) -> str:
    text = str(value or "").lower()
    if numeric_fractions:
        text = NUMERIC_FRACTION_RE.sub(_replace_numeric_fraction, text)

    def _replace_fraction(match: re.Match[str]) -> str:
        numerator = NUMBER_WORDS.get(match.group("num").lower())
        denominator = FRACTION_DENOMINATORS.get(match.group("den").lower())
        if numerator is None or denominator is None or denominator == 0:
            return match.group(0)
        return _format_float_literal(numerator / denominator)

    number_words = "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))
    denominator_words = "|".join(sorted(FRACTION_DENOMINATORS, key=len, reverse=True))
    text = re.sub(
        rf"\b(?P<num>{number_words})\s+(?P<den>{denominator_words})\b",
        _replace_fraction,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\bполовин[ау]?\b", "0.5", text, flags=re.IGNORECASE)
    return text


def _replace_word_operators(value: str, *, numeric_fractions: bool = True) -> str:
    text = _replace_text_numbers(value, numeric_fractions=numeric_fractions)
    replacements = (
        (r"(?i)\bплюс\b|\bприбав(?:ь|ить)?\b", "+"),
        (r"(?i)\bминус\b|\bмину\b|\bвычти\b", "-"),
        (r"(?i)\bумнож(?:ь|ить)?(?:\s+на)?\b", "*"),
        (r"(?i)\bраздели(?:ть)?(?:\s+на)?\b|\bподели(?:ть)?(?:\s+на)?\b|\bрасстел(?:и|ить)?(?:\s+на)?\b|\bдел[её]н(?:ное|ный|ная)?\s+на\b", "/"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _operator_from_command(text: str) -> str | None:
    source = str(text or "").lower()
    if re.search(r"сумм|сложи|сложить|прибав|плюс|итого", source):
        return "+"
    if re.search(r"минус|вычти", source):
        return "-"
    if re.search(r"умнож", source):
        return "*"
    if re.search(r"раздели|разделить|подели|поделить|расстел|дел[её]н", source):
        return "/"
    return None


def _command_expression(user_message: str) -> str | None:
    op = _operator_from_command(user_message)
    if op is None:
        return None
    tokens = _plain_number_tokens(user_message)
    rendered = []
    for token in tokens:
        normalized = _normalize_number_text(token)
        if _number(normalized) is None:
            continue
        rendered.append(normalized.lstrip("+") or "0")
    if len(rendered) < 2:
        return None
    return f" {op} ".join(rendered)


def _ordered_math_expression(user_message: str) -> str | None:
    source = _replace_word_operators(user_message or "", numeric_fractions=False).replace(",", ".").replace("×", "*")
    token_re = rf"{NUMBER_TOKEN_RE.pattern}|[+\-*/()]"
    tokens = [token.strip() for token in re.findall(token_re, source) if token.strip()]
    if not tokens:
        return None
    expression = " ".join(tokens)
    expression = re.sub(r"(?<=\d)[ \u00a0]+(?=\d{3}(?:\D|$))", "", expression)
    if not ARITHMETIC_OPERATOR_RE.search(expression):
        return None
    if not re.fullmatch(r"[0-9\.\+\-\*/\(\)\s]+", expression):
        return None
    try:
        ast.parse(expression, mode="eval")
    except SyntaxError:
        return None
    return expression


def _mostly_math_text(user_message: str) -> bool:
    text = str(user_message or "").strip().lower()
    if not text:
        return False
    text = _replace_word_operators(text)
    text = CALCULATION_COMMAND_RE.sub(" ", text)
    text = re.sub(NUMBER_TOKEN_RE, " ", text)
    text = re.sub(r"[+\-*/×=().,;:!?₽$€\s]+", " ", text)
    return len(text.strip()) <= 3


def _time_items_from_text(user_message: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for match in TIME_VALUE_RE.finditer(user_message or ""):
        value = _number(_normalize_number_text(match.group("value")))
        if value is None:
            continue
        unit = _unit(match.group("unit"))
        if unit in {"hours", "minutes"}:
            items.append({"value": value, "unit": unit})
    return items


def _unit(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"h", "hr", "hrs", "hour", "hours", "час", "часа", "часов", "ч"}:
        return "hours"
    if raw in {"m", "min", "mins", "minute", "minutes", "минута", "минуты", "минут", "мин"}:
        return "minutes"
    if raw in {"rate", "hourly_rate", "money_per_hour", "ставка", "ставка_в_час"}:
        return "rate"
    if raw in {"rub", "ruble", "rubles", "руб", "рубль", "рубли", "рублей", "₽"}:
        return "money"
    if raw in {"percent", "percentage", "%", "процент", "процентов"}:
        return "percent"
    return raw


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items")
    return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []


def _item_minutes(item: dict[str, Any]) -> tuple[float | None, str]:
    value = _number(item.get("value"))
    unit = _unit(item.get("unit"))
    if value is None:
        return None, ""
    if unit == "hours":
        return value * 60.0, f"{_format_number(value)} ч = {_format_number(value * 60.0)} минут"
    if unit == "minutes":
        return value, f"{_format_number(value)} минут"
    return value, f"{_format_number(value)}"


def _sum_minutes(payload: dict[str, Any]) -> tuple[float, list[str]]:
    total = 0.0
    details: list[str] = []
    for item in _items(payload):
        minutes, detail = _item_minutes(item)
        if minutes is None:
            continue
        total += minutes
        if detail:
            details.append(detail)
    return total, details


def _hours_minutes_text(total_minutes: float) -> str:
    sign = "-" if total_minutes < 0 else ""
    value = abs(total_minutes)
    hours = int(value // 60)
    minutes = value - hours * 60
    if abs(minutes - round(minutes)) < 1e-9:
        minute_text = str(int(round(minutes)))
    else:
        minute_text = _format_number(minutes)
    if hours and minutes:
        return f"{sign}{hours} ч {minute_text} мин"
    if hours:
        return f"{sign}{hours} ч"
    return f"{sign}{minute_text} мин"


def _safe_eval(expr: str) -> float:
    tree = ast.parse(expr, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ALLOWED_BIN_OPS):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                if abs(right) < 1e-12:
                    raise ValueError("division_by_zero")
                return left / right
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ALLOWED_UNARY_OPS):
            value = _eval(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        raise ValueError("unsupported_expression")

    return _eval(tree)


def _basic_arithmetic_expression(payload: dict[str, Any], user_message: str) -> str | None:
    expression = str(payload.get("expression") or "").strip()
    if not expression:
        ordered_expression = _ordered_math_expression(user_message)
        if ordered_expression:
            return ordered_expression
        command_expression = _command_expression(user_message)
        if command_expression:
            return command_expression
        source = _replace_word_operators(user_message or "")
        candidates = re.findall(r"[0-9\.\,\+\-\*/×\(\)\s]+", source)
        expression = max(candidates, key=len).strip() if candidates else ""
    else:
        expression = _replace_word_operators(expression)
    expression = expression.replace(",", ".")
    expression = expression.replace("×", "*")
    expression = re.sub(r"(?<=\d)[ \u00a0]+(?=\d{3}(?:\D|$))", "", expression)
    if not expression or not re.fullmatch(r"[0-9\.\+\-\*/\(\)\s]+", expression):
        return None
    return expression


def _percentage_or_fraction_of(user_message: str) -> dict[str, str] | None:
    source = _replace_text_numbers(user_message or "")
    percent_match = re.search(
        rf"({NUMBER_TOKEN_RE.pattern})\s*(?:%|процент(?:а|ов)?)\s+от\s+({NUMBER_TOKEN_RE.pattern})",
        source,
        flags=re.IGNORECASE,
    )
    if percent_match:
        percent = _number(_normalize_number_text(percent_match.group(1)))
        base = _number(_normalize_number_text(percent_match.group(2)))
        if percent is not None and base is not None:
            result = base * percent / 100.0
            return {
                "result": _format_number(result),
                "details": f"{_format_number(percent)}% от {_format_number(base)} = {_format_number(result)}",
            }
    fraction_match = re.search(
        rf"({NUMBER_TOKEN_RE.pattern})\s+от\s+({NUMBER_TOKEN_RE.pattern})",
        source,
        flags=re.IGNORECASE,
    )
    if fraction_match:
        fraction = _number(_normalize_number_text(fraction_match.group(1)))
        base = _number(_normalize_number_text(fraction_match.group(2)))
        if fraction is not None and base is not None and abs(fraction) <= 1:
            result = base * fraction
            return {
                "result": _format_number(result),
                "details": f"{_format_number(fraction)} от {_format_number(base)} = {_format_number(result)}",
            }
    return None


def looks_like_explicit_calculation(user_message: str) -> bool:
    text = str(user_message or "").strip()
    if not text:
        return False
    numbers = _plain_numbers(text)
    has_command = bool(CALCULATION_COMMAND_RE.search(text))
    has_sum_hint = bool(SUM_HINT_RE.search(text))
    has_word_operator = bool(WORD_OPERATOR_RE.search(text))
    if TIMEZONE_CONTEXT_RE.search(text) and not has_command and not has_sum_hint:
        return False
    if len(_time_items_from_text(text)) >= 2 and (has_command or has_word_operator):
        return True
    expression = _basic_arithmetic_expression({}, text)
    has_expression_operator = bool(expression and ARITHMETIC_OPERATOR_RE.search(expression))
    if len(numbers) >= 2 and has_sum_hint:
        return True
    if len(numbers) >= 2 and (has_command or has_word_operator or has_expression_operator) and _mostly_math_text(text):
        return True
    if len(numbers) >= 2 and has_command and (has_word_operator or has_expression_operator):
        return True
    return False


def try_calculate_text(user_message: str, *, force: bool = False) -> dict[str, str] | None:
    if not force and not looks_like_explicit_calculation(user_message):
        return None
    time_items = _time_items_from_text(user_message)
    if len(time_items) >= 2:
        try:
            return calculate({"operation": "sum_time_values", "items": time_items}, user_message)
        except Exception:
            pass
    percent_or_fraction = _percentage_or_fraction_of(user_message)
    if percent_or_fraction:
        return percent_or_fraction
    try:
        return calculate({"operation": "basic_arithmetic"}, user_message)
    except Exception:
        return None


def calculate(payload: dict[str, Any] | None, user_message: str = "") -> dict[str, str]:
    data = payload if isinstance(payload, dict) else {}
    operation = str(data.get("operation") or "").strip().lower()

    if operation in {"convert_hours_to_minutes", "hours_to_minutes"}:
        value = _number(data.get("value"))
        if value is None and _items(data):
            value = _number(_items(data)[0].get("value"))
        if value is not None:
            minutes = value * 60.0
            return {
                "result": f"{_format_number(minutes)} минут",
                "details": f"{_format_number(value)} часа = {_format_number(minutes)} минут",
            }

    if operation in {"convert_minutes_to_hours", "minutes_to_hours"}:
        value = _number(data.get("value"))
        if value is None and _items(data):
            value = _number(_items(data)[0].get("value"))
        if value is not None:
            hours = value / 60.0
            return {
                "result": f"{_format_number(hours)} часа",
                "details": f"{_format_number(value)} минут = {_format_number(hours)} часа",
            }

    if operation in {"sum_time_values", "sum_hours", "sum_project_hours", "remaining_hours", "sum_and_convert_to_minutes"}:
        total_minutes, details = _sum_minutes(data)
        result_minutes = f"{_format_number(total_minutes)} минут"
        readable = _hours_minutes_text(total_minutes)
        return {
            "result": f"{result_minutes} ({readable})",
            "details": "; ".join([*details, f"итого = {_format_number(total_minutes)} минут"]),
        }

    if operation in {"multiply_hours_by_rate", "cost", "hours_times_rate"}:
        hours = _number(data.get("hours"))
        rate = _number(data.get("rate") or data.get("hourly_rate"))
        if hours is None:
            total_minutes, _ = _sum_minutes(data)
            hours = total_minutes / 60.0 if total_minutes else None
        if rate is None:
            for item in _items(data):
                if _unit(item.get("unit")) == "rate":
                    rate = _number(item.get("value"))
                    break
        if hours is not None and rate is not None:
            total = hours * rate
            return {
                "result": f"{_format_number(total)} ₽",
                "details": f"{_format_number(hours)} ч × {_format_number(rate)} ₽/ч = {_format_number(total)} ₽",
            }

    if operation in {"percentage", "percent"}:
        base = _number(data.get("base") or data.get("amount") or data.get("value"))
        percent = _number(data.get("percent") or data.get("percentage"))
        if base is not None and percent is not None:
            result = base * percent / 100.0
            return {
                "result": _format_number(result),
                "details": f"{_format_number(percent)}% от {_format_number(base)} = {_format_number(result)}",
            }

    if operation in {"basic_arithmetic", "arithmetic", ""} and AVERAGE_HINT_RE.search(user_message or ""):
        tokens = _plain_number_tokens(user_message)
        numbers = _plain_numbers(user_message)
        if numbers:
            decimals = max((_decimal_places(token) for token in tokens), default=0)
            result = sum(numbers) / len(numbers)
            rendered_numbers = [_format_number_with_decimals(item, decimals) for item in numbers]
            rendered_result = _format_number_with_decimals(result, decimals)
            return {
                "result": rendered_result,
                "details": f"({' + '.join(rendered_numbers)}) / {len(numbers)} = {rendered_result}",
            }

    if operation in {"basic_arithmetic", "arithmetic", ""} and PRODUCT_HINT_RE.search(user_message or ""):
        tokens = _plain_number_tokens(user_message)
        numbers = _plain_numbers(user_message)
        if len(numbers) >= 2:
            decimals = max((_decimal_places(token) for token in tokens), default=0)
            result = 1.0
            for number in numbers:
                result *= number
            rendered_numbers = [_format_number_with_decimals(item, decimals) for item in numbers]
            rendered_result = _format_number_with_decimals(result, decimals)
            return {
                "result": rendered_result,
                "details": f"{' × '.join(rendered_numbers)} = {rendered_result}",
            }

    if operation in {"basic_arithmetic", "arithmetic", ""} and SUM_HINT_RE.search(user_message or ""):
        tokens = _plain_number_tokens(user_message)
        numbers = _plain_numbers(user_message)
        if len(numbers) >= 2:
            decimals = max((_decimal_places(token) for token in tokens), default=0)
            result = sum(numbers)
            rendered_numbers = [_format_number_with_decimals(item, decimals) for item in numbers]
            rendered_result = _format_number_with_decimals(result, decimals)
            return {
                "result": rendered_result,
                "details": f"{' + '.join(rendered_numbers)} = {rendered_result}",
            }

    expression = _basic_arithmetic_expression(data, user_message)
    if operation in {"basic_arithmetic", "arithmetic", ""} and expression:
        expression = expression.replace("×", "*")
        result = _safe_eval(expression)
        return {
            "result": _format_number(result),
            "details": f"{expression} = {_format_number(result)}",
        }

    raise ValueError("unsupported_calculation")

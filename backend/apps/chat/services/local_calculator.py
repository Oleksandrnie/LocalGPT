from __future__ import annotations

import ast
import math
import re
from typing import Any

ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div)
ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub)


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
        candidates = re.findall(r"[0-9\.\,\+\-\*/\(\)\s]+", user_message or "")
        expression = max(candidates, key=len).strip() if candidates else ""
    expression = expression.replace(",", ".")
    if not expression or not re.fullmatch(r"[0-9\.\+\-\*/\(\)\s]+", expression):
        return None
    return expression


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

    expression = _basic_arithmetic_expression(data, user_message)
    if operation in {"basic_arithmetic", "arithmetic", ""} and expression:
        result = _safe_eval(expression)
        return {
            "result": _format_number(result),
            "details": f"{expression} = {_format_number(result)}",
        }

    raise ValueError("unsupported_calculation")


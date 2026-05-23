"""
tools.py
Mock hotel availability tool + Gemini function declaration schema.
"""

from __future__ import annotations

import json
import random
from datetime import date

# ---------------------------------------------------------------------------
# Mock availability data
# ---------------------------------------------------------------------------

_BOOKED_COMBOS: set[tuple[str, str]] = {
    ("Single",    "2025-12-24"),
    ("Single",    "2025-12-25"),
    ("Double",    "2025-12-31"),
    ("Suite",     "2025-12-31"),
    ("Penthouse", "2025-12-24"),
    ("Penthouse", "2025-12-25"),
    ("Penthouse", "2025-12-31"),
}

_PRICES: dict[str, int] = {
    "Single":    80,
    "Double":    140,
    "Suite":     300,
    "Penthouse": 700,
}


def check_room_availability(
    room_type: str,
    check_in_date: str,
    check_out_date: str,
) -> dict:
    """
    Simulated availability check.

    Returns a dict with:
        status          : "Available" | "Fully Booked" | "Error"
        room_type       : echoed back
        check_in_date   : echoed back
        check_out_date  : echoed back
        price_per_night : int (USD) — only present when Available
        total_price     : int (USD) — only present when Available
        message         : human-readable summary
    """
    canonical = room_type.strip().title()
    if canonical not in _PRICES:
        return {
            "status": "Error",
            "message": (
                f"Unknown room type '{room_type}'. "
                "Valid options: Single, Double, Suite, Penthouse."
            ),
        }

    try:
        ci = date.fromisoformat(check_in_date)
        co = date.fromisoformat(check_out_date)
    except ValueError as exc:
        return {"status": "Error", "message": f"Invalid date format: {exc}"}

    nights = (co - ci).days
    if nights <= 0:
        return {
            "status": "Error",
            "message": "check_out_date must be after check_in_date.",
        }

    booked = any(
        (canonical, str(ci.replace(day=ci.day + i))) in _BOOKED_COMBOS
        for i in range(nights)
    )
    if not booked:
        booked = random.random() < 0.10

    if booked:
        return {
            "status": "Fully Booked",
            "room_type": canonical,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "message": (
                f"Sorry, no {canonical} rooms are available "
                f"from {check_in_date} to {check_out_date}."
            ),
        }

    price = _PRICES[canonical]
    total = price * nights
    return {
        "status": "Available",
        "room_type": canonical,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "price_per_night": price,
        "total_price": total,
        "message": (
            f"{canonical} room available from {check_in_date} to {check_out_date}. "
            f"${price}/night x {nights} night(s) = ${total} total."
        ),
    }


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def dispatch_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute a tool by name and return the result as a dict."""
    if tool_name == "check_room_availability":
        return check_room_availability(
            room_type=tool_input.get("room_type", ""),
            check_in_date=tool_input.get("check_in_date", ""),
            check_out_date=tool_input.get("check_out_date", ""),
        )
    return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# Gemini function declaration schema
# ---------------------------------------------------------------------------

from google.generativeai.types import FunctionDeclaration, Tool  # noqa: E402

AVAILABILITY_FUNCTION = FunctionDeclaration(
    name="check_room_availability",
    description=(
        "Check whether a specific hotel room type is available for the requested "
        "dates. Call this tool as soon as you have the room_type, check_in_date, "
        "and check_out_date. Do NOT guess availability — always call this tool."
    ),
    parameters={
        "type": "object",
        "properties": {
            "room_type": {
                "type": "string",
                "description": (
                    "The type of room requested. Must be exactly one of: "
                    "Single, Double, Suite, Penthouse."
                ),
                "enum": ["Single", "Double", "Suite", "Penthouse"],
            },
            "check_in_date": {
                "type": "string",
                "description": "Check-in date in ISO format YYYY-MM-DD.",
            },
            "check_out_date": {
                "type": "string",
                "description": "Check-out date in ISO format YYYY-MM-DD.",
            },
        },
        "required": ["room_type", "check_in_date", "check_out_date"],
    },
)

HOTEL_TOOLS = Tool(function_declarations=[AVAILABILITY_FUNCTION])

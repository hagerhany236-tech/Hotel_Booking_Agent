"""
agent.py
Room Booking Dynamic Concierge Agent — powered by Google Gemini (free tier)
============================================================================
Run:
    python agent.py
    python agent.py --guest "Jane Smith"   # loads stored preferences for Jane

Free API key: https://aistudio.google.com/app/apikey
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv
from pydantic import ValidationError

from memory import build_preference_prompt, save_preferences
from schemas import BookingConfirmation
from tools import HOTEL_TOOLS, dispatch_tool

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "gemini-2.0-flash"   # free tier, fast, supports function calling

SYSTEM_PROMPT = """You are a concierge agent for The Grand Palace Hotel. \
Your ONLY job is to help guests book a hotel room. Do not discuss any other topic.

Room types available: Single, Double, Suite, Penthouse.

Your task for each conversation:
1. Collect the following information (ask for missing items one at a time):
   - Guest full name (first + last)
   - Desired room type (Single / Double / Suite / Penthouse)
   - Check-in date  (YYYY-MM-DD)
   - Check-out date (YYYY-MM-DD)
2. Once you have all four details, call the check_room_availability tool immediately.
3. If available, confirm the booking by outputting a JSON block wrapped in
   <booking_json> ... </booking_json> tags with these exact keys:
       guest_name, room_type, check_in_date, check_out_date
   All dates MUST be in YYYY-MM-DD format.
4. If fully booked, apologise and ask if the guest wants to try different dates \
or a different room type.

Rules:
- Never invent availability — always call the tool.
- If the guest provides a date in any other format (e.g. "next Friday"), convert it \
to YYYY-MM-DD before calling the tool and confirm the conversion with the guest.
- Be warm, concise, and professional.
{preference_block}"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_booking_json(text: str) -> dict[str, Any] | None:
    """Pull the <booking_json>...</booking_json> block from assistant text."""
    match = re.search(r"<booking_json>(.*?)</booking_json>", text, re.DOTALL)
    if not match:
        return None
    raw = match.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _validate_booking(
    data: dict[str, Any],
    chat,            # genai ChatSession — we send the correction into it
) -> BookingConfirmation | None:
    """
    Try to build a BookingConfirmation. On failure, send the raw error back
    into the chat so Gemini can self-correct, then return None.
    """
    try:
        return BookingConfirmation(**data)
    except ValidationError as exc:
        error_summary = "; ".join(
            f"{e['loc'][0]}: {e['msg']}" for e in exc.errors()
        )
        correction_message = (
            f"The booking data failed validation: {error_summary}. "
            "Please correct the data and output the <booking_json> block again "
            "with valid values."
        )
        print(f"\n[Validation error — asking agent to self-correct]\n  {error_summary}\n")
        # We return (None, correction_message) to let the caller inject it
        return None, correction_message
    return BookingConfirmation(**data), None   # unreachable but clear


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------


def _handle_response(response, chat) -> tuple[str, BookingConfirmation | None, str | None]:
    """
    Process a Gemini response object.

    Handles tool calls internally (calls dispatch_tool and sends results back),
    then returns:
        (agent_text, confirmed_booking_or_None, correction_message_or_None)
    """
    # Gemini may chain multiple function calls before returning text.
    # We loop until the response contains only text parts.
    while True:
        # Check for function calls in the response
        fn_calls = []
        for part in response.parts:
            if part.function_call.name:
                fn_calls.append(part.function_call)

        if not fn_calls:
            break  # pure text response — done

        # Execute every function call and build response parts
        fn_responses = []
        for fn_call in fn_calls:
            name = fn_call.name
            args = dict(fn_call.args)
            print(f"\n[Tool call] {name}({json.dumps(args, indent=2)})")
            result = dispatch_tool(name, args)
            print(f"[Tool result] {json.dumps(result, indent=2)}\n")

            fn_responses.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=name,
                        response={"result": result},
                    )
                )
            )

        # Send all tool results back in a single turn
        response = chat.send_message(fn_responses)

    # Extract text
    agent_text = response.text.strip() if response.text else ""
    return agent_text


# ---------------------------------------------------------------------------


def run_agent(guest_name_hint: str | None = None) -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set. Add it to your .env file.")
        print("Get a free key at: https://aistudio.google.com/app/apikey")
        sys.exit(1)

    genai.configure(api_key=api_key)

    # Inject long-term preferences if a returning guest name was supplied
    preference_block = ""
    if guest_name_hint:
        preference_block = build_preference_prompt(guest_name_hint)
        if preference_block:
            print(f"[Memory] Loaded preferences for {guest_name_hint}.")

    system = SYSTEM_PROMPT.format(preference_block=preference_block)

    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system,
        tools=[HOTEL_TOOLS],
    )

    # Use automatic function calling disabled so we handle it ourselves
    chat = model.start_chat()

    confirmed_booking: BookingConfirmation | None = None

    print("\n" + "=" * 55)
    print("  🏨  Welcome to The Grand Palace Hotel Concierge")
    print("=" * 55)
    print("  Type 'quit' or 'exit' to end the session.\n")

    # Opening greeting
    opening_response = chat.send_message("Hello, I'd like to book a room.")
    agent_text = _handle_response(opening_response, chat)
    print(f"Agent: {agent_text}\n")

    # -----------------------------------------------------------------------
    # Main conversation loop
    # -----------------------------------------------------------------------
    while confirmed_booking is None:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", ""):
            print("\nGoodbye! We hope to host you soon. 🏨\n")
            sys.exit(0)

        response = chat.send_message(user_input)
        agent_text = _handle_response(response, chat)
        print(f"\nAgent: {agent_text}\n")

        # Check for completed booking JSON
        booking_data = _extract_booking_json(agent_text)
        if booking_data:
            result = _validate_booking(booking_data, chat)
            if isinstance(result, tuple):
                # Validation failed — result is (None, correction_msg)
                _, correction_msg = result
                correction_response = chat.send_message(correction_msg)
                corrected_text = _handle_response(correction_response, chat)
                print(f"\nAgent: {corrected_text}\n")
                # Check again after correction
                booking_data2 = _extract_booking_json(corrected_text)
                if booking_data2:
                    result2 = _validate_booking(booking_data2, chat)
                    if not isinstance(result2, tuple):
                        confirmed_booking = result2
            else:
                confirmed_booking = result

    # -----------------------------------------------------------------------
    # Booking confirmed
    # -----------------------------------------------------------------------
    print(confirmed_booking.summary())

    # ---- Bonus: extract & persist preferences ----
    pref_prompt = (
        "Based on our conversation, list any guest preferences or special requirements "
        "as a JSON array of short strings (e.g. [\"Prefers high floors\", \"Requires king bed\"]). "
        "Output ONLY the JSON array, nothing else."
    )
    pref_response = chat.send_message(pref_prompt)
    pref_text = pref_response.text.strip() if pref_response.text else ""
    try:
        clean = re.sub(r"```[a-z]*\n?", "", pref_text).strip().rstrip("`").strip()
        preferences: list[str] = json.loads(clean)
        if preferences:
            save_preferences(confirmed_booking.guest_name, preferences)
            print(
                f"[Memory] Saved {len(preferences)} preference(s) "
                f"for {confirmed_booking.guest_name}."
            )
    except (json.JSONDecodeError, TypeError):
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hotel Room Booking Concierge Agent")
    parser.add_argument(
        "--guest",
        type=str,
        default=None,
        help="Returning guest name to pre-load stored preferences.",
    )
    args = parser.parse_args()
    run_agent(guest_name_hint=args.guest)

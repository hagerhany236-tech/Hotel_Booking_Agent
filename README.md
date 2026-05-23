# 🏨 Hotel Room Booking Concierge Agent

An autonomous AI agent that handles hotel room bookings via a dynamic multi-turn conversation.
Built for the APPGAIN.io AI Internship Technical Assessment — powered by **Google Gemini (free tier)**.

---

## Features

- **Agentic loop** — continuous function-calling loop using the Gemini API
- **Mock availability tool** — `check_room_availability()` simulates real hotel inventory
- **Pydantic validation + self-correction** — invalid booking data is caught and fed back to the LLM to fix automatically
- **Short-term memory** — full conversation history maintained across all turns via Gemini `ChatSession`
- **Long-term preference store** (bonus) — SQLite-backed guest profiles injected into subsequent sessions

---

## Project Structure

```
hotel-agent/
├── agent.py          # Agentic loop orchestration (entry point)
├── tools.py          # Mock tool + Gemini FunctionDeclaration schema
├── schemas.py        # Pydantic BookingConfirmation model + validators
├── memory.py         # SQLite long-term preference store
├── requirements.txt
├── .env              # Your API key goes here (not committed)
└── README.md
```

---

## Setup

### 1. Clone / download the project

```bash
git clone https://github.com/YOUR_USERNAME/hotel-agent.git
cd hotel-agent
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get a free Gemini API key

1. Go to https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Click **Create API key**
4. Copy the key

### 5. Configure your API key

Create a `.env` file in the project root:

```
GEMINI_API_KEY=AIza...your-key-here...
```

---

## Running the Agent

### New session

```bash
python agent.py
```

### Returning guest (loads stored preferences)

```bash
python agent.py --guest "Jane Smith"
```

---

## Example Session

```
=======================================================
  🏨  Welcome to The Grand Palace Hotel Concierge
=======================================================
  Type 'quit' or 'exit' to end the session.

Agent: Good evening! Welcome to The Grand Palace Hotel.
       I'd be happy to help you book a room. Could I start
       with your full name, please?

You: John Doe

Agent: Thank you, John! What type of room would you like?
       We have Single, Double, Suite, and Penthouse rooms.

You: A suite please

Agent: Lovely choice! What are your preferred check-in
       and check-out dates?

You: Check in June 10 2025, check out June 14

[Tool call] check_room_availability({
  "room_type": "Suite",
  "check_in_date": "2025-06-10",
  "check_out_date": "2025-06-14"
})
[Tool result] {"status": "Available", "total_price": 1200, ...}

Agent: Great news! A Suite is available from 2025-06-10 to
       2025-06-14 — that's 4 nights at $300/night ($1,200 total).

       <booking_json>
       {
         "guest_name": "John Doe",
         "room_type": "Suite",
         "check_in_date": "2025-06-10",
         "check_out_date": "2025-06-14"
       }
       </booking_json>

==================================================
  ✅ BOOKING CONFIRMED
==================================================
  Guest      : John Doe
  Room type  : Suite
  Check-in   : 2025-06-10
  Check-out  : 2025-06-14
  Duration   : 4 night(s)
==================================================
```

---

## Architecture

### Agentic Loop (`agent.py`)

```
User input
    │
    ▼
chat.send_message(user_input)        ← Gemini ChatSession keeps history
    │
    ├─── response has function_call? ──► dispatch_tool() ──► send_message(fn_response) ──► loop
    │
    └─── pure text response
              │
              ├─── Contains <booking_json>? ──► Pydantic validate
              │         │
              │         ├─── Valid   ──► Print confirmation + save preferences
              │         └─── Invalid ──► send correction into chat ──► retry
              │
              └─── No booking yet ──► Print reply ──► wait for user input
```

### Validation (`schemas.py`)

| Field | Constraint |
|---|---|
| `guest_name` | Non-empty; must have first + last name |
| `room_type` | Exactly one of: Single, Double, Suite, Penthouse |
| `check_in_date` | ISO `YYYY-MM-DD`; must be today or future |
| `check_out_date` | ISO `YYYY-MM-DD`; must be after check-in |

### Long-term Memory (`memory.py`)

At the end of each confirmed booking, the agent extracts guest preferences from the conversation and writes them to `preferences.db` (SQLite). On the next run with `--guest "Name"`, preferences are injected into the system prompt.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Free key from https://aistudio.google.com/app/apikey |

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `google-generativeai` | ≥ 0.7 | Gemini API client (free tier) |
| `pydantic` | ≥ 2.0 | Schema validation |
| `python-dotenv` | ≥ 1.0 | Load `.env` file |

---

## Free Tier Limits (Gemini 1.5 Flash)

| Limit | Value |
|---|---|
| Requests per minute | 15 |
| Requests per day | 1,500 |
| Tokens per minute | 1,000,000 |

More than enough for development and demos.

from __future__ import annotations

import json
import os
from datetime import date
from typing import Any

from dotenv import load_dotenv
from groq import Groq, GroqError
from pydantic import ValidationError

from .models import ExtractedIntent


SYSTEM_PROMPT = """You are a rental housing assistant for a short-term monthly rental business.

Your only job is to understand the user's natural language message and return strict JSON.
Do not update data.
Do not say anything was saved.
Do not calculate payment status.
Do not invent unknown room IDs, prices, dates, tenant names, or payment methods.
The backend will validate, preview, confirm, calculate, and save.

Return only valid JSON with this exact shape:
{
  "intent": "payment_update",
  "confidence": 0.0,
  "room_id": 101,
  "tenant_name": null,
  "tenant_ph": null,
  "rent_start_date": null,
  "rent_end_date": null,
  "amount_due": null,
  "amount_paid": 550000,
  "payment_date": "2026-07-03",
  "payment_method": "Transfer",
  "move_out_date": null,
  "current_occupants": null,
  "ac": null,
  "new_amount_due": null,
  "user_message_summary": "Room 101 paid 550000 by transfer on 2026-07-03",
  "missing_fields": [],
  "needs_follow_up": false,
  "follow_up_questions": []
}

Allowed intents:
- question_empty_rooms
- question_late_payments
- question_unpaid_payments
- question_room_status
- question_payment_status
- question_summary
- question_unknown
- payment_update
- move_out
- move_in
- rent_change
- ac_change
- auto_rollover
- unknown

Field rules:
- Use integers for room_id and occupant counts.
- Use numbers for money. Do not include Rp, commas, or currency text.
- Use YYYY-MM-DD for dates.
- Resolve "today" and "yesterday" using the backend current date supplied by the user message context.
- Normalize payment_method to "Transfer" or "Cash" when possible.
- Normalize ac to "Y" or "N" when possible.
- If required fields are missing, set needs_follow_up true and list missing_fields and follow_up_questions.
- For payment_update, amount_paid may be null if the user did not say the amount.
- For move_in, rent_end_date is required unless the user clearly provided it.
- A follow-up answer belongs to the original request. Keep the original intent and merge the new fields.
- If a move-in tenant has not paid yet, use amount_paid 0 and leave payment_date and payment_method null. They are not missing fields.
- For rent_change, new_amount_due is required.
- For ac_change, include ac if known and new_amount_due if user gave the new rent.
- If confidence is low or intent is unclear, use intent "unknown" and ask a follow-up.
"""


class GroqAgentError(Exception):
    pass


class GroqIntentAgent:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        load_dotenv()
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
        if not self.api_key:
            raise GroqAgentError(
                "GROQ_API_KEY is missing. Add it to a .env file or export it before using /chat."
            )
        self.client = Groq(api_key=self.api_key)

    def extract_intent(self, message: str, today: date | None = None) -> ExtractedIntent:
        today_value = today or date.today()
        user_prompt = (
            f"Backend current date: {today_value.isoformat()}.\n"
            f"User message: {message}"
        )
        first_error: Exception | None = None
        for attempt in range(2):
            try:
                content = self._call_groq(user_prompt, strict_retry=attempt == 1)
                parsed = json.loads(content)
                cleaned = self._clean_payload(parsed)
                return ExtractedIntent(**cleaned)
            except (json.JSONDecodeError, ValidationError, GroqAgentError, GroqError) as error:
                first_error = error
        raise GroqAgentError(
            "Groq did not return valid intent JSON. Please rephrase the message."
        ) from first_error

    def _call_groq(self, user_prompt: str, *, strict_retry: bool) -> str:
        retry_text = ""
        if strict_retry:
            retry_text = "\nThe previous response was invalid. Return JSON only, no markdown."
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + retry_text},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        if not content:
            raise GroqAgentError("Groq returned an empty response.")
        return content

    def _clean_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = set(ExtractedIntent.model_fields)
        result = {key: value for key, value in payload.items() if key in allowed_keys}
        if result.get("room_id") == "":
            result["room_id"] = None
        if isinstance(result.get("room_id"), str) and result["room_id"].isdigit():
            result["room_id"] = int(result["room_id"])
        return result

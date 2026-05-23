from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator


VALID_ROOM_TYPES = ["Single", "Double", "Suite", "Penthouse"]


class BookingConfirmation(BaseModel):
    guest_name: str
    room_type: Literal["Single", "Double", "Suite", "Penthouse"]
    check_in_date: str
    check_out_date: str

    @field_validator("guest_name")
    @classmethod
    def name_must_have_first_and_last(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("guest_name cannot be empty.")
        parts = v.split()
        if len(parts) < 2:
            raise ValueError(
                f"guest_name must contain both a first and last name (got '{v}')."
            )
        return v

    @field_validator("check_in_date", "check_out_date")
    @classmethod
    def must_be_iso_format(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(
                f"Date '{v}' is not in ISO format (YYYY-MM-DD). "
                "Please provide a date like 2025-09-15."
            )
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Date '{v}' is not a valid calendar date.")
        return v

    @field_validator("check_in_date")
    @classmethod
    def check_in_must_be_future(cls, v: str) -> str:
        check_in = date.fromisoformat(v)
        if check_in < date.today():
            raise ValueError(
                f"check_in_date '{v}' is in the past. Please provide an upcoming date."
            )
        return v

    @model_validator(mode="after")
    def checkout_after_checkin(self) -> "BookingConfirmation":
        try:
            ci = date.fromisoformat(self.check_in_date)
            co = date.fromisoformat(self.check_out_date)
        except ValueError:
            return self
        if co <= ci:
            raise ValueError(
                f"check_out_date '{self.check_out_date}' must be after "
                f"check_in_date '{self.check_in_date}'."
            )
        return self

    def summary(self) -> str:
        ci = date.fromisoformat(self.check_in_date)
        co = date.fromisoformat(self.check_out_date)
        nights = (co - ci).days
        return (
            f"\n{'='*50}\n"
            f"  ✅ BOOKING CONFIRMED\n"
            f"{'='*50}\n"
            f"  Guest      : {self.guest_name}\n"
            f"  Room type  : {self.room_type}\n"
            f"  Check-in   : {self.check_in_date}\n"
            f"  Check-out  : {self.check_out_date}\n"
            f"  Duration   : {nights} night(s)\n"
            f"{'='*50}\n"
        )

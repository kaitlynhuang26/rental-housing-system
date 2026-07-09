from __future__ import annotations

import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from .models import Payment, Room, RoomDetail, Summary


DEFAULT_EXCEL_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "Kos Gedung Panjang (1).xlsx"
)

REQUIRED_ROOM_COLUMNS = {
    "room_id",
    "floor",
    "room_number",
    "ac",
    "current_occupants",
    "usual_price",
    "rent_required",
    "note",
}

REQUIRED_PAYMENT_COLUMNS = {
    "room_id",
    "rent_start_date",
    "rent_end_date",
    "amount_due",
    "amount_paid",
    "payment_date",
    "payment_status",
    "room_status",
    "payment_method",
    "tenant_name",
    "tenant_ph",
    "ac",
}


class ExcelDataError(Exception):
    def __init__(
        self,
        detail: str,
        *,
        available_sheets: list[str] | None = None,
        missing_columns: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.available_sheets = available_sheets
        self.missing_columns = missing_columns
        self.warnings = warnings or []


class RentalExcelService:
    def __init__(self, excel_path: str | Path | None = None, today: date | None = None):
        configured_path = excel_path or os.getenv("EXCEL_FILE_PATH") or DEFAULT_EXCEL_PATH
        self.excel_path = Path(configured_path).expanduser().resolve()
        self.today = today or date.today()
        self._rooms: list[Room] | None = None
        self._payments: list[Payment] | None = None
        self._warnings: list[str] = []

    def health(self) -> dict[str, str]:
        if not self.excel_path.exists():
            raise ExcelDataError(f"Excel file not found: {self.excel_path}")
        return {"status": "ok", "excel_file": str(self.excel_path)}

    def get_rooms(self) -> list[Room]:
        self._load_if_needed()
        return self._rooms or []

    def get_payments(self) -> list[Payment]:
        self._load_if_needed()
        return self._payments or []

    def get_summary(self) -> Summary:
        self._load_if_needed()
        rooms = self._rooms or []
        payments = [payment for payment in (self._payments or []) if _is_active_payment(payment)]

        total_rooms = len(rooms)
        empty_rooms = sum(1 for room in rooms if room.current_status == "Empty")
        occupied_rooms = total_rooms - empty_rooms
        rent_required_n = sum(1 for room in rooms if _normalize_yes_no(room.rent_required) == "N")

        total_amount_due = sum(payment.amount_due for payment in payments)
        total_amount_paid = sum(payment.amount_paid for payment in payments)
        total_unpaid_amount = sum(
            max(payment.amount_due - payment.amount_paid, 0)
            for payment in payments
            if payment.calculated_payment_status == "Unpaid"
        )

        total_cash_collected = sum(
            payment.amount_paid
            for payment in payments
            if _clean_text(payment.payment_method).lower() == "cash"
        )
        total_transfer_collected = sum(
            payment.amount_paid
            for payment in payments
            if _clean_text(payment.payment_method).lower() == "transfer"
        )

        return Summary(
            total_rooms=total_rooms,
            occupied_rooms=occupied_rooms,
            empty_rooms=empty_rooms,
            rooms_with_rent_required_n=rent_required_n,
            total_amount_due=total_amount_due,
            total_amount_paid=total_amount_paid,
            total_unpaid_amount=total_unpaid_amount,
            total_cash_collected=total_cash_collected,
            total_transfer_collected=total_transfer_collected,
            late_payment_rows=sum(
                1 for payment in payments if payment.calculated_payment_status == "Late"
            ),
            unpaid_payment_rows=sum(
                1 for payment in payments if payment.calculated_payment_status == "Unpaid"
            ),
            warnings=self._warnings,
        )

    def get_empty_rooms(self) -> list[Room]:
        return [room for room in self.get_rooms() if room.current_status == "Empty"]

    def get_late_payments(self) -> list[Payment]:
        return [
            payment
            for payment in self.get_payments()
            if _is_active_payment(payment) and payment.calculated_payment_status == "Late"
        ]

    def get_unpaid_payments(self) -> list[Payment]:
        return [
            payment
            for payment in self.get_payments()
            if _is_active_payment(payment) and payment.calculated_payment_status == "Unpaid"
        ]

    def get_room_detail(self, room_id: int) -> RoomDetail:
        rooms = self.get_rooms()
        room = next((item for item in rooms if item.room_id == room_id), None)
        if room is None:
            raise ExcelDataError(f"Room {room_id} was not found.")

        payments = [
            payment for payment in self.get_payments() if payment.room_id == room_id
        ]
        return RoomDetail(room=room, payments=payments)

    def _load_if_needed(self) -> None:
        if self._rooms is not None and self._payments is not None:
            return

        if not self.excel_path.exists():
            raise ExcelDataError(f"Excel file not found: {self.excel_path}")

        try:
            excel = pd.ExcelFile(self.excel_path)
        except ImportError as error:
            raise ExcelDataError(
                "Missing Excel reader dependency. Install project requirements with "
                "`python -m pip install -r backend/requirements.txt`."
            ) from error

        required_sheets = {"room_record", "payments"}
        missing_sheets = sorted(required_sheets - set(excel.sheet_names))
        if missing_sheets:
            raise ExcelDataError(
                f"Missing required sheet(s): {', '.join(missing_sheets)}",
                available_sheets=excel.sheet_names,
            )

        room_df = self._read_sheet("room_record")
        payment_df = self._read_sheet("payments")
        self._validate_columns(room_df, REQUIRED_ROOM_COLUMNS, "room_record")
        self._validate_columns(payment_df, REQUIRED_PAYMENT_COLUMNS, "payments")

        self._rooms = self._build_rooms(room_df)
        self._payments = self._build_payments(payment_df, self._rooms)
        self._apply_latest_payment_status_to_rooms()

    def _read_sheet(self, sheet_name: str) -> pd.DataFrame:
        try:
            df = pd.read_excel(self.excel_path, sheet_name=sheet_name, dtype=object)
        except ImportError as error:
            raise ExcelDataError(
                "Missing Excel reader dependency. Install project requirements with "
                "`python -m pip install -r backend/requirements.txt`."
            ) from error

        df = df.rename(columns={column: _normalize_column(column) for column in df.columns})

        # This workbook uses "ac (portable ac)" in room_record; expose it as "ac".
        if "ac_portable_ac" in df.columns and "ac" not in df.columns:
            df = df.rename(columns={"ac_portable_ac": "ac"})

        # Drop Excel helper/note columns that are outside the business schema.
        unnamed_columns = [column for column in df.columns if column.startswith("unnamed")]
        return df.drop(columns=unnamed_columns, errors="ignore")

    def _validate_columns(
        self, df: pd.DataFrame, required_columns: set[str], sheet_name: str
    ) -> None:
        missing_columns = sorted(required_columns - set(df.columns))
        if missing_columns:
            raise ExcelDataError(
                f"Sheet '{sheet_name}' is missing required column(s): "
                + ", ".join(missing_columns),
                missing_columns=missing_columns,
            )

    def _build_rooms(self, df: pd.DataFrame) -> list[Room]:
        rooms: list[Room] = []
        for index, row in df.iterrows():
            row_number = index + 2
            warnings: list[str] = []
            room_id = _to_int(row.get("room_id"))
            if room_id is None:
                self._warnings.append(f"room_record row {row_number} has no room_id and was skipped.")
                continue

            rooms.append(
                Room(
                    room_id=room_id,
                    floor=_to_int(row.get("floor")),
                    room_number=_to_int(row.get("room_number")),
                    ac=_normalize_yes_no(row.get("ac")),
                    current_occupants=_to_int(row.get("current_occupants")) or 0,
                    current_status=(
                        "Empty"
                        if (_to_int(row.get("current_occupants")) or 0) == 0
                        else "Occupied"
                    ),
                    usual_price=_to_money(row.get("usual_price")),
                    rent_required=_normalize_yes_no(row.get("rent_required")),
                    note=_clean_text(row.get("note")) or None,
                    warnings=warnings,
                )
            )
        return rooms

    def _build_payments(self, df: pd.DataFrame, rooms: list[Room]) -> list[Payment]:
        payments: list[Payment] = []
        room_by_id = {room.room_id: room for room in rooms}

        for index, row in df.iterrows():
            row_number = index + 2
            warnings: list[str] = []
            room_id = _to_int(row.get("room_id"))
            if room_id is None:
                self._warnings.append(f"payments row {row_number} has no room_id and was skipped.")
                continue

            room = room_by_id.get(room_id)
            rent_required = room.rent_required if room else None
            if room is None:
                warnings.append(f"room_id {room_id} does not exist in room_record.")

            rent_start_date = _parse_date(row.get("rent_start_date"), "rent_start_date", row_number, warnings)
            rent_end_date = _parse_date(row.get("rent_end_date"), "rent_end_date", row_number, warnings)
            payment_date = _parse_date(row.get("payment_date"), "payment_date", row_number, warnings)

            amount_due = _to_money(row.get("amount_due"))
            if _normalize_yes_no(rent_required) == "N":
                amount_due = 0

            original_room_status = _clean_text(row.get("room_status")) or None
            room_status = _normalize_room_status(original_room_status)
            calculated_status = "N/A" if _normalize_yes_no(rent_required) == "N" else self._calculate_payment_status(
                room_status=room_status,
                rent_start_date=rent_start_date,
                rent_end_date=rent_end_date,
                payment_date=payment_date,
                warnings=warnings,
                row_number=row_number,
            )

            payments.append(
                Payment(
                    row_number=row_number,
                    room_id=room_id,
                    rent_start_date=_date_to_string(rent_start_date),
                    rent_end_date=_date_to_string(rent_end_date),
                    amount_due=amount_due,
                    amount_paid=_to_money(row.get("amount_paid")),
                    payment_date=_date_to_string(payment_date),
                    original_payment_status=_clean_text(row.get("payment_status")) or None,
                    calculated_payment_status=calculated_status,
                    original_room_status=original_room_status,
                    room_status=room_status,
                    payment_method=_normalize_payment_method(row.get("payment_method")),
                    tenant_name=_clean_text(row.get("tenant_name")) or None,
                    tenant_ph=_clean_text(row.get("tenant_ph")) or None,
                    ac=_normalize_yes_no(row.get("ac")),
                    rent_required=rent_required,
                    record_status=_normalize_record_status(row.get("record_status")),
                    source=_clean_text(row.get("source")) or None,
                    notes=_clean_text(row.get("notes")) or None,
                    warnings=warnings,
                )
            )
        return payments

    def _apply_latest_payment_status_to_rooms(self) -> None:
        if self._rooms is None or self._payments is None:
            return

        latest_payment_by_room = self._latest_payment_by_room(
            [payment for payment in self._payments if _is_active_payment(payment)]
        )
        for room in self._rooms:
            latest_payment = latest_payment_by_room.get(room.room_id)
            if latest_payment and latest_payment.room_status in {"Occupied", "Empty"}:
                room.current_status = latest_payment.room_status

    def _latest_payment_by_room(self, payments: list[Payment]) -> dict[int, Payment]:
        latest: dict[int, Payment] = {}
        for payment in payments:
            if payment.room_id is None:
                continue
            if not _is_active_payment(payment):
                continue

            current_latest = latest.get(payment.room_id)
            if current_latest is None or _payment_sort_key(payment) > _payment_sort_key(current_latest):
                latest[payment.room_id] = payment
        return latest

    def _calculate_payment_status(
        self,
        *,
        room_status: str | None,
        rent_start_date: date | None,
        rent_end_date: date | None,
        payment_date: date | None,
        warnings: list[str],
        row_number: int,
    ) -> str:
        if room_status == "Empty":
            return "N/A"

        if rent_start_date is None:
            warnings.append(
                f"payments row {row_number} cannot calculate status without rent_start_date."
            )
            return "Unknown"

        if payment_date is not None:
            return "Late" if payment_date > rent_start_date + timedelta(days=7) else "Paid"

        if self.today > rent_start_date + timedelta(days=7):
            return "Unpaid"

        return "Pending"


def _normalize_column(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0") and text.replace(".", "", 1).isdigit():
        return text[:-2]
    return text


def _normalize_yes_no(value: Any) -> str | None:
    text = _clean_text(value).upper()
    if text in {"YES", "TRUE"}:
        return "Y"
    if text in {"NO", "FALSE"}:
        return "N"
    return text if text in {"Y", "N"} else (text or None)


def _normalize_room_status(value: Any) -> str | None:
    text = _clean_text(value).lower()
    if text in {"ocuppied", "occupied"}:
        return "Occupied"
    if text == "empty":
        return "Empty"
    return _clean_text(value) or None


def _normalize_payment_method(value: Any) -> str | None:
    text = _clean_text(value).lower()
    if text == "transfer":
        return "Transfer"
    if text == "cash":
        return "Cash"
    return _clean_text(value) or None


def _normalize_record_status(value: Any) -> str:
    text = _clean_text(value).lower()
    if text == "cancelled":
        return "Cancelled"
    if text == "corrected":
        return "Corrected"
    return "Active"


def _is_active_payment(payment: Payment) -> bool:
    return _normalize_record_status(payment.record_status) == "Active"


def _to_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _to_money(value: Any) -> float:
    if value is None or pd.isna(value):
        return 0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.-]", "", str(value))
    if cleaned in {"", "-", "."}:
        return 0
    try:
        return float(cleaned)
    except ValueError:
        return 0


def _parse_date(value: Any, field_name: str, row_number: int, warnings: list[str]) -> date | None:
    if value is None or pd.isna(value):
        return None

    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        warnings.append(f"payments row {row_number} has invalid {field_name}: {value!r}.")
        return None
    return parsed.date()


def _date_to_string(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _payment_sort_key(payment: Payment) -> tuple[str, str, int]:
    return (
        payment.rent_start_date or "",
        payment.rent_end_date or "",
        payment.row_number,
    )

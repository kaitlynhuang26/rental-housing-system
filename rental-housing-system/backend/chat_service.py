from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Protocol

from .ai_agent import GroqAgentError, GroqIntentAgent
from .excel_service import ExcelDataError, RentalExcelService
from .models import (
    ChatConfirmResponse,
    ChatResponse,
    ExtractedIntent,
    OperationResponse,
    Payment,
    PendingAction,
)
from .pending_actions import PendingActionError, PendingActionStore
from .update_service import RentalUpdateService


class IntentAgent(Protocol):
    def extract_intent(self, message: str, today: date | None = None) -> ExtractedIntent:
        ...


class ChatService:
    def __init__(
        self,
        *,
        excel_service: RentalExcelService | None = None,
        update_service: RentalUpdateService | None = None,
        pending_store: PendingActionStore | None = None,
        intent_agent: IntentAgent | None = None,
        today: date | None = None,
    ):
        self.today = today or date.today()
        self.excel_service = excel_service or RentalExcelService(today=self.today)
        self.update_service = update_service or RentalUpdateService(today=self.today)
        self.pending_store = pending_store or PendingActionStore()
        self.intent_agent = intent_agent

    def chat(self, message: str) -> ChatResponse:
        cleaned_message = message.strip()
        if not cleaned_message:
            return ChatResponse(type="follow_up", message="Please type a message first.")

        if self._is_undo_request(cleaned_message):
            return self._preview_undo(cleaned_message)

        direct_answer = self._direct_read_only_answer(cleaned_message)
        if direct_answer is not None:
            return direct_answer

        try:
            intent = self._agent().extract_intent(cleaned_message, today=self.today)
        except GroqAgentError as error:
            return ChatResponse(type="error", message=str(error))

        intent = self._normalize_relative_dates(intent)

        if intent.intent == "unknown":
            return ChatResponse(
                type="follow_up",
                message="I am not sure what you want to do. Can you say it another way?",
                extracted_intent=intent,
            )

        if intent.intent.startswith("question_"):
            if intent.confidence < 0.45 and intent.intent == "question_unknown":
                return ChatResponse(
                    type="follow_up",
                    message="I am not sure what you want to ask. Can you say it another way?",
                    extracted_intent=intent,
                )
            if intent.needs_follow_up and intent.intent in {"question_room_status", "question_payment_status"}:
                return self._follow_up(intent)
            return self._answer_question(intent, cleaned_message)

        return self._preview_update(intent, cleaned_message)

    def confirm(self, action_id: str, confirm: bool) -> ChatConfirmResponse:
        try:
            action = self.pending_store.get(action_id)
            if action.status != "pending":
                raise PendingActionError(
                    f"Pending action {action_id} is already {action.status}."
                )
            if not confirm:
                self.pending_store.mark_cancelled(action_id)
                return ChatConfirmResponse(
                    success=True,
                    message="Okay, I cancelled that pending action. Excel was not updated.",
                    action_id=action_id,
                )

            result = self._run_backend_action(
                action.backend_action,
                {**action.request_payload, "preview": False},
            )
            self.pending_store.mark_confirmed(action_id)
            return ChatConfirmResponse(
                success=True,
                message="Saved. Excel was updated and a backup/audit log entry was created.",
                action_id=action_id,
                result=result,
            )
        except (PendingActionError, ExcelDataError) as error:
            return ChatConfirmResponse(
                success=False,
                message=str(error),
                action_id=action_id,
            )

    def pending_actions(self) -> list[PendingAction]:
        return self.pending_store.list_pending()

    def _agent(self) -> IntentAgent:
        if self.intent_agent is None:
            self.intent_agent = GroqIntentAgent()
        return self.intent_agent

    def _answer_question(self, intent: ExtractedIntent, original_message: str) -> ChatResponse:
        if intent.intent == "question_empty_rooms":
            rooms = self.excel_service.get_empty_rooms()
            ids = [room.room_id for room in rooms]
            message = (
                f"There are {len(ids)} empty rooms: {', '.join(map(str, ids))}."
                if ids
                else "There are no empty rooms right now."
            )
            return ChatResponse(type="answer", message=message, data=[room.model_dump() for room in rooms])

        if intent.intent == "question_late_payments":
            payments = self._filter_payments_by_month(
                self.excel_service.get_late_payments(),
                original_message,
            )
            return ChatResponse(
                type="answer",
                message=self._room_number_list_message("late payment", payments, original_message),
                data=[payment.model_dump() for payment in payments],
            )

        if intent.intent == "question_unpaid_payments":
            payments = self._filter_payments_by_month(
                self.excel_service.get_unpaid_payments(),
                original_message,
            )
            return ChatResponse(
                type="answer",
                message=self._room_number_list_message("unpaid payment", payments, original_message),
                data=[payment.model_dump() for payment in payments],
            )

        if intent.intent == "question_summary":
            summary = self.excel_service.get_summary()
            message = (
                f"Summary: {summary.total_rooms} rooms, {summary.occupied_rooms} occupied, "
                f"{summary.empty_rooms} empty, {self._rupiah(summary.total_amount_paid)} paid, "
                f"{self._rupiah(summary.total_unpaid_amount)} unpaid."
            )
            return ChatResponse(type="answer", message=message, data=summary.model_dump())

        if intent.intent in {"question_room_status", "question_payment_status"}:
            missing = self._missing(intent, ["room_id"])
            if missing:
                return self._follow_up_with_fields(intent, missing)
            detail = self.excel_service.get_room_detail(intent.room_id or 0)
            latest = self._latest_payment(detail.payments)
            if intent.intent == "question_room_status":
                tenant = f" Tenant: {latest.tenant_name}." if latest and latest.tenant_name else ""
                message = (
                    f"Room {detail.room.room_id} is {detail.room.current_status}. "
                    f"Occupants: {detail.room.current_occupants}.{tenant}"
                )
            else:
                if latest is None:
                    message = f"Room {detail.room.room_id} has no payment history."
                else:
                    message = (
                        f"Room {detail.room.room_id}'s latest payment status is "
                        f"{latest.calculated_payment_status}. Paid "
                        f"{self._rupiah(latest.amount_paid)} of {self._rupiah(latest.amount_due)}."
                    )
            return ChatResponse(
                type="answer",
                message=message,
                data=detail.model_dump(),
            )

        return self._answer_unknown_question(intent, original_message)

    def _direct_read_only_answer(self, message: str) -> ChatResponse | None:
        lower = message.lower()
        invalid_room_response = self._invalid_room_response(message)
        if invalid_room_response is not None:
            return invalid_room_response

        if any(phrase in lower for phrase in ["new tenant", "move in", "moved in"]):
            return None

        if "previous" in lower and "empty" in lower:
            return self._previously_empty_answer(message)

        if "previously" in lower:
            return ChatResponse(
                type="follow_up",
                message="Do you mean previous tenants for a specific room, or rooms that were previously occupied? Please include the room number or month.",
            )

        if re.search(r"\bhow many rooms\b", lower) and "empty" not in lower:
            rooms = self.excel_service.get_rooms()
            return ChatResponse(
                type="answer",
                message=f"There are {len(rooms)} rooms.",
                data=[room.model_dump() for room in rooms],
            )

        if "empty" in lower and "room" in lower:
            rooms = self.excel_service.get_empty_rooms()
            ids = [room.room_id for room in rooms]
            return ChatResponse(
                type="answer",
                message=f"Empty rooms: {', '.join(map(str, ids))}." if ids else "There are no empty rooms right now.",
                data=[room.model_dump() for room in rooms],
            )

        if (
            "ac" in lower
            and ("which" in lower or "what" in lower or "show" in lower or "list" in lower)
            and not any(word in lower for word in ["rent", "change", "changed", "add", "moved"])
        ):
            payments = self._current_ac_payments()
            ids = [payment.room_id for payment in payments if payment.room_id is not None]
            return ChatResponse(
                type="answer",
                message=f"Rooms with AC: {', '.join(map(str, ids))}." if ids else "No rooms currently show AC.",
                data=[payment.model_dump() for payment in payments],
            )

        occupant_count = self._occupant_count_from_message(lower)
        if occupant_count is not None:
            rooms = [
                room for room in self.excel_service.get_rooms()
                if room.current_occupants == occupant_count
            ]
            ids = [room.room_id for room in rooms]
            return ChatResponse(
                type="answer",
                message=(
                    f"Rooms with {occupant_count} occupant(s): {', '.join(map(str, ids))}."
                    if ids
                    else f"No rooms currently show {occupant_count} occupant(s)."
                ),
                data=[room.model_dump() for room in rooms],
            )

        if "transfer" in lower and "collect" in lower:
            return self._collected_payment_answer(message, "Transfer")

        if "cash" in lower and "collect" in lower:
            return self._collected_payment_answer(message, "Cash")

        if self._is_collection_question(lower):
            return self._all_collected_payment_answer(message)

        if "paid late" in lower or "late payment" in lower:
            payments = self._filter_payments_by_month(
                self.excel_service.get_late_payments(),
                message,
            )
            return ChatResponse(
                type="answer",
                message=self._room_number_list_message("late payment", payments, message),
                data=[payment.model_dump() for payment in payments],
            )

        if "unpaid" in lower:
            payments = self._filter_payments_by_month(
                self.excel_service.get_unpaid_payments(),
                message,
            )
            message_text = self._room_number_list_message("unpaid payment", payments, message)
            if not payments and self._has_stale_latest_periods():
                message_text += " Some rooms may need auto rollover before current-month unpaid rooms can appear."
            return ChatResponse(
                type="answer",
                message=message_text,
                data=[payment.model_dump() for payment in payments],
            )

        historical_tenant_answer = self._historical_tenant_answer(message)
        if historical_tenant_answer is not None:
            return historical_tenant_answer

        return None

    def _answer_unknown_question(self, intent: ExtractedIntent, message: str) -> ChatResponse:
        lower = message.lower()
        rooms = self.excel_service.get_rooms()
        if "ac" in lower:
            ac_payments = self._current_ac_payments()
            ids = [payment.room_id for payment in ac_payments if payment.room_id is not None]
            return ChatResponse(
                type="answer",
                message=f"Rooms with AC: {', '.join(map(str, ids))}." if ids else "No rooms currently show AC.",
                data=[payment.model_dump() for payment in ac_payments],
                extracted_intent=intent,
            )
        if "occupied" in lower:
            occupied = [room for room in rooms if room.current_status == "Occupied"]
            ids = [room.room_id for room in occupied]
            return ChatResponse(
                type="answer",
                message=f"Occupied rooms: {', '.join(map(str, ids))}." if ids else "No rooms are occupied right now.",
                data=[room.model_dump() for room in occupied],
                extracted_intent=intent,
            )
        return ChatResponse(
            type="follow_up",
            message="I can answer summaries, empty rooms, late payments, unpaid rooms, room status, payment status, occupied rooms, and AC rooms. What would you like to ask?",
            extracted_intent=intent,
        )

    def _preview_update(self, intent: ExtractedIntent, original_message: str) -> ChatResponse:
        missing = self._missing_update_fields(intent)
        inferred_amount = False
        amount_is_missing = (
            intent.intent == "payment_update"
            and (intent.amount_paid is None or intent.amount_paid <= 0)
        )
        if amount_is_missing and intent.room_id is not None:
            latest = self._latest_payment_for_room(intent.room_id)
            if latest is not None and latest.amount_due > 0:
                intent = intent.model_copy(update={"amount_paid": latest.amount_due})
                inferred_amount = True
                missing = [field for field in missing if field != "amount_paid"]

        if missing:
            return self._follow_up_with_fields(intent, missing)

        if intent.intent in {"rent_change", "ac_change"}:
            rent_guardrail = self._rent_change_guardrail(intent, original_message)
            if rent_guardrail is not None:
                return rent_guardrail
        if intent.intent == "payment_update":
            payment_guardrail = self._payment_update_guardrail(intent, original_message)
            if payment_guardrail is not None:
                return payment_guardrail

        backend_action, payload = self._payload_for_update(intent, original_message)
        try:
            preview = self._run_backend_action(backend_action, payload)
        except ExcelDataError as error:
            return ChatResponse(
                type="error",
                message=error.detail,
                extracted_intent=intent,
            )

        action = self.pending_store.create(
            intent=intent.intent,
            backend_action=backend_action,
            extracted_fields=intent.model_dump(mode="json"),
            request_payload=payload,
            preview_response=preview,
            user_message=original_message,
        )
        return ChatResponse(
            type="confirmation_required",
            action_id=action.action_id,
            message=self._confirmation_message(intent, preview, inferred_amount),
            preview=preview,
            extracted_intent=intent,
        )

    def _payload_for_update(self, intent: ExtractedIntent, original_message: str) -> tuple[str, dict[str, Any]]:
        summary = intent.user_message_summary or original_message
        if intent.intent == "payment_update":
            if self._is_next_period_request(original_message):
                payload = {
                    "room_id": intent.room_id,
                    "amount_paid": intent.amount_paid,
                    "payment_date": intent.payment_date,
                    "payment_method": intent.payment_method,
                    "preview": True,
                    "user_message": summary,
                }
                return "record_next_period_payment", self._drop_none(payload)
            payload = {
                "room_id": intent.room_id,
                "amount_paid": intent.amount_paid,
                "payment_date": intent.payment_date,
                "payment_method": intent.payment_method,
                "rent_start_date": intent.rent_start_date,
                "rent_end_date": intent.rent_end_date,
                "preview": True,
                "user_message": summary,
            }
            return "update_current_payment", self._drop_none(payload)

        if intent.intent == "move_out":
            return "move_out_tenant", {
                "room_id": intent.room_id,
                "move_out_date": intent.move_out_date,
                "preview": True,
                "user_message": summary,
            }

        if intent.intent == "move_in":
            payload = {
                "room_id": intent.room_id,
                "tenant_name": intent.tenant_name,
                "tenant_ph": intent.tenant_ph,
                "rent_start_date": intent.rent_start_date,
                "rent_end_date": intent.rent_end_date,
                "amount_due": intent.amount_due,
                "current_occupants": intent.current_occupants,
                "ac": intent.ac,
                "amount_paid": intent.amount_paid or 0,
                "payment_date": intent.payment_date,
                "payment_method": intent.payment_method,
                "preview": True,
                "user_message": summary,
            }
            return "move_in_tenant", self._drop_none(payload)

        if intent.intent in {"rent_change", "ac_change"}:
            payload = {
                "room_id": intent.room_id,
                "new_amount_due": intent.new_amount_due,
                "effective_start_date": intent.rent_start_date,
                "ac": intent.ac,
                "current_occupants": intent.current_occupants,
                "preview": True,
                "user_message": summary,
            }
            return "update_room_rent", self._drop_none(payload)

        if intent.intent == "auto_rollover":
            requested_room = self._room_id_from_message(original_message)
            payload: dict[str, Any] = {"preview": True}
            if requested_room is not None:
                payload["included_room_ids"] = [requested_room]
            return "auto_rollover_rental_periods", payload

        raise ExcelDataError("I understood this as an update, but I do not know which backend action to use.")

    def _rent_change_guardrail(
        self,
        intent: ExtractedIntent,
        original_message: str,
    ) -> ChatResponse | None:
        if intent.room_id is None or intent.new_amount_due is None:
            return None

        lower = original_message.lower()
        has_period_hint = any(
            phrase in lower
            for phrase in [
                "current",
                "this month",
                "this period",
                "now",
                "today",
                "next month",
                "next period",
                "future",
                "starting",
                "effective",
                "from ",
            ]
        ) or intent.rent_start_date is not None
        if not has_period_hint:
            return ChatResponse(
                type="follow_up",
                message=(
                    f"Should Room {intent.room_id}'s rent change apply to the current month, "
                    "or to the next rental period? Please include the effective start date if it is for a future period."
                ),
                missing_fields=["effective_start_date"],
                extracted_intent=intent,
            )

        latest = self._latest_payment_for_room(intent.room_id)
        if latest is None:
            return None
        is_current_period = any(
            phrase in lower for phrase in ["current", "this month", "this period", "now", "today"]
        ) and intent.rent_start_date is None
        if is_current_period and latest.amount_due == intent.new_amount_due:
            return ChatResponse(
                type="answer",
                message=(
                    f"Room {intent.room_id}'s current recorded rent is already "
                    f"{self._rupiah(intent.new_amount_due)}. No Excel update is needed."
                ),
                data=latest.model_dump(),
                extracted_intent=intent,
            )
        return None

    def _payment_update_guardrail(
        self,
        intent: ExtractedIntent,
        original_message: str,
    ) -> ChatResponse | None:
        if self._is_next_period_request(original_message):
            return None
        if intent.room_id is None or intent.rent_start_date or intent.rent_end_date:
            return None
        latest = self._latest_payment_for_room(intent.room_id)
        if latest is None:
            return ChatResponse(
                type="follow_up",
                message=(
                    f"Room {intent.room_id} does not have an active payment period to update. "
                    "Should I create the next rental period first, or is this a new move-in?"
                ),
                missing_fields=["rent_start_date", "rent_end_date"],
                extracted_intent=intent,
            )

        latest_is_finished = (
            latest.payment_date is not None
            or latest.calculated_payment_status in {"Paid", "Late"}
            or (latest.amount_due > 0 and latest.amount_paid >= latest.amount_due)
        )
        partial_payment = (
            intent.amount_paid is not None
            and latest.amount_due > 0
            and intent.amount_paid < latest.amount_due
        )
        if latest_is_finished and partial_payment:
            return ChatResponse(
                type="follow_up",
                message=(
                    f"Room {intent.room_id}'s latest recorded period "
                    f"({latest.rent_start_date} to {latest.rent_end_date}) is already paid. "
                    "Do you want this Rp amount to be a payment for the next rental period? "
                    "If yes, run auto rollover first or specify the next rent_start_date and rent_end_date."
                ),
                missing_fields=["rent_start_date", "rent_end_date"],
                extracted_intent=intent,
            )
        return None

    def _run_backend_action(self, backend_action: str, payload: dict[str, Any]) -> OperationResponse:
        if backend_action == "update_current_payment":
            return self.update_service.update_current_payment(**payload)
        if backend_action == "record_next_period_payment":
            return self.update_service.record_next_period_payment(**payload)
        if backend_action == "move_out_tenant":
            return self.update_service.move_out_tenant(**payload)
        if backend_action == "move_in_tenant":
            return self.update_service.move_in_tenant(**payload)
        if backend_action == "update_room_rent":
            return self.update_service.update_room_rent(**payload)
        if backend_action == "auto_rollover_rental_periods":
            return self.update_service.auto_rollover_rental_periods(**payload)
        if backend_action == "undo_last_change":
            return self.update_service.undo_last_change(**payload)
        raise ExcelDataError(f"Unknown backend action: {backend_action}")

    def _missing_update_fields(self, intent: ExtractedIntent) -> list[str]:
        required_by_intent = {
            "payment_update": ["room_id", "amount_paid", "payment_date", "payment_method"],
            "move_out": ["room_id", "move_out_date"],
            "move_in": [
                "room_id",
                "tenant_name",
                "rent_start_date",
                "rent_end_date",
                "amount_due",
                "current_occupants",
                "ac",
            ],
            "rent_change": ["room_id", "new_amount_due"],
            "ac_change": ["room_id", "new_amount_due", "ac"],
            "auto_rollover": [],
        }
        return self._missing(intent, required_by_intent.get(intent.intent, []))

    def _missing(self, intent: ExtractedIntent, fields: list[str]) -> list[str]:
        missing = []
        for field in fields:
            value = getattr(intent, field)
            if value is None or value == "":
                missing.append(field)
        return missing

    def _follow_up(self, intent: ExtractedIntent) -> ChatResponse:
        message = " ".join(intent.follow_up_questions) if intent.follow_up_questions else "I need a bit more information."
        return ChatResponse(
            type="follow_up",
            message=message,
            missing_fields=intent.missing_fields,
            extracted_intent=intent,
        )

    def _follow_up_with_fields(self, intent: ExtractedIntent, fields: list[str]) -> ChatResponse:
        questions = {
            "room_id": "Which room is this for?",
            "amount_paid": "How much did they pay?",
            "payment_date": "What date did they pay?",
            "payment_method": "Did they pay by cash or transfer?",
            "move_out_date": "What date did they move out?",
            "tenant_name": "What is the tenant name?",
            "rent_start_date": "What is the rent start date?",
            "rent_end_date": "What is the rent end date?",
            "amount_due": "What is the agreed rent amount?",
            "current_occupants": "How many people will stay?",
            "ac": "Is there AC? Please answer Y or N.",
            "new_amount_due": "What is the new rent amount?",
        }
        return ChatResponse(
            type="follow_up",
            message=" ".join(questions.get(field, f"Please provide {field}.") for field in fields),
            missing_fields=fields,
            extracted_intent=intent,
        )

    def _confirmation_message(
        self,
        intent: ExtractedIntent,
        preview: OperationResponse,
        inferred_amount: bool,
    ) -> str:
        prefix = ""
        if inferred_amount and intent.amount_paid is not None:
            prefix = f"I found the current amount due is {self._rupiah(intent.amount_paid)}. "

        if intent.intent == "payment_update":
            period = self._period_from_preview(preview)
            return (
                f"{prefix}I will mark Room {intent.room_id} as paid by "
                f"{intent.payment_method} on {intent.payment_date} for "
                f"{self._rupiah(intent.amount_paid or 0)}{period}. Should I save this?"
            )
        if intent.intent == "move_out":
            return f"I will mark Room {intent.room_id} as moved out on {intent.move_out_date}. Should I save this?"
        if intent.intent == "move_in":
            return (
                f"I will add {intent.tenant_name} as the tenant for Room {intent.room_id}, "
                f"from {intent.rent_start_date} to {intent.rent_end_date}, rent "
                f"{self._rupiah(intent.amount_due or 0)}. Should I save this?"
            )
        if intent.intent in {"rent_change", "ac_change"}:
            return (
                f"I will update Room {intent.room_id}'s rent to "
                f"{self._rupiah(intent.new_amount_due or 0)}"
                f"{' and AC to ' + intent.ac if intent.ac else ''}. Should I save this?"
            )
        if intent.intent == "auto_rollover":
            return (
                f"Auto rollover would create {len(preview.rows_to_create)} row(s). "
                "Should I save these new rental periods?"
            )
        return "I prepared a preview. Should I save this?"

    def _preview_undo(self, original_message: str) -> ChatResponse:
        try:
            preview = self.update_service.undo_last_change(preview=True)
        except ExcelDataError as error:
            return ChatResponse(type="error", message=error.detail)
        action = self.pending_store.create(
            intent="undo_last_change",
            backend_action="undo_last_change",
            extracted_fields={},
            request_payload={
                "preview": True,
                "backup_file": (
                    preview.rows_to_create[0].get("backup_file")
                    if preview.rows_to_create
                    else None
                ),
            },
            preview_response=preview,
            user_message=original_message,
        )
        backup_name = (
            preview.rows_to_create[0].get("backup_file")
            if preview.rows_to_create
            else "the latest backup"
        )
        return ChatResponse(
            type="confirmation_required",
            action_id=action.action_id,
            message=(
                f"I can restore the workbook using {backup_name}, which is the state "
                "before the last saved change. I will first back up the current workbook. "
                "Should I undo the last change?"
            ),
            preview=preview,
        )

    def _is_undo_request(self, message: str) -> bool:
        lower = message.lower()
        return any(
            phrase in lower
            for phrase in [
                "undo last change",
                "reverse last change",
                "revert last change",
                "undo the last update",
            ]
        )

    def _is_next_period_request(self, message: str) -> bool:
        lower = message.lower()
        return any(
            phrase in lower
            for phrase in [
                "next rental period",
                "next rent period",
                "next period",
                "next month",
            ]
        )

    def _period_from_preview(self, preview: OperationResponse) -> str:
        if preview.rows_to_create:
            row = preview.rows_to_create[0]
            start = row.get("rent_start_date")
            end = row.get("rent_end_date")
            if start and end:
                return f" for rental period {start} to {end}"
        return ""

    def _payment_list_message(self, label: str, payments: list[Payment]) -> str:
        if not payments:
            return f"There are no {label} rows."
        room_ids = sorted({payment.room_id for payment in payments if payment.room_id is not None})
        return f"There are {len(payments)} {label} row(s), covering room(s): {', '.join(map(str, room_ids))}."

    def _collected_payment_answer(self, message: str, payment_method: str) -> ChatResponse:
        room_id = self._room_id_from_message(message)
        payments = [
            payment for payment in self.excel_service.get_payments()
            if payment.payment_method == payment_method
            and (room_id is None or payment.room_id == room_id)
        ]
        payments = self._filter_payments_for_collection_question(payments, message)
        unclassified_paid = [
            payment for payment in self.excel_service.get_payments()
            if payment.amount_paid > 0
            and payment.payment_method not in {"Transfer", "Cash"}
            and (room_id is None or payment.room_id == room_id)
        ]
        unclassified_paid = self._filter_payments_for_collection_question(unclassified_paid, message)
        total = sum(payment.amount_paid for payment in payments)
        unclassified_total = sum(payment.amount_paid for payment in unclassified_paid)
        target = f" from Room {room_id}" if room_id is not None else ""
        month = self._month_name_from_message(message)
        month_text = f" in {month}" if month else ""
        message_text = f"{payment_method} collected{target}{month_text}: {self._rupiah(total)} based on rent_start_date."
        if unclassified_total:
            message_text += (
                f" There is also {self._rupiah(unclassified_total)} paid{target} "
                "with no payment method recorded, so it is not counted as transfer or cash."
            )
        return ChatResponse(
            type="answer",
            message=message_text,
            data={
                "matched_payments": [payment.model_dump() for payment in payments],
                "unclassified_paid": [payment.model_dump() for payment in unclassified_paid],
            },
        )

    def _is_collection_question(self, lower_message: str) -> bool:
        if not any(word in lower_message for word in ["collect", "collected", "collection", "received"]):
            return False
        return any(
            word in lower_message
            for word in [
                "money",
                "payment",
                "payments",
                "paid",
                "rent",
                "revenue",
                "income",
                "total",
                "amount",
            ]
        )

    def _all_collected_payment_answer(self, message: str) -> ChatResponse:
        room_id = self._room_id_from_message(message)
        month = self._month_name_from_message(message)
        if room_id is None and month is None:
            summary = self.excel_service.get_summary()
            unclassified_total = max(
                summary.total_amount_paid
                - summary.total_transfer_collected
                - summary.total_cash_collected,
                0,
            )
            message_text = (
                f"Total money collected: {self._rupiah(summary.total_amount_paid)} "
                f"(Transfer {self._rupiah(summary.total_transfer_collected)}, "
                f"Cash {self._rupiah(summary.total_cash_collected)}"
            )
            if unclassified_total:
                message_text += f", unclassified {self._rupiah(unclassified_total)}"
            message_text += ")."
            return ChatResponse(
                type="answer",
                message=message_text,
                data=summary.model_dump(),
            )

        payments = [
            payment for payment in self.excel_service.get_payments()
            if payment.amount_paid > 0
            and (room_id is None or payment.room_id == room_id)
        ]
        payments = self._filter_payments_for_collection_question(payments, message)
        total = sum(payment.amount_paid for payment in payments)
        transfer_total = sum(payment.amount_paid for payment in payments if payment.payment_method == "Transfer")
        cash_total = sum(payment.amount_paid for payment in payments if payment.payment_method == "Cash")
        unclassified_total = sum(
            payment.amount_paid
            for payment in payments
            if payment.payment_method not in {"Transfer", "Cash"}
        )
        target = f" from Room {room_id}" if room_id is not None else ""
        month_text = f" in {month}" if month else ""
        message_text = (
            f"Total money collected{target}{month_text}: {self._rupiah(total)} "
            f"based on rent_start_date "
            f"(Transfer {self._rupiah(transfer_total)}, Cash {self._rupiah(cash_total)}"
        )
        if unclassified_total:
            message_text += f", unclassified {self._rupiah(unclassified_total)}"
        message_text += ")."
        return ChatResponse(
            type="answer",
            message=message_text,
            data=[payment.model_dump() for payment in payments],
        )

    def _current_ac_payments(self) -> list[Payment]:
        valid_room_ids = self._valid_room_ids()
        latest_by_room: dict[int, Payment] = {}
        for payment in self.excel_service.get_payments():
            if (
                payment.room_id is None
                or payment.room_id not in valid_room_ids
                or payment.record_status not in {None, "Active"}
            ):
                continue
            current = latest_by_room.get(payment.room_id)
            if current is None or self._payment_sort_key(payment) > self._payment_sort_key(current):
                latest_by_room[payment.room_id] = payment
        return [
            payment for payment in latest_by_room.values()
            if payment.room_status == "Occupied" and payment.ac == "Y"
        ]

    def _previously_empty_answer(self, message: str) -> ChatResponse:
        room_id = self._room_id_from_message(message)
        valid_room_ids = self._valid_room_ids()
        empty_payments = [
            payment for payment in self.excel_service.get_payments()
            if payment.room_status == "Empty"
            and payment.room_id in valid_room_ids
            and (room_id is None or payment.room_id == room_id)
        ]
        month_number = self._month_number_from_message(message)
        if month_number is not None:
            empty_payments = [
                payment for payment in empty_payments
                if self._date_month(payment.rent_start_date) == month_number
                or self._date_month(payment.rent_end_date) == month_number
            ]

        if not empty_payments:
            target = f" Room {room_id}" if room_id is not None else ""
            month = f" in {self._month_name_from_message(message)}" if month_number else ""
            return ChatResponse(
                type="answer",
                message=f"I do not see any previously empty records for{target}{month}.",
                data=[],
            )

        descriptions = []
        for payment in empty_payments:
            month_name = self._month_name_from_payment(payment)
            room_text = f"Room {payment.room_id}"
            if month_name:
                descriptions.append(f"{room_text} was empty in {month_name}")
            else:
                descriptions.append(f"{room_text} was empty")

        return ChatResponse(
            type="answer",
            message="; ".join(descriptions) + ".",
            data=[payment.model_dump() for payment in empty_payments],
        )

    def _room_number_list_message(
        self,
        label: str,
        payments: list[Payment],
        original_message: str,
    ) -> str:
        month_name = self._month_name_from_message(original_message)
        suffix = f" in {month_name}" if month_name else ""
        room_ids = sorted({payment.room_id for payment in payments if payment.room_id is not None})
        if not room_ids:
            return f"No rooms had {label}s{suffix}."
        return f"Rooms with {label}s{suffix}: {', '.join(map(str, room_ids))}."

    def _filter_payments_by_month(
        self,
        payments: list[Payment],
        original_message: str,
    ) -> list[Payment]:
        month_number = self._month_number_from_message(original_message)
        if month_number is None:
            return payments
        return [
            payment for payment in payments
            if self._date_month(payment.payment_date) == month_number
            or self._date_month(payment.rent_start_date) == month_number
        ]

    def _filter_payments_for_collection_question(
        self,
        payments: list[Payment],
        original_message: str,
    ) -> list[Payment]:
        return self._filter_payments_by_rent_month(payments, original_message)

    def _filter_payments_by_rent_month(
        self,
        payments: list[Payment],
        original_message: str,
    ) -> list[Payment]:
        month_number = self._month_number_from_message(original_message)
        if month_number is None:
            return payments
        return [
            payment for payment in payments
            if self._date_month(payment.rent_start_date) == month_number
        ]

    def _month_number_from_message(self, message: str) -> int | None:
        lowered = message.lower()
        months = {
            "january": 1,
            "jan": 1,
            "february": 2,
            "feb": 2,
            "march": 3,
            "mar": 3,
            "april": 4,
            "apr": 4,
            "may": 5,
            "june": 6,
            "jun": 6,
            "july": 7,
            "jul": 7,
            "august": 8,
            "aug": 8,
            "september": 9,
            "sep": 9,
            "october": 10,
            "oct": 10,
            "november": 11,
            "nov": 11,
            "december": 12,
            "dec": 12,
        }
        for name, number in months.items():
            if name in lowered:
                return number
        return None

    def _month_name_from_message(self, message: str) -> str | None:
        month_number = self._month_number_from_message(message)
        if month_number is None:
            return None
        names = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        return names[month_number - 1]

    def _date_month(self, value: str | None) -> int | None:
        if not value or len(value) < 7:
            return None
        try:
            return int(value[5:7])
        except ValueError:
            return None

    def _room_id_from_message(self, message: str) -> int | None:
        match = re.search(r"\broom\s+(\d+)\b", message.lower())
        return int(match.group(1)) if match else None

    def _valid_room_ids(self) -> set[int]:
        return {room.room_id for room in self.excel_service.get_rooms()}

    def _invalid_room_response(self, message: str) -> ChatResponse | None:
        room_id = self._room_id_from_message(message)
        if room_id is None:
            return None
        valid_room_ids = [room.room_id for room in self.excel_service.get_rooms()]
        if room_id in valid_room_ids:
            return None
        return ChatResponse(
            type="error",
            message=(
                f"Room {room_id} is not a valid room. Valid room IDs are: "
                f"{', '.join(map(str, valid_room_ids))}."
            ),
            data={"valid_room_ids": valid_room_ids},
        )

    def _occupant_count_from_message(self, message: str) -> int | None:
        patterns = [
            r"\bhas\s+(\d+)\s+occupant",
            r"\bwith\s+(\d+)\s+occupant",
            r"\b(\d+)\s+occupant",
            r"\b(\d+)\s+people",
            r"\b(\d+)\s+person",
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return int(match.group(1))
        return None

    def _has_stale_latest_periods(self) -> bool:
        for room in self.excel_service.get_rooms():
            if room.current_status != "Occupied":
                continue
            latest = self._latest_payment_for_room(room.room_id)
            if latest is None or not latest.rent_end_date:
                continue
            try:
                latest_end = date.fromisoformat(latest.rent_end_date)
            except ValueError:
                continue
            if latest_end < self.today:
                return True
        return False

    def _historical_tenant_answer(self, message: str) -> ChatResponse | None:
        lower = message.lower()
        if not any(word in lower for word in ["staying", "stayed", "tenant", "who is in"]):
            return None
        room_id = self._room_id_from_message(message)
        if room_id is None:
            return None

        detail = self.excel_service.get_room_detail(room_id)
        month_number = self._month_number_from_message(message)
        if month_number is None:
            latest = self._latest_payment(detail.payments)
            if latest is None or not latest.tenant_name:
                return ChatResponse(
                    type="answer",
                    message=f"I do not see a tenant recorded for Room {room_id}.",
                    data=detail.model_dump(),
                )
            return ChatResponse(
                type="answer",
                message=f"Room {room_id}: {latest.tenant_name}.",
                data=latest.model_dump(),
            )

        year = self._year_from_message(message) or self.today.year
        matching = [
            payment for payment in detail.payments
            if self._payment_overlaps_month(payment, year, month_number)
        ]
        if not matching:
            month_name = self._month_name_from_message(message) or f"month {month_number}"
            return ChatResponse(
                type="answer",
                message=f"I do not see a tenant recorded for Room {room_id} in {month_name} {year}.",
                data=detail.model_dump(),
            )
        names = []
        for payment in matching:
            if payment.tenant_name and payment.tenant_name not in names:
                names.append(payment.tenant_name)
        month_name = self._month_name_from_message(message) or f"month {month_number}"
        return ChatResponse(
            type="answer",
            message=f"Room {room_id} in {month_name} {year}: {', '.join(names)}.",
            data=[payment.model_dump() for payment in matching],
        )

    def _payment_overlaps_month(self, payment: Payment, year: int, month_number: int) -> bool:
        if not payment.rent_start_date or not payment.rent_end_date:
            return False
        try:
            start = date.fromisoformat(payment.rent_start_date)
            end = date.fromisoformat(payment.rent_end_date)
        except ValueError:
            return False
        month_start = date(year, month_number, 1)
        if month_number == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month_number + 1, 1) - timedelta(days=1)
        return start <= month_end and end >= month_start

    def _year_from_message(self, message: str) -> int | None:
        match = re.search(r"\b(20\d{2})\b", message)
        return int(match.group(1)) if match else None

    def _latest_payment_for_room(self, room_id: int) -> Payment | None:
        return self._latest_payment(self.excel_service.get_room_detail(room_id).payments)

    def _latest_payment(self, payments: list[Payment]) -> Payment | None:
        active = [payment for payment in payments if payment.record_status in {None, "Active"}]
        if not active:
            return None
        return sorted(
            active,
            key=self._payment_sort_key,
        )[-1]

    def _payment_sort_key(self, payment: Payment) -> tuple[str, str, int]:
        return (
            payment.rent_start_date or "",
            payment.rent_end_date or "",
            payment.row_number,
        )

    def _month_name_from_payment(self, payment: Payment) -> str | None:
        month_number = self._date_month(payment.rent_start_date) or self._date_month(payment.rent_end_date)
        if month_number is None:
            return None
        names = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        return names[month_number - 1]

    def _normalize_relative_dates(self, intent: ExtractedIntent) -> ExtractedIntent:
        updates: dict[str, Any] = {}
        for field in ["payment_date", "move_out_date", "rent_start_date", "rent_end_date"]:
            value = getattr(intent, field)
            if isinstance(value, str):
                normalized = self._relative_date(value)
                if normalized != value:
                    updates[field] = normalized
        return intent.model_copy(update=updates) if updates else intent

    def _relative_date(self, value: str) -> str:
        lowered = value.strip().lower()
        if lowered == "today":
            return self.today.isoformat()
        if lowered == "yesterday":
            return (self.today - timedelta(days=1)).isoformat()
        return value

    def _drop_none(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in payload.items() if value is not None}

    def _rupiah(self, value: float | int) -> str:
        return f"Rp{float(value):,.0f}"

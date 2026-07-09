from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    status: str
    excel_file: str


class Room(ApiModel):
    room_id: int
    floor: Optional[int] = None
    room_number: Optional[int] = None
    ac: Optional[str] = None
    current_occupants: int = 0
    current_status: Optional[str] = None
    usual_price: float = 0
    rent_required: Optional[str] = None
    note: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class Payment(ApiModel):
    row_number: int
    room_id: Optional[int] = None
    rent_start_date: Optional[str] = None
    rent_end_date: Optional[str] = None
    amount_due: float = 0
    amount_paid: float = 0
    payment_date: Optional[str] = None
    original_payment_status: Optional[str] = None
    calculated_payment_status: str
    original_room_status: Optional[str] = None
    room_status: Optional[str] = None
    payment_method: Optional[str] = None
    tenant_name: Optional[str] = None
    tenant_ph: Optional[str] = None
    ac: Optional[str] = None
    rent_required: Optional[str] = None
    record_status: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class Summary(ApiModel):
    total_rooms: int
    occupied_rooms: int
    empty_rooms: int
    rooms_with_rent_required_n: int
    total_amount_due: float
    total_amount_paid: float
    total_unpaid_amount: float
    total_cash_collected: float
    total_transfer_collected: float
    late_payment_rows: int
    unpaid_payment_rows: int
    warnings: List[str] = Field(default_factory=list)


class RoomDetail(ApiModel):
    room: Room
    payments: List[Payment]


class AuditLogEntry(ApiModel):
    timestamp: Optional[str] = None
    action_type: Optional[str] = None
    room_id: Optional[int] = None
    sheet_name: Optional[str] = None
    row_index: Optional[int] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    user_message: Optional[str] = None
    status: Optional[str] = None


class ChangePreview(ApiModel):
    sheet_name: str
    row_index: Optional[int] = None
    column: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class OperationResponse(ApiModel):
    preview: bool
    success: bool
    message: str
    backup_path: Optional[str] = None
    rows_to_create: List[Dict[str, Any]] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    changes: List[ChangePreview] = Field(default_factory=list)


class PreviewRequest(ApiModel):
    preview: bool = True
    excluded_room_ids: List[int] = Field(default_factory=list)
    included_room_ids: List[int] = Field(default_factory=list)


class UndoLastChangeRequest(ApiModel):
    preview: bool = True
    backup_file: Optional[str] = None


class UpdateCurrentPaymentRequest(ApiModel):
    room_id: int
    amount_paid: float
    payment_date: str
    payment_method: str
    rent_start_date: Optional[str] = None
    rent_end_date: Optional[str] = None
    preview: bool = True
    user_message: Optional[str] = None


class MoveOutTenantRequest(ApiModel):
    room_id: int
    move_out_date: str
    preview: bool = True
    user_message: Optional[str] = None


class MoveInTenantRequest(ApiModel):
    room_id: int
    tenant_name: str
    tenant_ph: Optional[str] = None
    rent_start_date: str
    rent_end_date: str
    amount_due: float
    current_occupants: int
    ac: str
    amount_paid: float = 0
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    preview: bool = True
    user_message: Optional[str] = None


class UpdateRoomRentRequest(ApiModel):
    room_id: int
    new_amount_due: float
    effective_start_date: Optional[str] = None
    ac: Optional[str] = None
    current_occupants: Optional[int] = None
    preview: bool = True
    user_message: Optional[str] = None


class ErrorResponse(ApiModel):
    detail: str
    available_sheets: Optional[List[str]] = None
    missing_columns: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    extra: Optional[Dict[str, Any]] = None


IntentName = Literal[
    "question_empty_rooms",
    "question_late_payments",
    "question_unpaid_payments",
    "question_room_status",
    "question_payment_status",
    "question_summary",
    "question_unknown",
    "payment_update",
    "move_out",
    "move_in",
    "rent_change",
    "ac_change",
    "auto_rollover",
    "unknown",
]


class ExtractedIntent(ApiModel):
    intent: IntentName
    confidence: float = 0
    room_id: Optional[int] = None
    tenant_name: Optional[str] = None
    tenant_ph: Optional[str] = None
    rent_start_date: Optional[str] = None
    rent_end_date: Optional[str] = None
    amount_due: Optional[float] = None
    amount_paid: Optional[float] = None
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    move_out_date: Optional[str] = None
    current_occupants: Optional[int] = None
    ac: Optional[str] = None
    new_amount_due: Optional[float] = None
    user_message_summary: Optional[str] = None
    missing_fields: List[str] = Field(default_factory=list)
    needs_follow_up: bool = False
    follow_up_questions: List[str] = Field(default_factory=list)


class ChatRequest(ApiModel):
    message: str


class ChatResponse(ApiModel):
    type: Literal["answer", "confirmation_required", "follow_up", "error"]
    message: str
    data: Optional[Any] = None
    action_id: Optional[str] = None
    preview: Optional[OperationResponse] = None
    missing_fields: List[str] = Field(default_factory=list)
    extracted_intent: Optional[ExtractedIntent] = None


class ChatConfirmRequest(ApiModel):
    action_id: str
    confirm: bool


class PendingAction(ApiModel):
    action_id: str
    created_at: str
    intent: str
    backend_action: str
    extracted_fields: Dict[str, Any]
    request_payload: Dict[str, Any]
    preview_response: OperationResponse
    user_message: str
    status: Literal["pending", "confirmed", "cancelled"] = "pending"


class ChatConfirmResponse(ApiModel):
    success: bool
    message: str
    action_id: str
    result: Optional[OperationResponse] = None

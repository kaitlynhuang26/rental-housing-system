from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from .chat_service import ChatService
from .excel_service import ExcelDataError, RentalExcelService
from .locations import ALL_LOCATION_ID, RentalLocation, get_location, is_all_locations, list_locations
from .models import (
    AuditLogEntry,
    ChatConfirmRequest,
    ChatConfirmResponse,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
    LocationInfo,
    MoveInTenantRequest,
    MoveOutTenantRequest,
    OperationResponse,
    Payment,
    PendingAction,
    PreviewRequest,
    Room,
    RoomDetail,
    Summary,
    UndoLastChangeRequest,
    UpdateCurrentPaymentRequest,
    UpdateRoomRentRequest,
)
from .update_service import RentalUpdateService

app = FastAPI(
    title="Rental Housing Management API",
    version="0.3.0",
    description="Rental room backend with safe Excel updates and Groq-powered chat previews.",
)

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

configured_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins or DEFAULT_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Rental Housing Management API is running.",
        "docs": "/docs",
        "health": "/health",
        "summary": "/summary",
    }


def get_service(location_id: Optional[str] = None) -> RentalExcelService:
    location = get_location(location_id)
    return RentalExcelService(excel_path=location.excel_path)


def get_update_service(location_id: Optional[str] = None) -> RentalUpdateService:
    location = get_location(location_id)
    return RentalUpdateService(excel_path=location.excel_path)


def get_chat_service(location_id: Optional[str] = None) -> ChatService:
    location = get_location(location_id)
    return ChatService(
        excel_service=RentalExcelService(excel_path=location.excel_path),
        update_service=RentalUpdateService(excel_path=location.excel_path),
        location_id=location.location_id,
    )


def raise_api_error(error: ExcelDataError, status_code: int = 400) -> None:
    raise HTTPException(
        status_code=status_code,
        detail=ErrorResponse(
            detail=error.detail,
            available_sheets=error.available_sheets,
            missing_columns=error.missing_columns,
            warnings=error.warnings or None,
        ).model_dump(),
    )


def _with_location(item, location: RentalLocation):
    return item.model_copy(
        update={"location_id": location.location_id, "location_name": location.name}
    )


def _service_for_location(location: RentalLocation) -> RentalExcelService:
    return RentalExcelService(excel_path=location.excel_path)


def _all_rooms() -> list[Room]:
    rows: list[Room] = []
    for location in list_locations():
        rows.extend(_with_location(room, location) for room in _service_for_location(location).get_rooms())
    return rows


def _all_payments(method_name: str = "get_payments") -> list[Payment]:
    rows: list[Payment] = []
    for location in list_locations():
        service = _service_for_location(location)
        rows.extend(_with_location(payment, location) for payment in getattr(service, method_name)())
    return rows


def _all_summary() -> Summary:
    summaries: list[Summary] = []
    warnings: list[str] = []
    for location in list_locations():
        summary = _service_for_location(location).get_summary()
        summaries.append(summary)
        warnings.extend(f"{location.name}: {warning}" for warning in summary.warnings)
    return Summary(
        location_id=ALL_LOCATION_ID,
        location_name="All Locations",
        total_rooms=sum(item.total_rooms for item in summaries),
        occupied_rooms=sum(item.occupied_rooms for item in summaries),
        empty_rooms=sum(item.empty_rooms for item in summaries),
        rooms_with_rent_required_n=sum(item.rooms_with_rent_required_n for item in summaries),
        total_amount_due=sum(item.total_amount_due for item in summaries),
        total_amount_paid=sum(item.total_amount_paid for item in summaries),
        total_unpaid_amount=sum(item.total_unpaid_amount for item in summaries),
        total_cash_collected=sum(item.total_cash_collected for item in summaries),
        total_transfer_collected=sum(item.total_transfer_collected for item in summaries),
        late_payment_rows=sum(item.late_payment_rows for item in summaries),
        unpaid_payment_rows=sum(item.unpaid_payment_rows for item in summaries),
        warnings=warnings,
    )


def _require_single_location(location_id: Optional[str]) -> Optional[str]:
    if is_all_locations(location_id):
        raise HTTPException(
            status_code=400,
            detail="Please choose one rental location before saving or previewing updates.",
        )
    return location_id


@app.get("/health", response_model=HealthResponse)
def health(location_id: Optional[str] = None) -> HealthResponse:
    try:
        location = get_location(location_id)
        return HealthResponse(
            **get_service(location.location_id).health(),
            location_id=location.location_id,
            location_name=location.name,
        )
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise_api_error(error, status_code=500)


@app.get("/locations", response_model=list[LocationInfo])
def locations() -> list[LocationInfo]:
    return [LocationInfo(**location.model_dump()) for location in list_locations()]


@app.get("/rooms", response_model=list[Room])
def rooms(location_id: Optional[str] = None) -> list[Room]:
    try:
        if is_all_locations(location_id):
            return _all_rooms()
        location = get_location(location_id)
        return [_with_location(room, location) for room in get_service(location.location_id).get_rooms()]
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise_api_error(error)


@app.get("/payments", response_model=list[Payment])
def payments(location_id: Optional[str] = None) -> list[Payment]:
    try:
        if is_all_locations(location_id):
            return _all_payments()
        location = get_location(location_id)
        return [_with_location(payment, location) for payment in get_service(location.location_id).get_payments()]
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise_api_error(error)


@app.get("/summary", response_model=Summary)
def summary(location_id: Optional[str] = None) -> Summary:
    try:
        if is_all_locations(location_id):
            return _all_summary()
        location = get_location(location_id)
        return get_service(location.location_id).get_summary().model_copy(
            update={"location_id": location.location_id, "location_name": location.name}
        )
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise_api_error(error)


@app.get("/rooms/empty", response_model=list[Room])
def empty_rooms(location_id: Optional[str] = None) -> list[Room]:
    try:
        if is_all_locations(location_id):
            return [room for room in _all_rooms() if room.current_status == "Empty"]
        location = get_location(location_id)
        return [_with_location(room, location) for room in get_service(location.location_id).get_empty_rooms()]
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise_api_error(error)


@app.get("/payments/late", response_model=list[Payment])
def late_payments(location_id: Optional[str] = None) -> list[Payment]:
    try:
        if is_all_locations(location_id):
            return _all_payments("get_late_payments")
        location = get_location(location_id)
        return [_with_location(payment, location) for payment in get_service(location.location_id).get_late_payments()]
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise_api_error(error)


@app.get("/payments/unpaid", response_model=list[Payment])
def unpaid_payments(location_id: Optional[str] = None) -> list[Payment]:
    try:
        if is_all_locations(location_id):
            return _all_payments("get_unpaid_payments")
        location = get_location(location_id)
        return [_with_location(payment, location) for payment in get_service(location.location_id).get_unpaid_payments()]
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise_api_error(error)


@app.get("/room/{room_id}", response_model=RoomDetail)
def room_detail(room_id: int, location_id: Optional[str] = None) -> RoomDetail:
    try:
        location = get_location(location_id)
        detail = get_service(location.location_id).get_room_detail(room_id)
        return detail.model_copy(
            update={
                "room": _with_location(detail.room, location),
                "payments": [_with_location(payment, location) for payment in detail.payments],
            }
        )
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        status_code = 404 if "was not found" in error.detail else 400
        raise_api_error(error, status_code=status_code)


@app.post("/rental-periods/auto-rollover", response_model=OperationResponse)
def auto_rollover(request: PreviewRequest, location_id: Optional[str] = None) -> OperationResponse:
    try:
        location_id = _require_single_location(location_id)
        return get_update_service(location_id).auto_rollover_rental_periods(
            preview=request.preview,
            excluded_room_ids=request.excluded_room_ids,
            included_room_ids=request.included_room_ids,
        )
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/payments/update-current", response_model=OperationResponse)
def update_current_payment(request: UpdateCurrentPaymentRequest, location_id: Optional[str] = None) -> OperationResponse:
    try:
        location_id = _require_single_location(location_id)
        return get_update_service(location_id).update_current_payment(**request.model_dump())
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/tenants/move-out", response_model=OperationResponse)
def move_out_tenant(request: MoveOutTenantRequest, location_id: Optional[str] = None) -> OperationResponse:
    try:
        location_id = _require_single_location(location_id)
        return get_update_service(location_id).move_out_tenant(**request.model_dump())
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/tenants/move-in", response_model=OperationResponse)
def move_in_tenant(request: MoveInTenantRequest, location_id: Optional[str] = None) -> OperationResponse:
    try:
        location_id = _require_single_location(location_id)
        return get_update_service(location_id).move_in_tenant(**request.model_dump())
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/rooms/update-rent", response_model=OperationResponse)
def update_room_rent(request: UpdateRoomRentRequest, location_id: Optional[str] = None) -> OperationResponse:
    try:
        location_id = _require_single_location(location_id)
        return get_update_service(location_id).update_room_rent(**request.model_dump())
    except ExcelDataError as error:
        raise_api_error(error)


@app.get("/audit-log", response_model=list[AuditLogEntry])
def audit_log(limit: int = 50, location_id: Optional[str] = None) -> list[AuditLogEntry]:
    try:
        if is_all_locations(location_id):
            entries: list[AuditLogEntry] = []
            for location in list_locations():
                entries.extend(
                    AuditLogEntry(**row, location_id=location.location_id, location_name=location.name)
                    for row in get_update_service(location.location_id).get_audit_log(limit=limit)
                )
            return sorted(entries, key=lambda item: item.timestamp or "", reverse=True)[:limit]
        location = get_location(location_id)
        return [
            AuditLogEntry(**row, location_id=location.location_id, location_name=location.name)
            for row in get_update_service(location.location_id).get_audit_log(limit=limit)
        ]
    except (ExcelDataError, ValueError) as error:
        if isinstance(error, ValueError):
            raise HTTPException(status_code=400, detail=str(error))
        raise_api_error(error)


@app.post("/undo/last-change", response_model=OperationResponse)
def undo_last_change(request: UndoLastChangeRequest, location_id: Optional[str] = None) -> OperationResponse:
    try:
        location_id = _require_single_location(location_id)
        return get_update_service(location_id).undo_last_change(
            preview=request.preview,
            backup_file=request.backup_file,
        )
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        if is_all_locations(request.location_id):
            return ChatResponse(
                type="follow_up",
                message="Please choose one rental location before using chatbot updates or questions.",
            )
        return get_chat_service(request.location_id).chat(request.message)
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/chat/confirm", response_model=ChatConfirmResponse)
def confirm_chat_action(request: ChatConfirmRequest) -> ChatConfirmResponse:
    if is_all_locations(request.location_id):
        return ChatConfirmResponse(
            success=False,
            message="Please choose one rental location before confirming a chatbot action.",
            action_id=request.action_id,
        )
    return get_chat_service(request.location_id).confirm(request.action_id, request.confirm)


@app.get("/chat/pending-actions", response_model=list[PendingAction])
def pending_chat_actions() -> list[PendingAction]:
    return get_chat_service().pending_actions()

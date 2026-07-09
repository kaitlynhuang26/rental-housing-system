from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .chat_service import ChatService
from .excel_service import ExcelDataError, RentalExcelService
from .models import (
    AuditLogEntry,
    ChatConfirmRequest,
    ChatConfirmResponse,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    HealthResponse,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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


def get_service() -> RentalExcelService:
    return RentalExcelService()


def get_update_service() -> RentalUpdateService:
    return RentalUpdateService()


def get_chat_service() -> ChatService:
    return ChatService()


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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        return HealthResponse(**get_service().health())
    except ExcelDataError as error:
        raise_api_error(error, status_code=500)


@app.get("/rooms", response_model=list[Room])
def rooms() -> list[Room]:
    try:
        return get_service().get_rooms()
    except ExcelDataError as error:
        raise_api_error(error)


@app.get("/payments", response_model=list[Payment])
def payments() -> list[Payment]:
    try:
        return get_service().get_payments()
    except ExcelDataError as error:
        raise_api_error(error)


@app.get("/summary", response_model=Summary)
def summary() -> Summary:
    try:
        return get_service().get_summary()
    except ExcelDataError as error:
        raise_api_error(error)


@app.get("/rooms/empty", response_model=list[Room])
def empty_rooms() -> list[Room]:
    try:
        return get_service().get_empty_rooms()
    except ExcelDataError as error:
        raise_api_error(error)


@app.get("/payments/late", response_model=list[Payment])
def late_payments() -> list[Payment]:
    try:
        return get_service().get_late_payments()
    except ExcelDataError as error:
        raise_api_error(error)


@app.get("/payments/unpaid", response_model=list[Payment])
def unpaid_payments() -> list[Payment]:
    try:
        return get_service().get_unpaid_payments()
    except ExcelDataError as error:
        raise_api_error(error)


@app.get("/room/{room_id}", response_model=RoomDetail)
def room_detail(room_id: int) -> RoomDetail:
    try:
        return get_service().get_room_detail(room_id)
    except ExcelDataError as error:
        status_code = 404 if "was not found" in error.detail else 400
        raise_api_error(error, status_code=status_code)


@app.post("/rental-periods/auto-rollover", response_model=OperationResponse)
def auto_rollover(request: PreviewRequest) -> OperationResponse:
    try:
        return get_update_service().auto_rollover_rental_periods(
            preview=request.preview,
            excluded_room_ids=request.excluded_room_ids,
            included_room_ids=request.included_room_ids,
        )
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/payments/update-current", response_model=OperationResponse)
def update_current_payment(request: UpdateCurrentPaymentRequest) -> OperationResponse:
    try:
        return get_update_service().update_current_payment(**request.model_dump())
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/tenants/move-out", response_model=OperationResponse)
def move_out_tenant(request: MoveOutTenantRequest) -> OperationResponse:
    try:
        return get_update_service().move_out_tenant(**request.model_dump())
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/tenants/move-in", response_model=OperationResponse)
def move_in_tenant(request: MoveInTenantRequest) -> OperationResponse:
    try:
        return get_update_service().move_in_tenant(**request.model_dump())
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/rooms/update-rent", response_model=OperationResponse)
def update_room_rent(request: UpdateRoomRentRequest) -> OperationResponse:
    try:
        return get_update_service().update_room_rent(**request.model_dump())
    except ExcelDataError as error:
        raise_api_error(error)


@app.get("/audit-log", response_model=list[AuditLogEntry])
def audit_log(limit: int = 50) -> list[AuditLogEntry]:
    try:
        return [
            AuditLogEntry(**row)
            for row in get_update_service().get_audit_log(limit=limit)
        ]
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/undo/last-change", response_model=OperationResponse)
def undo_last_change(request: UndoLastChangeRequest) -> OperationResponse:
    try:
        return get_update_service().undo_last_change(
            preview=request.preview,
            backup_file=request.backup_file,
        )
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        return get_chat_service().chat(request.message)
    except ExcelDataError as error:
        raise_api_error(error)


@app.post("/chat/confirm", response_model=ChatConfirmResponse)
def confirm_chat_action(request: ChatConfirmRequest) -> ChatConfirmResponse:
    return get_chat_service().confirm(request.action_id, request.confirm)


@app.get("/chat/pending-actions", response_model=list[PendingAction])
def pending_chat_actions() -> list[PendingAction]:
    return get_chat_service().pending_actions()

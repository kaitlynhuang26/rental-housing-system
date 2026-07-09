from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import OperationResponse, PendingAction


DEFAULT_PENDING_ACTIONS_PATH = (
    Path(__file__).resolve().parents[1] / "pending_actions.json"
)


class PendingActionError(Exception):
    pass


class PendingActionStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or DEFAULT_PENDING_ACTIONS_PATH)

    def create(
        self,
        *,
        intent: str,
        backend_action: str,
        extracted_fields: dict[str, Any],
        request_payload: dict[str, Any],
        preview_response: OperationResponse,
        user_message: str,
    ) -> PendingAction:
        action = PendingAction(
            action_id=uuid.uuid4().hex,
            created_at=datetime.now().isoformat(timespec="seconds"),
            intent=intent,
            backend_action=backend_action,
            extracted_fields=extracted_fields,
            request_payload=request_payload,
            preview_response=preview_response,
            user_message=user_message,
            status="pending",
        )
        actions = self.list_all()
        actions[action.action_id] = action
        self._write(actions)
        return action

    def get(self, action_id: str) -> PendingAction:
        action = self.list_all().get(action_id)
        if action is None:
            raise PendingActionError(f"Pending action {action_id} was not found.")
        return action

    def list_pending(self) -> list[PendingAction]:
        return [
            action
            for action in self.list_all().values()
            if action.status == "pending"
        ]

    def list_all(self) -> dict[str, PendingAction]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PendingActionError(f"Could not read pending actions: {error}") from error

        actions: dict[str, PendingAction] = {}
        for action_id, value in raw.items():
            actions[action_id] = PendingAction(**value)
        return actions

    def mark_confirmed(self, action_id: str) -> PendingAction:
        return self._set_status(action_id, "confirmed")

    def mark_cancelled(self, action_id: str) -> PendingAction:
        return self._set_status(action_id, "cancelled")

    def _set_status(self, action_id: str, status: str) -> PendingAction:
        actions = self.list_all()
        action = actions.get(action_id)
        if action is None:
            raise PendingActionError(f"Pending action {action_id} was not found.")
        if action.status != "pending":
            raise PendingActionError(
                f"Pending action {action_id} is already {action.status}."
            )
        updated = action.model_copy(update={"status": status})
        actions[action_id] = updated
        self._write(actions)
        return updated

    def _write(self, actions: dict[str, PendingAction]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            action_id: action.model_dump(mode="json")
            for action_id, action in actions.items()
        }
        self.path.write_text(
            json.dumps(serializable, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

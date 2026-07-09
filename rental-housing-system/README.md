# Rental Housing Management System - Steps 1, 2, and 3

This is a FastAPI backend for the rental housing Excel workbook.

Step 1 reads, cleans, calculates, and summarizes workbook data.

Step 2 adds safe write/update operations. Every write endpoint supports preview mode, creates a backup before saving, and writes to `audit_log`.

Step 3 adds a Groq-powered chat layer. Groq only extracts intent and fields from natural language. The backend still reads, validates, previews, confirms, saves, creates backups, and writes audit logs.

## Architecture

- `backend/main.py` defines the FastAPI app and API endpoints.
- `backend/excel_service.py` loads the Excel workbook, validates required sheets and columns, cleans rows, calculates payment status, and builds summaries.
- `backend/update_service.py` handles safe Excel writes, backups, audit logs, rental period rollover, payment updates, move-in, move-out, rent changes, and AC changes.
- `backend/ai_agent.py` sends the user message to Groq and requires strict JSON intent extraction.
- `backend/chat_service.py` maps extracted intents to read-only answers or safe preview updates.
- `backend/pending_actions.py` stores previewed actions in `pending_actions.json` until the user confirms or cancels.
- `backend/models.py` defines Pydantic response models so API output stays predictable.
- `data/Kos Gedung Panjang (1).xlsx` is a working copy of the uploaded workbook. The original file in Downloads is not modified.

The Excel path is configurable with `EXCEL_FILE_PATH`. If it is not set, the backend uses:

```bash
data/Kos Gedung Panjang (1).xlsx
```

## File Structure

```text
rental-housing-system/
  backend/
    __init__.py
    main.py
    ai_agent.py
    chat_service.py
    excel_service.py
    pending_actions.py
    update_service.py
    models.py
    requirements.txt
  backups/
  data/
    Kos Gedung Panjang (1).xlsx
  .env.example
  pending_actions.json
  README.md
```

## Business Rules Implemented

- `Ocuppied`, `occupied`, and `Occupied` are normalized to `Occupied`.
- `empty` and `Empty` are normalized to `Empty`.
- If `room_status` is `Empty`, `calculated_payment_status` is `N/A`.
- If `rent_required` is `N` in `room_record`, payment `amount_due` is treated as `0` in the API.
- If `payment_date` exists and is more than 7 days after `rent_start_date`, `calculated_payment_status` is `Late`.
- If `payment_date` exists and is within 7 days after `rent_start_date`, `calculated_payment_status` is `Paid`.
- If `payment_date` is blank and today is more than 7 days after `rent_start_date`, `calculated_payment_status` is `Unpaid`.
- If `payment_date` is blank and today is before or within 7 days after `rent_start_date`, `calculated_payment_status` is `Pending`.
- The original workbook `payment_status` is preserved as `original_payment_status`.
- Step 2 treats the `payments` sheet as the source of truth for current room status. `room_record` is mostly stable room metadata.
- Step 2 adds `record_status`, `source`, and `notes` to `payments` if missing.
- Step 2 adds `audit_log` if missing.

## Setup

From this folder:

```bash
cd /Users/kaitlynhuang/Documents/AI\ Rental\ Agent/rental-housing-system
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Optional custom Excel path:

```bash
export EXCEL_FILE_PATH="/absolute/path/to/Kos Gedung Panjang (1).xlsx"
```

Groq setup:

```bash
cp .env.example .env
```

Then open `.env` and replace the placeholder:

```text
GROQ_API_KEY=your_real_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

Never paste the API key directly into Python code.

## Run

```bash
python -m uvicorn backend.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

## API Endpoints

### GET `/health`

Example:

```json
{
  "status": "ok",
  "excel_file": "/Users/kaitlynhuang/Documents/AI Rental Agent/rental-housing-system/data/Kos Gedung Panjang (1).xlsx"
}
```

### GET `/rooms`

Returns all rooms from `room_record`.

Example item:

```json
{
  "room_id": 101,
  "floor": 1,
  "room_number": 1,
  "ac": "N",
  "current_occupants": 2,
  "current_status": "Occupied",
  "usual_price": 550000.0,
  "rent_required": "Y",
  "note": null,
  "warnings": []
}
```

### GET `/payments`

Returns all payment rows with the calculated status.

Example item:

```json
{
  "row_number": 2,
  "room_id": 101,
  "rent_start_date": "2026-01-01",
  "rent_end_date": "2026-01-31",
  "amount_due": 550000.0,
  "amount_paid": 550000.0,
  "payment_date": "2026-01-02",
  "original_payment_status": "Paid",
  "calculated_payment_status": "Paid",
  "original_room_status": "Ocuppied",
  "room_status": "Occupied",
  "payment_method": "transfer",
  "tenant_name": "Arumi/Arin",
  "tenant_ph": null,
  "ac": "N",
  "rent_required": "Y",
  "warnings": []
}
```

### GET `/summary`

With the current workbook and a server date after the recorded rent periods, the summary will look like:

```json
{
  "total_rooms": 14,
  "occupied_rooms": 14,
  "empty_rooms": 0,
  "rooms_with_rent_required_n": 2,
  "total_amount_due": 29180000.0,
  "total_amount_paid": 29180000.0,
  "total_unpaid_amount": 0.0,
  "total_cash_collected": 0.0,
  "total_transfer_collected": 28730000.0,
  "late_payment_rows": 12,
  "unpaid_payment_rows": 0,
  "warnings": [
    "payments row 44 has no room_id and was skipped.",
    "payments row 53 has no room_id and was skipped.",
    "payments row 58 has no room_id and was skipped.",
    "payments row 71 has no room_id and was skipped.",
    "payments row 89 has no room_id and was skipped."
  ]
}
```

### GET `/rooms/empty`

Returns rooms whose latest active payment row says `room_status = Empty`.

### GET `/payments/late`

Returns rows where `calculated_payment_status` is `Late`.

### GET `/payments/unpaid`

Returns rows where `calculated_payment_status` is `Unpaid`.

### GET `/room/{room_id}`

Example:

```text
GET /room/101
```

Returns room details plus payment history for room `101`.

Unknown rooms return a 404-style response:

```json
{
  "detail": {
    "detail": "Room 999 was not found.",
    "available_sheets": null,
    "missing_columns": null,
    "warnings": null,
    "extra": null
  }
}
```

## Error Handling

- Missing Excel file: clear `Excel file not found` error.
- Missing `room_record` or `payments` sheet: clear error plus available sheets.
- Missing required columns: clear error listing missing columns.
- Invalid dates: row is kept when possible and a warning is added to that row.
- Blank payment rows without `room_id`: skipped and listed in summary warnings.
- Write operations create a backup first. If backup fails, Excel is not updated.
- Old rows are never deleted. Wrong generated rows should be marked `Cancelled` or `Corrected`.

## Step 2 Write Endpoints

Always test with `"preview": true` first.

### POST `/rental-periods/auto-rollover`

Creates next rental period rows when the latest active occupied period has ended and no next period exists yet.

Request:

```json
{
  "preview": true
}
```

Response preview shape:

```json
{
  "preview": true,
  "success": true,
  "message": "Preview only. 5 rental period row(s) would be created.",
  "backup_path": null,
  "rows_to_create": [
    {
      "room_id": 101,
      "rent_start_date": "2026-06-01",
      "rent_end_date": "2026-06-30",
      "amount_due": 550000.0,
      "amount_paid": 0,
      "payment_status": "Unpaid",
      "room_status": "Occupied",
      "source": "Auto rollover",
      "notes": "Assumed tenant continued"
    }
  ],
  "skipped": [],
  "warnings": [],
  "changes": []
}
```

Use `"preview": false` only after checking the proposed rows.

### POST `/payments/update-current`

Updates the latest active payment row for a room unless a rent period is specified.

```json
{
  "room_id": 101,
  "amount_paid": 550000,
  "payment_date": "2026-06-02",
  "payment_method": "Transfer",
  "preview": true,
  "user_message": "Room 101 paid by transfer on June 2"
}
```

### POST `/tenants/move-out`

Marks the latest active row as empty and cancels active future rows instead of deleting them.

```json
{
  "room_id": 101,
  "move_out_date": "2026-06-15",
  "preview": true,
  "user_message": "Room 101 moved out on June 15"
}
```

### POST `/tenants/move-in`

Adds a brand new payment row for a new tenant and updates stable room metadata.

```json
{
  "room_id": 101,
  "tenant_name": "Budi",
  "tenant_ph": "08123456789",
  "rent_start_date": "2026-07-01",
  "rent_end_date": "2026-07-31",
  "amount_due": 550000,
  "current_occupants": 1,
  "ac": "N",
  "amount_paid": 550000,
  "payment_date": "2026-07-01",
  "payment_method": "Cash",
  "preview": true,
  "user_message": "Budi moved into Room 101 and paid cash"
}
```

### POST `/rooms/update-rent`

Updates `room_record.usual_price` and matching current/future active payment rows when they exist.
This endpoint also handles AC or occupant changes that explain the rent change, so there is no separate AC update endpoint.

```json
{
  "room_id": 101,
  "new_amount_due": 700000,
  "effective_start_date": "2026-07-01",
  "ac": "Y",
  "current_occupants": 1,
  "preview": true,
  "user_message": "add ac"
}
```

The `user_message` is written into Excel notes as a formal sentence, for example:
`Rent changed to 700000.0 effective 2026-07-01 due to add ac.`

### GET `/audit-log`

Returns recent audit entries.

```text
GET /audit-log?limit=50
```

## Step 3 Chat Endpoints

### POST `/chat`

Use this for both questions and natural-language update requests.

Question example:

```json
{
  "message": "Who paid late?"
}
```

Example answer:

```json
{
  "type": "answer",
  "message": "There are 12 late payment row(s), covering room(s): 101, 102, 103.",
  "data": []
}
```

Update example:

```json
{
  "message": "Room 101 paid today by transfer"
}
```

Example preview response:

```json
{
  "type": "confirmation_required",
  "action_id": "abc123",
  "message": "I found the current amount due is Rp550,000. I will mark Room 101 as paid by Transfer on 2026-07-06 for Rp550,000. Should I save this?",
  "preview": {
    "preview": true,
    "success": true,
    "message": "Preview only. Current payment would be updated.",
    "changes": []
  }
}
```

Follow-up example:

```json
{
  "type": "follow_up",
  "message": "What date did they move out?",
  "missing_fields": ["move_out_date"]
}
```

### POST `/chat/confirm`

Save or cancel a pending previewed action.

Save:

```json
{
  "action_id": "abc123",
  "confirm": true
}
```

Cancel:

```json
{
  "action_id": "abc123",
  "confirm": false
}
```

When `confirm` is `true`, the backend runs the same action with `preview=false`, creates a backup, saves Excel, and writes an audit log. When `confirm` is `false`, Excel is not updated.

### GET `/chat/pending-actions`

Returns pending actions waiting for confirmation.

## Groq System Prompt

The full prompt lives in `backend/ai_agent.py` as `SYSTEM_PROMPT`. Its core rules are:

- Return only valid JSON.
- Extract intent and fields only.
- Do not update Excel.
- Do not claim anything was saved.
- Do not calculate payment status.
- Resolve vague dates like today/yesterday using the backend current date.
- Mark missing fields and ask follow-up questions.

## Preview Before Saving

1. Open `http://127.0.0.1:8000/docs`.
2. Run a Step 2 endpoint with `"preview": true`.
3. Read `rows_to_create`, `changes`, `skipped`, and `warnings`.
4. If the preview is correct, run the same endpoint again with `"preview": false`.
5. Check `backup_path` in the response.
6. Check `GET /audit-log`.

## Suggested Test Cases With Current Data

1. `GET /health` returns `status: ok`.
2. `GET /rooms` returns `14` rooms.
3. `GET /rooms/empty` returns `[]` because all current rooms have at least one occupant in `room_record`.
4. `GET /payments` returns normalized `room_status: Occupied` for rows that originally say `Ocuppied`.
5. `GET /payments/late` includes room `101` for the `2026-03-01` rent period because payment was on `2026-03-31`.
6. `GET /summary` returns `rooms_with_rent_required_n: 2`.
7. `GET /summary` returns `total_transfer_collected: 28730000.0` and `total_cash_collected: 0.0` for the current workbook. One paid `Empty` row has no payment method, so it is included in total paid but not transfer collected.
8. `GET /room/101` returns room `101` and its payment history.
9. `GET /room/999` returns a 404-style error.
10. Temporarily point `EXCEL_FILE_PATH` to a missing file and confirm `/health` returns a clear missing-file error.
11. `POST /rental-periods/auto-rollover` with preview true returns proposed rows and does not save.
12. `POST /payments/update-current` with preview true returns proposed cell changes.
13. `POST /tenants/move-in` with missing `tenant_ph` still previews but returns a warning.
14. Run a write endpoint on a copy of the workbook with preview false and confirm a backup is created.
15. Confirm `GET /audit-log` returns saved write actions after preview false.
16. `POST /chat` with `{"message": "Who paid late?"}` returns an answer.
17. `POST /chat` with `{"message": "Room 101 paid today by transfer"}` returns `confirmation_required`, not a saved update.
18. Copy the returned `action_id` into `POST /chat/confirm` with `confirm: false` and confirm Excel does not change.
19. Run another chat update on a copied workbook, confirm with `confirm: true`, and confirm a backup plus audit log are created.

## Stage 4 Frontend

The React frontend is in `frontend/`. It keeps API calls in `src/api.js`,
shared formatting in `src/utils.js`, and one component for each main page.

```text
frontend/
  src/
    components/Common.jsx
    pages/
      Dashboard.jsx
      Rooms.jsx
      Payments.jsx
      RawData.jsx
      Chatbot.jsx
      AutoRollover.jsx
      AuditLog.jsx
    api.js
    App.jsx
    main.jsx
    styles.css
    utils.js
  index.html
  package.json
  vite.config.js
```

### Run Backend And Frontend

Open two terminal windows from the project folder.

Terminal 1:

```bash
source .venv/bin/activate
python -m uvicorn backend.main:app --reload
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

The frontend calls `http://127.0.0.1:8000` by default. To use another backend:

```bash
VITE_API_BASE_URL="http://127.0.0.1:8001" npm run dev
```

### Frontend Manual Checklist

1. Dashboard summary cards and room availability load.
2. Occupied rooms are green and empty rooms are red.
3. Late and unpaid alerts show the correct tenant, period, and amount.
4. Room filters work.
5. Monthly Payments groups records by room and `rent_start_date` month.
6. Raw Data status, room, and tenant filters work.
7. Chat answers a read-only question.
8. Chat shows a preview and confirmation buttons for an update.
9. Cancelling a chat action does not save.
10. Confirming a chat action refreshes all pages.
11. Auto Rollover previews rows and allows individual rooms to be unchecked.
12. Confirming rollover saves only selected rooms.
13. Audit Log shows newly saved actions.

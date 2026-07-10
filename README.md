# Rental Housing Management System

A rental housing management app built around an existing Excel workflow.

The project started from a real monthly rental workbook and grew into a safer management system with:

- a FastAPI backend that reads and validates Excel data
- safe Excel write operations with preview, backup, and audit log
- a Groq-powered AI chatbot for natural-language questions and updates
- a React dashboard for rooms, payments, alerts, audit logs, and chatbot actions

The main design principle is:

```text
LLM = understands language
Backend = validates, calculates, previews, saves, and protects the Excel file
```

Watch the full demo here: [Rental Housing Management System Demo](https://drive.google.com/file/d/1HvQ6VpqLoROjrwJ4TQEks1pJhEriypzx/view?usp=sharing)

Watch the AI demo here: [Rental Assistant AI CHAT Demo]
(https://drive.google.com/file/d/1bgRpdyGd3ZfFBnropEjBBZEv2Vsaxq5z/view?usp=sharing)


## Demo Data

The real workbook is private and ignored by Git.

This repository includes a locked public demo workbook for portfolio viewing:

```text
data/public_demo/Kos_Gedung_Panjang_PUBLIC_DEMO_LOCKED.xlsx
```

The backend default local path is still:

```text
data/Kos Gedung Panjang (1).xlsx
```

To run the app with another workbook, set:

```bash
export EXCEL_FILE_PATH="/absolute/path/to/your workbook.xlsx"
```

## Features

- Read rooms and payments from Excel
- Normalize messy spreadsheet values such as `Ocuppied` to `Occupied`
- Parse Excel dates safely
- Calculate payment status in Python instead of trusting spreadsheet formulas
- Dashboard summaries for total rooms, occupied rooms, empty rooms, paid amount, cash, transfer, late, and unpaid payments
- Monthly payment view grouped by room and rent start month
- Safe update endpoints with `preview=true`
- Backup before every save
- Audit log for every confirmed write
- Auto rollover for tenants assumed to continue month to month
- Move-in, move-out, rent change, AC/rent note handling, and current payment updates
- Undo last change by restoring a selected backup after preview and confirmation
- Groq chatbot that extracts intent and fields, then asks the backend to preview actions
- React frontend with Dashboard, Rooms, Payments, Raw Data, Chatbot, Auto Rollover, and Audit Log pages

## Architecture

```text
rental-housing-system/
  backend/
    main.py              FastAPI app and routes
    excel_service.py     Read, clean, normalize, calculate, and summarize Excel data
    update_service.py    Safe write operations, backups, audit log, rollover, undo
    ai_agent.py          Groq intent extraction prompt and API call
    chat_service.py      Maps AI intents to backend read/preview/confirm actions
    pending_actions.py   Stores previewed chatbot actions before confirmation
    models.py            Pydantic request and response models
    requirements.txt

  frontend/
    src/
      pages/
        Dashboard.jsx
        Rooms.jsx
        Payments.jsx
        RawData.jsx
        Chatbot.jsx
        AutoRollover.jsx
        AuditLog.jsx
      api.js
      utils.js
      App.jsx
      main.jsx
      styles.css

  data/
    public_demo/
      Kos_Gedung_Panjang_PUBLIC_DEMO_LOCKED.xlsx

  .env.example
  README.md
```

## How It Works

1. The backend reads the Excel workbook.
2. It validates required sheets and columns.
3. It normalizes inconsistent values.
4. It calculates payment status from business rules.
5. The frontend displays dashboards, monthly views, raw data, and alerts.
6. For updates, the backend previews changes first.
7. Only after confirmation does it create a backup, write to Excel, and add an audit log row.
8. The chatbot never edits Excel directly. It only converts natural language into structured intent.

## Payment Rules

- If `room_status = Empty`, payment status is `N/A`.
- If `payment_date` exists and is more than 7 days after `rent_start_date`, status is `Late`.
- If `payment_date` exists and is within 7 days after `rent_start_date`, status is `Paid`.
- If `payment_date` is blank and today is within 7 days after `rent_start_date`, status is `Pending`.
- If `payment_date` is blank and today is more than 7 days after `rent_start_date`, status is `Unpaid`.
- If `rent_required = N`, `amount_due` is treated as `0`.
- The original Excel `payment_status` is preserved, but the API also returns `calculated_payment_status`.

## Safety Design

The most important part of this project is avoiding accidental data loss.

- The app does not delete old payment rows.
- Write operations support preview mode.
- Confirmed writes create a workbook backup first.
- Confirmed writes add an `audit_log` entry.
- Auto-created rows can be marked `Cancelled` or `Corrected` instead of deleted.
- Chatbot updates always require confirmation.
- `.env`, real Excel files, backups, pending actions, virtual environments, and `node_modules` are ignored by Git.

## Obstacles, Challenges, And Solutions

### 1. The source of truth was an Excel file, not a database

**Challenge:** The business already ran on Excel, so replacing it immediately with a database would have been risky and hard for the user to trust.

**Solution:** Keep Excel as the source of truth for this stage. The backend reads and writes Excel safely while adding validation, backups, audit logs, and API access around it.

### 2. Rental periods do not always start on the first day of the month

**Challenge:** Some tenants start on dates like `2026-01-12`, so monthly rent cannot simply be grouped by calendar month.

**Solution:** Each payment row represents one rental period. Auto rollover uses the previous row's date pattern to create the next period instead of assuming every period starts on day 1.

### 3. Spreadsheet data had typos and inconsistent values

**Challenge:** Values like `Ocuppied`, `occupied`, `transfer`, `cash`, `Y`, `yes`, and blank cells appear in different forms.

**Solution:** The backend normalizes values internally before calculating summaries or statuses. The raw Excel value is still preserved where useful.

### 4. Spreadsheet formulas could not be fully trusted

**Challenge:** The workbook may contain formulas or old status values that do not reflect the current business rules.

**Solution:** The backend keeps the original status but calculates a separate `calculated_payment_status` using Python rules.

### 5. Updating Excel directly is risky

**Challenge:** A wrong update could damage the workbook or overwrite history.

**Solution:** Every write operation supports preview mode, creates a timestamped backup before saving, writes an audit log, and avoids deleting historical rows.

### 6. Auto rollover needs to be helpful but not dangerous

**Challenge:** Most tenants continue monthly, but some move out. Automatically creating every next row without review could create wrong records.

**Solution:** Auto rollover first returns a preview of proposed rows. The frontend lets the user uncheck rooms that should not continue before confirming.

### 7. Natural language can be ambiguous

**Challenge:** Messages like "Room 101 paid" may be missing amount, date, method, or rental period.

**Solution:** Groq extracts intent and fields, but the backend validates everything. Missing fields trigger follow-up questions. Updates are previewed and require confirmation before saving.

### 8. Chatbot context can become confusing

**Challenge:** A chatbot may forget what the user meant in follow-up answers like "transfer" or "they have not paid."

**Solution:** The frontend stores short-lived chat context for follow-up messages, and the backend prompt tells the AI to treat follow-up answers as part of the previous request.

### 9. Portfolio sharing needed demo data without exposing private files

**Challenge:** The project needs to be visible on GitHub, but real workbook data, backups, API keys, and local pending actions should stay private.

**Solution:** The real workbook is ignored by Git. A separate locked public demo workbook is included for portfolio display.

## Backend Setup

From the project folder:

```bash
cd rental-housing-system
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Create an environment file:

```bash
cp .env.example .env
```

Then add your Groq key:

```text
GROQ_API_KEY=your_real_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

Do not commit `.env`.

Run the backend:

```bash
python -m uvicorn backend.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Frontend Setup

Open a second terminal:

```bash
cd rental-housing-system/frontend
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

The frontend calls the backend at:

```text
http://127.0.0.1:8000
```

To use another backend URL:

```bash
VITE_API_BASE_URL="http://127.0.0.1:8001" npm run dev
```

## Main API Endpoints

### Read-only

```text
GET /health
GET /rooms
GET /payments
GET /summary
GET /rooms/empty
GET /payments/late
GET /payments/unpaid
GET /room/{room_id}
GET /audit-log
```

### Safe write/update

All write endpoints support preview mode.

```text
POST /rental-periods/auto-rollover
POST /payments/update-current
POST /tenants/move-out
POST /tenants/move-in
POST /rooms/update-rent
POST /undo/last-change
```

Preview example:

```json
{
  "room_id": 101,
  "amount_paid": 550000,
  "payment_date": "2026-07-01",
  "payment_method": "Transfer",
  "preview": true,
  "user_message": "Room 101 paid by transfer"
}
```

### Chatbot

```text
POST /chat
POST /chat/confirm
GET /chat/pending-actions
```

Question example:

```json
{
  "message": "Which rooms are unpaid?"
}
```

Update example:

```json
{
  "message": "Room 101 paid today by transfer"
}
```

The response will request confirmation before saving:

```json
{
  "type": "confirmation_required",
  "action_id": "abc123",
  "message": "I will mark Room 101 as paid by Transfer. Should I save this?",
  "preview": {}
}
```

Confirm:

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

## Frontend Pages

- **Dashboard:** summary cards, occupied/empty rooms, alerts
- **Rooms:** room table with filters
- **Payments:** user-friendly monthly payment view
- **Raw Data:** spreadsheet-like payment table for checking records
- **Chatbot:** natural language questions and update previews
- **Auto Rollover:** preview and confirm next rental period rows
- **Audit Log:** recent confirmed changes and undo controls

## Manual Test Checklist

- Dashboard loads summary cards.
- Occupied rooms appear green.
- Empty rooms appear red.
- Late and unpaid alerts appear.
- Rooms table filters work.
- Monthly payment view groups by room and rent start month.
- Raw data page shows all payment rows.
- Chatbot answers "Which rooms are empty?"
- Chatbot previews "Room 101 paid today by transfer."
- Chatbot requires confirmation before saving.
- Confirmed chat action creates a backup and audit log.
- Auto rollover preview shows proposed rows.
- User can uncheck rooms before confirming rollover.
- Undo last change previews the selected backup before restoring.
- Real `.env`, real Excel data, backups, and `node_modules` are not committed.

## Notes For Future Work

- Support multiple rental locations with a property selector.
- Add role-based user access.
- Move from Excel to a database when the workflow is stable.
- Add deployment for the backend and frontend.
- Add automated tests around the Excel update functions.

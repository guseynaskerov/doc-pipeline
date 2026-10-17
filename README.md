# doc-pipeline: LLM email triage with n8n and a Python validation service

An automation that reads incoming emails, classifies them with an LLM, extracts key data, validates the result with code, stores it in Postgres and sends a Telegram notification. PDF attachments are read by a small FastAPI service. Results that fail validation are flagged for human review. The classifier is measured on a labeled test set.

Built as a learning project: n8n, FastAPI, Docker Compose, Postgres, structured LLM output, testing and basic evaluation.

## How it works

```
Gmail (IMAP)
    |
    v
Has attachment? --yes--> pdf-service /extract (PDF -> text) --+
    |                                                         |
    +--no-----------------------------------------------------+
                                                              v
                                       Edit Fields (email text + PDF text)
                                                              |
                                                              v
                                            LLM (Groq, structured JSON output)
                                                              |
                                                              v
                                         pdf-service /validate (rules in code)
                                                              |
                                                              v
                                                   Postgres (status saved)
                                                              |
                                              not spam? -> status = processed?
                                                              |          |
                                                    Telegram: OK   Telegram: needs review
```

1. **Email Trigger (IMAP)** picks up new unread mail from a test Gmail inbox and downloads attachments.
2. If there is an attachment, **pdf-service `/extract`** returns its text. If the attachment is not a PDF, the error output is used and the email continues without it.
3. **Basic LLM Chain** (`openai/gpt-oss-120b` via Groq) returns JSON: `type`, `sender`, `amount`, `currency`, `due_date`, `summary`, `confidence`. A Structured Output Parser with Auto-Fix enforces the format.
4. **pdf-service `/validate`** checks the model output with plain code. It returns `processed` or `needs_review`.
5. **Postgres** stores every email with that status.
6. **Telegram** notifies about non-spam emails. Spam is stored but does not trigger a notification.

Email types: `invoice`, `complaint`, `request`, `spam`, `other`.

## Why a validation service

The LLM's confidence score turned out to be unreliable (see evaluation below), so the final decision is made by deterministic rules in `pdf-service/app/validation.py`:

- type must be one of the five allowed values
- confidence must be a number between 0 and 1, and at least 0.8
- `due_date`, if present, must be a valid `YYYY-MM-DD` date
- an invoice must have a positive amount and a currency from a known list

**Example from testing.** An email saying "please pay the invoice, details will follow" was classified as `invoice` with confidence 0.85 and amount 0. Under the old confidence-only threshold it would have been stored as processed. The validation rule "invoice without a positive amount" flagged it as `needs_review`, and the Telegram alert said so.

## pdf-service

A small FastAPI app in `pdf-service/`, started by Docker Compose (not exposed outside the Docker network; n8n calls `http://pdf-service:8000`).

| Endpoint | Purpose |
|---|---|
| `GET /health` | health check |
| `POST /extract` | accepts a PDF, returns `pages`, `has_text` and `text`; returns 400 for non-PDF files |
| `POST /validate` | accepts the model's JSON, returns `valid`, `issues` and `status` |

Tests (`pytest`, 12 tests) cover the validation rules and the API endpoints, including a sample PDF invoice:

```bash
cd pdf-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -v
```

## Evaluation of the classifier

A separate workflow (`workflows/evaluation.json`) runs a labeled dataset through the same prompt and computes accuracy. It processes emails one at a time with a 10-second pause to stay within the Groq free-tier limit (8,000 tokens per minute).

| Test set | Emails | Prompt v1 | Prompt v2 |
|---|---|---|---|
| Base set (RU/EN, clear cases) | 30 | 96.7% (29/30) | 100% (30/30) |
| Hard set (Azerbaijani, phishing, ambiguous cases) | 20 | not measured | 100% (20/20) |

**What changed between v1 and v2.** On the base set the model labeled a technology newsletter as `spam` with confidence 0.99. The class definitions were tightened:

- `spam`: unsolicited advertising, fraud, phishing, requests for card data
- `other`: everything else, including newsletters, system notifications and personal mail

## Limitations (please read before trusting the numbers)

- Both datasets are **small and synthetic**, written by the author. They are not real inbox data.
- The v2 prompt was adjusted after looking at the one failure in the base set, so the base-set result is **not an independent test**. The hard set was written afterwards and is a better, but still limited, check.
- The evaluation measures **classification only**. The PDF path and the validation rules are covered by unit tests and a few manual runs, not by a labeled dataset.
- The model was **overconfident**: the one wrong answer had confidence 0.99. In live testing the same near-empty email was labeled `other` (0.85) in one run and `spam` (0.9) in another.
- Validation checks that a result is **plausible**, not that it is **correct**: it cannot tell whether an amount matches the PDF.
- Only text PDFs are supported (no OCR); only the first attachment is read.
- Spam does not trigger a notification, so a legitimate email misclassified as spam would go unnoticed.
- Not yet tested on a real inbox over time.

## Repository layout

```
docker-compose.yml        n8n + Postgres + pdf-service
workflows/
  email-parser.json       main workflow
  evaluation.json         evaluation workflow (contains the 30-email base set)
pdf-service/
  app/main.py             FastAPI endpoints
  app/validation.py       validation rules
  tests/                  pytest tests and a sample PDF invoice
  Dockerfile
```

## Setup

Requires Docker with the Compose plugin.

1. Create a `.env` file next to `docker-compose.yml`:
   ```
   POSTGRES_PASSWORD=choose_a_password
   ```
2. Build and start the stack (this also builds `pdf-service`):
   ```bash
   docker compose up -d --build
   ```
3. Create the application database and table:
   ```bash
   docker compose exec postgres psql -U n8n -c "CREATE DATABASE docs;"
   docker compose exec postgres psql -U n8n -d docs -c "CREATE TABLE documents (
     id SERIAL PRIMARY KEY,
     received_at TIMESTAMPTZ DEFAULT now(),
     email_text TEXT,
     type TEXT,
     sender TEXT,
     amount NUMERIC,
     currency TEXT,
     due_date TEXT,
     summary TEXT,
     confidence NUMERIC,
     status TEXT DEFAULT 'new'
   );"
   ```
4. Open n8n at `http://localhost:5678`, create the owner account and import both files from `workflows/`.
5. Create credentials in n8n:
   - **IMAP** (host `imap.gmail.com`, port 993, a Gmail app password)
   - **Groq** (API key)
   - **Postgres** (host `postgres`, database `docs`, user `n8n`)
   - **Telegram** (bot token from @BotFather)
6. In both Telegram nodes replace `YOUR_CHAT_ID` with your chat ID.

This is a local development setup. It is not hardened for production use. Do not commit `.env` or any API keys.

## Roadmap

- Evaluation on real emails with manual labels, including PDF attachments
- OCR for scanned PDFs
- Check extracted values against the PDF text, not only for plausibility
- Stricter handling of emails classified as spam
- Store the evaluation datasets as separate files in the repository

## Stack

n8n, FastAPI, pytest, PostgreSQL, Docker Compose, Groq (`openai/gpt-oss-120b`), Telegram Bot API.

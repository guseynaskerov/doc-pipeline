# doc-pipeline: LLM email triage with n8n

An automation that reads incoming emails, classifies them with an LLM, extracts key data, stores it in Postgres and sends a Telegram notification. Low-confidence results are flagged for human review. The classifier is measured on a labeled test set, not just eyeballed.

Built as a learning project: n8n, Docker Compose, Postgres, structured LLM output and basic evaluation.

## How it works

```
Gmail (IMAP) -> Edit Fields -> LLM (Groq, structured output) -> Postgres
                                                                   |
                                          type != spam? -> confidence >= 0.8?
                                                              |            |
                                                      Telegram: OK    Telegram: needs review
```

1. **Email Trigger (IMAP)** picks up new unread mail from a test Gmail inbox.
2. **Basic LLM Chain** (`openai/gpt-oss-120b` via Groq) returns JSON: `type`, `sender`, `amount`, `currency`, `due_date`, `summary`, `confidence`.
3. **Structured Output Parser** with Auto-Fix enforces the JSON format.
4. **Postgres** stores every email. `status` is `processed` or `needs_review` depending on the model's confidence (threshold 0.8).
5. **Telegram** notifies about non-spam emails. Spam is stored but does not trigger a notification.

Email types: `invoice`, `complaint`, `request`, `spam`, `other`.

## Evaluation

A separate workflow (`workflows/evaluation.json`) runs a labeled dataset through the same prompt and computes accuracy. It processes emails one at a time with a 10-second pause to stay within the Groq free-tier limit (8,000 tokens per minute).

| Test set | Emails | Prompt v1 | Prompt v2 |
|---|---|---|---|
| Base set (RU/EN, clear cases) | 30 | 96.7% (29/30) | 100% (30/30) |
| Hard set (Azerbaijani, phishing, ambiguous cases) | 20 | not measured | 100% (20/20) |

**What changed between v1 and v2.** On the base set the model labeled a technology newsletter as `spam` with confidence 0.99. The class definitions were tightened:

- `spam`: unsolicited advertising, fraud, phishing, requests for card data
- `other`: everything else, including newsletters, system notifications and personal mail

### Limitations (please read before trusting the numbers)

- Both datasets are **small and synthetic**, written by the author. They are not real inbox data.
- The v2 prompt was adjusted after looking at the one failure in the base set, so the base-set result is **not an independent test**. The hard set was written afterwards and is a better, but still limited, check.
- The model was **overconfident**: the one wrong answer had confidence 0.99, so the confidence threshold does not reliably catch errors.
- In live testing the same near-empty email ("see attachment") was labeled `other` (0.85) in one run and `spam` (0.9) in another. Borderline emails can be unstable.
- Spam does not trigger a notification, so a legitimate email misclassified as spam would go unnoticed.
- Not yet tested on a real inbox over time. Attachments (PDF) are not processed.

## Repository layout

```
docker-compose.yml        n8n + Postgres
workflows/
  email-parser.json       main workflow
  evaluation.json         evaluation workflow (contains the 30-email base set)
```

## Setup

Requires Docker with the Compose plugin.

1. Create a `.env` file next to `docker-compose.yml`:
   ```
   POSTGRES_PASSWORD=choose_a_password
   ```
2. Start the stack:
   ```bash
   docker compose up -d
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

- FastAPI service for PDF attachments (text extraction and validation in code)
- Evaluation on real emails with manual labels
- Stricter review rules for spam and for emails with unclear content
- Store the evaluation datasets as separate files in the repository

## Stack

n8n, PostgreSQL, Docker Compose, Groq (`openai/gpt-oss-120b`), Telegram Bot API.

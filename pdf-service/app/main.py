import io

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.validation import validate_result

app = FastAPI(title="pdf-service")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    data = await file.read()
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except PdfReadError:
        raise HTTPException(status_code=400, detail="Not a valid PDF")
    return {"pages": len(reader.pages), "has_text": bool(text), "text": text}


@app.post("/validate")
def validate(result: dict = Body(...)):
    issues = validate_result(result)
    return {
        "valid": not issues,
        "issues": issues,
        "status": "needs_review" if issues else "processed",
    }

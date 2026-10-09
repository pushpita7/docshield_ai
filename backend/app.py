
import hashlib
from io import BytesIO

import fitz
from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware


# -----------------------------
# Configuration
# -----------------------------

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

app = FastAPI(
    title="DocShield AI",
    description="AI-assisted document and certificate screening API",
    version="1.0.0",
)


# -----------------------------
# CORS Configuration
# -----------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Home Route
# -----------------------------

@app.get("/")
def home():
    return {
        "message": "Welcome to DocShield AI",
        "status": "running",
        "docs": "/docs",
    }


# -----------------------------
# Health Check
# -----------------------------

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "DocShield AI",
    }


# -----------------------------
# Document Analysis
# -----------------------------

@app.post("/analyze")
async def analyze_document(file: UploadFile = File(...)):

    filename = file.filename or "unknown"
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Validate file extension
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a PDF, PNG, JPG, or JPEG file.",
        )

    # Read uploaded file
    content = await file.read()

    # Validate file size
    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum allowed size is 10 MB.",
        )

    # Calculate SHA-256 fingerprint
    file_hash = hashlib.sha256(content).hexdigest()

    # Common result fields
    result = {
        "filename": filename,
        "file_type": extension.replace(".", "").upper(),
        "file_size_bytes": len(content),
        "sha256": file_hash,
        "status": "Analysis completed",
        "pages": None,
        "extracted_text_characters": None,
        "metadata": {},
        "observations": [],
        "disclaimer": (
            "This tool performs preliminary document screening. "
            "Its results do not prove that a document is genuine or fraudulent."
        ),
    }

    # -----------------------------
    # PDF Analysis
    # -----------------------------

    if extension == ".pdf":

        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file does not have a valid PDF signature.",
            )

        try:
            with fitz.open(stream=content, filetype="pdf") as pdf:

                if pdf.is_encrypted:
                    raise HTTPException(
                        status_code=400,
                        detail="Password-protected PDFs are not supported.",
                    )

                if pdf.page_count == 0:
                    raise HTTPException(
                        status_code=400,
                        detail="The PDF contains no pages.",
                    )

                # Extract document text
                extracted_text = ""

                for page in pdf:
                    extracted_text += page.get_text()

                # Extract PDF metadata
                pdf_metadata = pdf.metadata or {}

                metadata = {
                    "author": pdf_metadata.get("author") or None,
                    "creator": pdf_metadata.get("creator") or None,
                    "producer": pdf_metadata.get("producer") or None,
                    "creation_date": pdf_metadata.get("creationDate") or None,
                    "modification_date": pdf_metadata.get("modDate") or None,
                }

                observations = []

                # Check missing metadata
                if not metadata["author"]:
                    observations.append(
                        "PDF author information is missing."
                    )

                if not metadata["creation_date"]:
                    observations.append(
                        "PDF creation date is missing."
                    )

                # Check extracted text
                if not extracted_text.strip():
                    observations.append(
                        "No selectable text was extracted. "
                        "The document may be scanned or image-based."
                    )

                # Populate result
                result["pages"] = pdf.page_count
                result["extracted_text_characters"] = len(extracted_text)
                result["metadata"] = metadata
                result["observations"] = observations

        except HTTPException:
            raise

        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Unable to read this PDF. The file may be damaged or invalid.",
            )

    # -----------------------------
    # Image Analysis
    # -----------------------------

    else:

        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()

            with Image.open(BytesIO(content)) as image:
                width, height = image.size

                result["image_dimensions"] = {
                    "width": width,
                    "height": height,
                }

                result["metadata"] = {
                    "format": image.format,
                    "mode": image.mode,
                }

                result["observations"] = []

        except (UnidentifiedImageError, OSError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="Unable to read this image. The file may be damaged or invalid.",
            )

    return result


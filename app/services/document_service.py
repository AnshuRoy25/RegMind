from __future__ import annotations

import hashlib
import logging
import mimetypes
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image

from regmind.app.core.config import settings
from regmind.app.core.database import SessionLocal
from regmind.app.models.circular import Circular, CircularPage
from regmind.app.services.common import org_id_or_none

log = logging.getLogger("regmind.documents")

OCR_MIN_CHARS = 24
OCR_DPI = 220


class DocumentError(ValueError):
    pass


@dataclass
class PageText:
    page_number: int
    text: str
    ocr_used: bool = False
    confidence: float = 0.0


@dataclass
class ExtractedDocument:
    text: str
    pages: list[PageText] = field(default_factory=list)
    ocr_used: bool = False
    mimetype: str = ""
    sha256: str = ""


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _ocr_image(image: Image.Image) -> tuple[str, float]:
    if not ocr_available():
        raise DocumentError(
            "The document appears to be scanned and Tesseract OCR is not installed. "
            "Install Tesseract and make sure it is on PATH."
        )
    data = pytesseract.image_to_data(
        image, output_type=pytesseract.Output.DICT, config="--psm 6"
    )
    words = []
    confidences = []
    for index, word in enumerate(data.get("text", [])):
        if word and word.strip():
            words.append(word.strip())
            try:
                confidence = float(data["conf"][index])
            except (KeyError, IndexError, TypeError, ValueError):
                continue
            if confidence >= 0:
                confidences.append(confidence)
    text = " ".join(words).strip()
    average = sum(confidences) / len(confidences) if confidences else 0.0
    return text, round(average, 2)


def _extract_pdf(path: Path) -> ExtractedDocument:
    pages: list[PageText] = []
    ocr_used = False
    with pymupdf.open(path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text().strip()
            used_ocr = False
            confidence = 0.0
            if len(text) < OCR_MIN_CHARS:
                try:
                    pixmap = page.get_pixmap(dpi=OCR_DPI)
                    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                    ocr_text, confidence = _ocr_image(image)
                    if ocr_text:
                        text = ocr_text
                        used_ocr = True
                        ocr_used = True
                except DocumentError:
                    raise
                except Exception as exc:
                    log.warning("OCR failed for page %s: %s", index, exc)
            pages.append(
                PageText(
                    page_number=index,
                    text=text,
                    ocr_used=used_ocr,
                    confidence=confidence,
                )
            )
    combined = "\n\n".join(
        f"[page {page.page_number}]\n{page.text}" for page in pages if page.text
    ).strip()
    return ExtractedDocument(text=combined, pages=pages, ocr_used=ocr_used)


def _extract_docx(path: Path) -> ExtractedDocument:
    from docx import Document as DocxDocument

    document = DocxDocument(str(path))
    chunks = [paragraph.text.strip() for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                chunks.append(" | ".join(cells))
    text = "\n".join(chunk for chunk in chunks if chunk).strip()
    if not text:
        raise DocumentError("No text found in the Word document")
    return ExtractedDocument(text=text, pages=[PageText(1, text)])


def _extract_image(path: Path) -> ExtractedDocument:
    with Image.open(path) as image:
        text, confidence = _ocr_image(image.convert("RGB"))
    if not text:
        raise DocumentError("OCR found no text in the image")
    return ExtractedDocument(
        text=text,
        pages=[PageText(1, text, ocr_used=True, confidence=confidence)],
        ocr_used=True,
    )


def extract_document(path: str | Path) -> ExtractedDocument:
    file_path = Path(path)
    if not file_path.exists():
        raise DocumentError(f"File not found: {file_path}")
    mimetype = mimetypes.guess_type(file_path.name)[0] or ""
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".pdf":
            extracted = _extract_pdf(file_path)
        elif suffix in (".docx", ".doc"):
            extracted = _extract_docx(file_path)
        elif suffix in (".txt", ".md", ".csv", ".json", ".html", ".htm"):
            text = file_path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                raise DocumentError("The text file is empty")
            extracted = ExtractedDocument(text=text, pages=[PageText(1, text)])
        elif suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"):
            extracted = _extract_image(file_path)
        else:
            raise DocumentError(f"Unsupported file type: {suffix or 'unknown'}")
    except DocumentError:
        raise
    except Exception as exc:
        raise DocumentError(f"Could not read {file_path.name}: {exc}") from exc

    if not extracted.text.strip():
        raise DocumentError("No text found in the document")
    extracted.mimetype = mimetype
    extracted.sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
    return extracted


def _title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned and not cleaned.lower().startswith("[page"):
            return cleaned[:200]
    return fallback[:200]


class DocumentService:
    async def ingest(
        self,
        *,
        path: str | Path,
        title: str = "",
        kind: str = "master",
        applies: bool = True,
        source_filename: str = "",
        raw_text: str | None = None,
    ) -> dict:
        file_path = Path(path).resolve()
        extracted = None
        if raw_text is None:
            extracted = extract_document(file_path)
            raw_text = extracted.text
        title = title.strip() or _title_from_text(raw_text, file_path.stem)
        org_id = org_id_or_none()

        db = SessionLocal()
        try:
            row = Circular(
                org_id=org_id,
                title=title,
                kind=kind,
                applies=applies,
                raw_text=raw_text,
                source_filename=source_filename or file_path.name,
                source_path=str(file_path),
                sha256=extracted.sha256 if extracted else "",
                mimetype=extracted.mimetype if extracted else "",
                status="registered",
            )
            db.add(row)
            db.flush()
            if extracted is not None:
                for page in extracted.pages:
                    db.add(
                        CircularPage(
                            circular_id=row.id,
                            page_number=page.page_number,
                            text=page.text,
                            ocr_used=page.ocr_used,
                            confidence=page.confidence,
                        )
                    )
            db.commit()
            return {
                "id": row.id,
                "title": row.title,
                "kind": row.kind,
                "applies": row.applies,
                "source_filename": row.source_filename,
                "source_path": row.source_path,
                "pages": len(extracted.pages) if extracted else 0,
                "ocr_used": bool(extracted and extracted.ocr_used),
                "chars": len(raw_text),
                "sha256": row.sha256,
            }
        finally:
            db.close()

    async def get_pages(self, circular_id: int) -> list[dict]:
        from sqlalchemy import select

        db = SessionLocal()
        try:
            rows = db.execute(
                select(CircularPage)
                .where(CircularPage.circular_id == circular_id)
                .order_by(CircularPage.page_number.asc())
            ).scalars().all()
            return [
                {
                    "page_number": row.page_number,
                    "text": row.text,
                    "ocr_used": row.ocr_used,
                    "confidence": row.confidence,
                }
                for row in rows
            ]
        finally:
            db.close()

    def save_upload(self, filename: str, data: bytes) -> Path:
        safe = Path(filename or "upload").name
        directory = settings.storage_dir / "uploads"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{hashlib.sha256(data).hexdigest()[:16]}-{safe}"
        path.write_bytes(data)
        return path


document_service = DocumentService()


__all__ = [
    "DocumentError",
    "DocumentService",
    "ExtractedDocument",
    "PageText",
    "document_service",
    "extract_document",
    "ocr_available",
]

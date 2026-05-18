import io
import uuid
from typing import List, Dict

from pypdf import PdfReader

DOCUMENT_STORE: Dict[str, List[dict]] = {}


class DocumentService:
    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        if filename.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(file_bytes))
            text = ""

            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            return text

        return file_bytes.decode("utf-8", errors="ignore")

    def chunk_text(self, text: str, chunk_size: int = 900, overlap: int = 150):
        chunks = []
        start = 0

        while start < len(text):
            chunk = text[start:start + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap

        return chunks

    def ingest(self, file_bytes: bytes, filename: str):
        text = self.extract_text(file_bytes, filename)

        if not text.strip():
            raise Exception("No readable text found. Try a text-based PDF, not scanned image PDF.")

        chunks = self.chunk_text(text)
        document_id = str(uuid.uuid4())

        DOCUMENT_STORE.clear()

        DOCUMENT_STORE[document_id] = [
            {
                "text": chunk,
                "document_name": filename,
                "chunk_index": i,
            }
            for i, chunk in enumerate(chunks)
        ]

        return {
            "message": "Document uploaded successfully",
            "document_id": document_id,
            "filename": filename,
            "chunks": len(chunks),
        }

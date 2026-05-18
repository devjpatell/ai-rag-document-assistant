from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.document_service import DocumentService
from app.services.query_service import QueryService

router = APIRouter(prefix="/api", tags=["RAG"])


class QueryRequest(BaseModel):
    question: str


@router.get("/test")
def test():
    return {"message": "API route working"}


@router.post("/ingest")
async def ingest_document(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        service = DocumentService()
        return service.ingest(file_bytes, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_documents(request: QueryRequest):
    try:
        service = QueryService()
        return service.answer_question(request.question)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
import db
import embedder

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    author: Optional[str] = None


class TweetResult(BaseModel):
    id: str
    username: str
    text: str
    url: str
    created_at: str
    score: float


@router.post("/search", response_model=list[TweetResult])
async def search(req: SearchRequest):
    embedding = await embedder.embed(req.query)
    results = await db.semantic_search(embedding, limit=req.limit, author=req.author)
    return results

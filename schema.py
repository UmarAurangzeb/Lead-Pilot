from pydantic import BaseModel, Field
from typing import List

class QueryResponse(BaseModel):
    queries: List[str] = Field(..., min_length=5, max_length=15)
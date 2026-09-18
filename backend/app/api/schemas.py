from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = 10
    use_agent: bool = True
    use_graph: bool = True
    session_id: str = Field(default="", max_length=64)


class IngestRequest(BaseModel):
    strategy: str = "parent_child"  # sliding | semantic | parent_child


class FeedbackRequest(BaseModel):
    session_id: str = Field(default="", max_length=64)
    query: str = Field(min_length=2, max_length=1000)
    vote: str = Field(description="up|down")
    note: str = Field(default="", max_length=500)

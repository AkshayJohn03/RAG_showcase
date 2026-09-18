"""Central config — env-driven, zero hard deps (pydantic-settings optional)."""
from __future__ import annotations
import os

try:
    from pydantic_settings import BaseSettings as _Base

    class Settings(_Base):
        llm_provider: str = "none"
        ollama_model: str = "llama3.1"
        ollama_base_url: str = "http://localhost:11434"
        openai_api_key: str = ""
        openai_model: str = "gpt-4o-mini"
        vector_backend: str = "local"
        qdrant_url: str = "http://localhost:6333"
        qdrant_collection: str = "rag_showcase"
        embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
        chunk_strategy: str = "parent_child"
        chunk_size: int = 512
        chunk_overlap: int = 80
        hybrid_alpha: float = 0.5
        rerank_top_n: int = 5
        reranker: str = "auto"  # auto | heuristic | cross-encoder
        langfuse_public_key: str = ""
        langfuse_secret_key: str = ""
        langfuse_host: str = "https://cloud.langfuse.com"
        prewarm_samples: bool = True
        api_port: int = 8000

        class Config:
            env_file = ".env"
            extra = "ignore"

    settings = Settings()
except Exception:
    # fallback: plain env reader so ingest/query run without extra installs
    class Settings:
        def __init__(self):
            g = os.getenv
            self.llm_provider = g("LLM_PROVIDER", "none")
            self.ollama_model = g("OLLAMA_MODEL", "llama3.1")
            self.ollama_base_url = g("OLLAMA_BASE_URL", "http://localhost:11434")
            self.openai_api_key = g("OPENAI_API_KEY", "")
            self.openai_model = g("OPENAI_MODEL", "gpt-4o-mini")
            self.vector_backend = g("VECTOR_BACKEND", "local")
            self.qdrant_url = g("QDRANT_URL", "http://localhost:6333")
            self.qdrant_collection = g("QDRANT_COLLECTION", "rag_showcase")
            self.embed_model = g("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            self.chunk_strategy = g("CHUNK_STRATEGY", "parent_child")
            self.chunk_size = int(g("CHUNK_SIZE", "512"))
            self.chunk_overlap = int(g("CHUNK_OVERLAP", "80"))
            self.hybrid_alpha = float(g("HYBRID_ALPHA", "0.5"))
            self.rerank_top_n = int(g("RERANK_TOP_N", "5"))
            self.reranker = g("RERANKER", "auto")
            self.langfuse_public_key = g("LANGFUSE_PUBLIC_KEY", "")
            self.langfuse_secret_key = g("LANGFUSE_SECRET_KEY", "")
            self.langfuse_host = g("LANGFUSE_HOST", "https://cloud.langfuse.com")
            self.prewarm_samples = g("PREWARM_SAMPLES", "1") == "1"
            self.api_port = int(g("API_PORT", "8000"))

    settings = Settings()

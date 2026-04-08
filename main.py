"""FastAPI 엔트리포인트 — Memory Module 서버"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 리소스 관리"""
    # --- Startup ---
    metadata_store = MetadataStore(settings.sqlite_path)
    await metadata_store.initialize()
    app.state.metadata_store = metadata_store

    graph_store = GraphStore(metadata_store)
    await graph_store.load_from_db()
    app.state.graph_store = graph_store

    yield

    # --- Shutdown: 그래프 직렬화 ---
    await graph_store.persist()
    await metadata_store.close()


app = FastAPI(
    title="AI Agent Memory Module",
    description="선제적 AI 메모리 — Anticipatory Memory Chains",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

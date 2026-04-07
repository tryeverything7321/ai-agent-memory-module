"""공통 pytest fixtures"""

import pytest
import pytest_asyncio

from storage.metadata_store import MetadataStore
from storage.graph_store import GraphStore
from storage.vector_store import VectorStore, MockEmbeddingProvider


@pytest_asyncio.fixture
async def metadata_store():
    store = MetadataStore(":memory:")
    await store.initialize()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def graph_store(metadata_store):
    store = GraphStore(metadata_store)
    return store


@pytest_asyncio.fixture
async def vector_store():
    provider = MockEmbeddingProvider(dim=1024)
    store = VectorStore(embedding_provider=provider, use_qdrant=False)
    await store.initialize()
    return store

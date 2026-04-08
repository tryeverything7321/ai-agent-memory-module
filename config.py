"""설정 모듈 — API endpoints, decay 파라미터, 모델 설정"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- 서버 ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Qdrant ---
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "memories"
    embedding_dim: int = 1024

    # --- SQLite ---
    sqlite_path: str = "memory.db"

    # --- LLM / Embedding API ---
    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "default"
    llm_api_key: str = "no-key"
    embedding_base_url: str = "http://localhost:8080/v1"
    embedding_model: str = "multilingual-e5-large"

    # --- Decay 파라미터 ---
    # λ 값: ephemeral=0.3, important=0.05, critical=0.005
    decay_lambda_ephemeral: float = 0.3
    decay_lambda_important: float = 0.05
    decay_lambda_critical: float = 0.005
    decay_boost_factor: float = 0.05
    decay_prune_threshold: float = 0.1

    # --- Prediction ---
    prediction_threshold: float = 0.5
    rrf_k: int = 60
    rrf_top_n: int = 5

    # --- 동시성 ---
    max_concurrent_extractions: int = 3

    # --- 그래프 직렬화 ---
    graph_serialize_interval: int = 10  # 변경 N건마다

    # --- Taxonomy ---
    taxonomy_persist_dir: str = "data/taxonomy"
    taxonomy_sweep_interval: int = 50  # decay sweep 주기 (턴)

    model_config = {"env_prefix": "MEMORY_", "env_file": ".env"}


settings = Settings()

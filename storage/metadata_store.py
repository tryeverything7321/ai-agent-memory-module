"""SQLite 기반 메타데이터 저장소 — decay weight, timestamps, 메모리 메타데이터 관리"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Optional

from models import Memory, Importance


class MetadataStore:
    """SQLite 기반 메모리 메타데이터 + decay weight 관리"""

    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    async def initialize(self) -> None:
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                facts_json TEXT DEFAULT '[]',
                importance TEXT DEFAULT 'ephemeral',
                decay_lambda REAL DEFAULT 0.3,
                decay_weight REAL DEFAULT 1.0,
                access_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_accessed_at TEXT NOT NULL,
                is_valid INTEGER DEFAULT 1,
                session_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);
            CREATE INDEX IF NOT EXISTS idx_memories_decay_weight ON memories(decay_weight);
            CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);

            CREATE TABLE IF NOT EXISTS graph_edges (
                graph_name TEXT NOT NULL,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                edge_data TEXT DEFAULT '{}',
                PRIMARY KEY (graph_name, source, target)
            );

            CREATE TABLE IF NOT EXISTS graph_nodes (
                graph_name TEXT NOT NULL,
                node_id TEXT NOT NULL,
                node_data TEXT DEFAULT '{}',
                PRIMARY KEY (graph_name, node_id)
            );
        """)
        self._conn.commit()

    async def save_memory(self, memory: Memory) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO memories
               (id, user_id, content, facts_json, importance, decay_lambda,
                decay_weight, access_count, created_at, last_accessed_at, is_valid, session_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                memory.id, memory.user_id, memory.content,
                json.dumps([f.model_dump() for f in memory.facts], ensure_ascii=False),
                memory.importance.value, memory.decay_lambda,
                memory.decay_weight, memory.access_count,
                memory.created_at.isoformat(), memory.last_accessed_at.isoformat(),
                int(memory.is_valid), memory.session_id,
            ),
        )
        self._conn.commit()

    async def get_memory(self, memory_id: str) -> Optional[Memory]:
        row = self._conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_memory(row)

    async def get_memories_by_user(self, user_id: str, valid_only: bool = True) -> list[Memory]:
        query = "SELECT * FROM memories WHERE user_id = ?"
        params: list = [user_id]
        if valid_only:
            query += " AND is_valid = 1"
        query += " ORDER BY created_at DESC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def get_memories_by_ids(self, memory_ids: list[str]) -> list[Memory]:
        """배치 조회 — N+1 방지 (PERF-3)"""
        if not memory_ids:
            return []
        placeholders = ",".join("?" * len(memory_ids))
        rows = self._conn.execute(
            f"SELECT * FROM memories WHERE id IN ({placeholders})", memory_ids
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def search_by_time_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> list[Memory]:
        rows = self._conn.execute(
            """SELECT * FROM memories
               WHERE user_id = ? AND is_valid = 1
                 AND created_at BETWEEN ? AND ?
               ORDER BY decay_weight DESC""",
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def update_decay_weight(self, memory_id: str, weight: float) -> None:
        self._conn.execute(
            "UPDATE memories SET decay_weight = ? WHERE id = ?", (weight, memory_id)
        )
        self._conn.commit()

    async def update_access(self, memory_id: str) -> None:
        """접근 시 access_count 증가 + last_accessed_at 갱신"""
        self._conn.execute(
            """UPDATE memories
               SET access_count = access_count + 1,
                   last_accessed_at = ?
               WHERE id = ?""",
            (datetime.now().isoformat(), memory_id),
        )
        self._conn.commit()

    async def invalidate_memory(self, memory_id: str) -> None:
        self._conn.execute(
            "UPDATE memories SET is_valid = 0 WHERE id = ?", (memory_id,)
        )
        self._conn.commit()

    async def delete_memories_below_threshold(self, threshold: float) -> int:
        """프루닝: 임계치 미달 메모리 삭제"""
        cursor = self._conn.execute(
            "DELETE FROM memories WHERE decay_weight < ? AND is_valid = 1",
            (threshold,),
        )
        self._conn.commit()
        return cursor.rowcount

    async def get_all_memories_unfiltered(self) -> list[Memory]:
        """모든 메모리 반환 (valid + invalid) — 분석용"""
        rows = self._conn.execute("SELECT * FROM memories").fetchall()
        return [self._row_to_memory(r) for r in rows]

    async def get_all_valid_memories(self, user_id: str) -> list[Memory]:
        rows = self._conn.execute(
            "SELECT * FROM memories WHERE user_id = ? AND is_valid = 1",
            (user_id,),
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    # --- Graph 직렬화 ---

    async def save_graph_data(
        self, graph_name: str, nodes: list[tuple], edges: list[tuple]
    ) -> None:
        """NetworkX 그래프를 SQLite에 직렬화"""
        self._conn.execute(
            "DELETE FROM graph_nodes WHERE graph_name = ?", (graph_name,)
        )
        self._conn.execute(
            "DELETE FROM graph_edges WHERE graph_name = ?", (graph_name,)
        )
        for node_id, node_data in nodes:
            self._conn.execute(
                "INSERT INTO graph_nodes (graph_name, node_id, node_data) VALUES (?, ?, ?)",
                (graph_name, str(node_id), json.dumps(node_data, ensure_ascii=False)),
            )
        for source, target, edge_data in edges:
            self._conn.execute(
                "INSERT INTO graph_edges (graph_name, source, target, edge_data) VALUES (?, ?, ?, ?)",
                (graph_name, str(source), str(target), json.dumps(edge_data, ensure_ascii=False)),
            )
        self._conn.commit()

    async def load_graph_data(self, graph_name: str) -> tuple[list, list]:
        """SQLite에서 그래프 복원"""
        node_rows = self._conn.execute(
            "SELECT node_id, node_data FROM graph_nodes WHERE graph_name = ?",
            (graph_name,),
        ).fetchall()
        edge_rows = self._conn.execute(
            "SELECT source, target, edge_data FROM graph_edges WHERE graph_name = ?",
            (graph_name,),
        ).fetchall()
        nodes = [(r["node_id"], json.loads(r["node_data"])) for r in node_rows]
        edges = [(r["source"], r["target"], json.loads(r["edge_data"])) for r in edge_rows]
        return nodes, edges

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> Memory:
        from models import Fact
        facts_raw = json.loads(row["facts_json"]) if row["facts_json"] else []
        facts = [Fact(**f) for f in facts_raw]
        return Memory(
            id=row["id"],
            user_id=row["user_id"],
            content=row["content"],
            facts=facts,
            importance=Importance(row["importance"]),
            decay_lambda=row["decay_lambda"],
            decay_weight=row["decay_weight"],
            access_count=row["access_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_accessed_at=datetime.fromisoformat(row["last_accessed_at"]),
            is_valid=bool(row["is_valid"]),
            session_id=row["session_id"],
        )

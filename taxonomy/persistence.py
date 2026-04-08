"""Taxonomy Persistence — TaxonomyGraph + Lineage 디스크 저장/복원

서버 재시작 후에도 taxonomy 상태를 유지한다.
두 개의 JSON 파일로 분리 저장:
  - taxonomy_state.json: TaxonomyGraph (카테고리, centroid, member 정보)
  - lineage_events.json: PhylogeneticLineage (진화 이벤트 DAG)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from taxonomy.taxonomy_graph import TaxonomyGraph
from taxonomy.lineage import PhylogeneticLineage


DEFAULT_DIR = Path("data/taxonomy")
TAXONOMY_FILE = "taxonomy_state.json"
LINEAGE_FILE = "lineage_events.json"
META_FILE = "taxonomy_meta.json"


class TaxonomyPersistence:
    """TaxonomyGraph + Lineage를 디스크에 저장/복원

    사용법:
        persistence = TaxonomyPersistence(base_dir="data/taxonomy")
        persistence.save(taxonomy, lineage, ephemeral_patterns)
        taxonomy, lineage, patterns = persistence.load()
    """

    def __init__(self, base_dir: str | Path = DEFAULT_DIR):
        self._dir = Path(base_dir)

    @property
    def base_dir(self) -> Path:
        return self._dir

    def exists(self) -> bool:
        """저장된 taxonomy 상태가 있는지 확인"""
        return (self._dir / TAXONOMY_FILE).exists()

    def save(
        self,
        taxonomy: TaxonomyGraph,
        lineage: PhylogeneticLineage,
        ephemeral_patterns: Optional[list[str]] = None,
        turn_count: int = 0,
    ) -> None:
        """현재 상태를 디스크에 저장한다.

        Args:
            taxonomy: TaxonomyGraph 인스턴스
            lineage: PhylogeneticLineage 인스턴스
            ephemeral_patterns: EPHEMERAL 판별 패턴 목록
            turn_count: 현재까지 처리한 턴 수
        """
        self._dir.mkdir(parents=True, exist_ok=True)

        # Taxonomy 저장
        taxonomy_data = taxonomy.to_json()
        with open(self._dir / TAXONOMY_FILE, "w", encoding="utf-8") as f:
            json.dump(taxonomy_data, f, ensure_ascii=False, indent=2)

        # Lineage 저장
        lineage_data = lineage.to_json()
        with open(self._dir / LINEAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(lineage_data, f, ensure_ascii=False, indent=2)

        # 메타 정보 저장
        from datetime import datetime, timezone
        meta = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "turn_count": turn_count,
            "category_count": len(taxonomy),
            "event_count": len(lineage_data),
            "ephemeral_patterns": ephemeral_patterns or [],
        }
        with open(self._dir / META_FILE, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

    def load(
        self,
    ) -> tuple[TaxonomyGraph, PhylogeneticLineage, list[str], int]:
        """디스크에서 상태를 복원한다.

        Returns:
            (taxonomy, lineage, ephemeral_patterns, turn_count)

        Raises:
            FileNotFoundError: 저장된 파일이 없을 때
        """
        taxonomy_path = self._dir / TAXONOMY_FILE
        lineage_path = self._dir / LINEAGE_FILE
        meta_path = self._dir / META_FILE

        if not taxonomy_path.exists():
            raise FileNotFoundError(f"Taxonomy 파일 없음: {taxonomy_path}")

        # Taxonomy 복원
        with open(taxonomy_path, encoding="utf-8") as f:
            taxonomy_data = json.load(f)
        taxonomy = TaxonomyGraph.from_json(taxonomy_data)

        # Lineage 복원
        lineage = PhylogeneticLineage()
        if lineage_path.exists():
            with open(lineage_path, encoding="utf-8") as f:
                lineage_data = json.load(f)
            lineage.from_json(lineage_data)

        # 메타 정보 복원
        ephemeral_patterns = []
        turn_count = 0
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            ephemeral_patterns = meta.get("ephemeral_patterns", [])
            turn_count = meta.get("turn_count", 0)

        return taxonomy, lineage, ephemeral_patterns, turn_count

    def delete(self) -> None:
        """저장된 상태를 삭제한다 (리셋용)."""
        for fname in [TAXONOMY_FILE, LINEAGE_FILE, META_FILE]:
            path = self._dir / fname
            if path.exists():
                path.unlink()

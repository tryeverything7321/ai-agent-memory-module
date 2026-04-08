"""Taxonomy Evolver — LLM 기반 동적 카테고리 분류 + 진화 관리

2단계 분류:
  1차: centroid cosine match (LLM 호출 없음, ~0ms)
  2차: LLM classify_or_propose (매칭 실패 시만, ~1초)

진화 오퍼레이션:
  - decay_sweep: 주기적 decay 계산 + prune + re-classify cascade
  - check_mitosis: 분산 높은 카테고리 분열
  - check_fusion: centroid 유사한 카테고리 병합
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from sklearn.cluster import KMeans

from taxonomy.taxonomy_graph import (
    TaxonomyGraph,
    CLASSIFY_THRESHOLD,
    SPLIT_THRESHOLD,
    MERGE_THRESHOLD,
    MIN_SPLIT_SIZE,
)
from taxonomy.lineage import PhylogeneticLineage

# --- 상수 ---
MAX_PRUNE_PER_SWEEP = 3
MAX_CASCADE_DEPTH = 1
SWEEP_INTERVAL_TURNS = 50


class TaxonomyEvolver:
    """동적 taxonomy 진화를 관리하는 메인 클래스

    TaxonomyGraph와 LLM을 연결하여:
    - 메시지를 기존/신규 카테고리로 분류
    - 주기적으로 decay sweep 실행
    - Mitosis(분열) / Fusion(병합) 판정
    """

    def __init__(
        self,
        taxonomy: TaxonomyGraph,
        lineage: PhylogeneticLineage,
        llm_client,
        embedding_provider,
    ):
        self._taxonomy = taxonomy
        self._lineage = lineage
        self._llm = llm_client
        self._embedding = embedding_provider
        self._turn_count = 0
        # memory_id → embedding 캐시 (mitosis용)
        self._embedding_cache: dict[str, list[float]] = {}

    @property
    def taxonomy(self) -> TaxonomyGraph:
        return self._taxonomy

    @property
    def lineage(self) -> PhylogeneticLineage:
        return self._lineage

    # --- 핵심: 분류 or 신규 제안 ---

    async def classify_or_propose(
        self, text: str, embedding: list[float]
    ) -> tuple[str, bool]:
        """메시지를 기존 카테고리로 분류하거나 신규 카테고리를 제안한다.

        Returns:
            (category_name, is_new): 카테고리 이름과 신규 여부
        """
        # --- 1차: centroid match (LLM 호출 없음) ---
        best = self._taxonomy.get_best_match(embedding, threshold=CLASSIFY_THRESHOLD)
        if best:
            self._taxonomy.activate_category(best, embedding)
            return best, False

        # --- 2차: LLM classify or propose ---
        existing = [c["name"] for c in self._taxonomy.get_all_categories()]
        category_name = await self._llm_classify_or_propose(text, existing)

        if category_name in self._taxonomy:
            # LLM이 기존 카테고리를 선택
            self._taxonomy.activate_category(category_name, embedding)
            return category_name, False
        else:
            # 신규 카테고리 생성
            self._taxonomy.add_category(
                name=category_name,
                centroid=embedding,
                created_by="discovery",
            )
            self._lineage.record_discovery(category_name, trigger_message=text[:100])
            return category_name, True

    async def _llm_classify_or_propose(
        self, text: str, existing_categories: list[str]
    ) -> str:
        """LLM에게 기존 카테고리 중 선택 또는 신규 제안을 요청"""
        categories_str = ", ".join(existing_categories) if existing_categories else "(없음)"

        prompt = f"""다음 메시지의 의도를 분류하세요.

메시지: "{text}"

현재 카테고리 목록: [{categories_str}]

규칙:
1. 위 카테고리 중 가장 적합한 것이 있으면 그 이름을 그대로 출력
2. 적합한 카테고리가 없으면 새 카테고리 이름을 제안 (한국어 또는 영어 snake_case, 2-3단어)
3. 카테고리 이름만 출력하세요 (다른 텍스트 없이)"""

        response = self._llm._client.chat.completions.create(
            model=self._llm._model,
            messages=[
                {"role": "system", "content": "카테고리 이름 하나만 답하세요."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=30,
        )

        raw = response.choices[0].message.content.strip().lower()
        # 공백 → underscore, 특수문자 제거
        raw = raw.replace(" ", "_").replace('"', "").replace("'", "")
        return raw

    # --- 멤버 등록 + sweep 체크 ---

    async def register_memory(
        self, category_name: str, memory_id: str, embedding: list[float]
    ) -> None:
        """메모리를 카테고리에 등록하고, 임베딩을 캐시한다."""
        self._taxonomy.add_member(category_name, memory_id)
        self._embedding_cache[memory_id] = embedding
        self._turn_count += 1

    def should_sweep(self) -> bool:
        """decay sweep 실행 시점인지 확인"""
        return self._turn_count > 0 and self._turn_count % SWEEP_INTERVAL_TURNS == 0

    # --- Decay Sweep ---

    async def decay_sweep(self, now) -> dict:
        """주기적 decay 계산 + prune + re-classify + mitosis/fusion

        Returns:
            sweep 결과 요약
        """
        from datetime import datetime as dt

        result = {
            "pruned": [],
            "reclassified": 0,
            "splits": [],
            "fusions": [],
        }

        # --- 1. Decay 재계산 ---
        self._taxonomy.decay_all(now)

        # --- 2. Prune (최대 MAX_PRUNE_PER_SWEEP개) ---
        candidates = self._taxonomy.get_candidates_for_prune()
        prune_targets = candidates[:MAX_PRUNE_PER_SWEEP]

        orphan_memories = []
        for cat_name in prune_targets:
            orphans = self._taxonomy.remove_category(cat_name)
            # decay weight 정보는 이미 prune 전에 계산됨
            self._lineage.record_extinction(cat_name, final_weight=0.0)
            orphan_memories.extend(orphans)
            result["pruned"].append(cat_name)

        # --- 3. Re-classification cascade (1 round만) ---
        for memory_id in orphan_memories:
            emb = self._embedding_cache.get(memory_id)
            if emb is None:
                continue
            # 간이 분류: centroid match만 (LLM 호출 최소화)
            best = self._taxonomy.get_best_match(emb)
            if best:
                self._taxonomy.add_member(best, memory_id)
                result["reclassified"] += 1

        # --- 4. Mitosis 체크 ---
        split_result = await self._check_mitosis()
        result["splits"] = split_result

        # --- 5. Fusion 체크 ---
        fusion_result = await self._check_fusion()
        result["fusions"] = fusion_result

        return result

    async def _check_mitosis(self) -> list[dict]:
        """분열 후보를 찾아 실행"""
        splits = []
        candidates = self._taxonomy.get_candidates_for_split(
            embeddings=self._embedding_cache
        )

        for cat_name in candidates:
            node = self._taxonomy._graph.nodes[cat_name]
            member_ids = node["member_ids"]

            # 멤버 임베딩 수집
            member_embs = []
            valid_ids = []
            for mid in member_ids:
                if mid in self._embedding_cache:
                    member_embs.append(self._embedding_cache[mid])
                    valid_ids.append(mid)

            if len(member_embs) < MIN_SPLIT_SIZE:
                continue

            # k-means(k=2)로 분할
            X = np.array(member_embs)
            kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
            labels = kmeans.fit_predict(X)

            members_a = [valid_ids[i] for i, l in enumerate(labels) if l == 0]
            members_b = [valid_ids[i] for i, l in enumerate(labels) if l == 1]

            if len(members_a) < 2 or len(members_b) < 2:
                continue

            centroid_a = kmeans.cluster_centers_[0].tolist()
            centroid_b = kmeans.cluster_centers_[1].tolist()

            # LLM에게 분할 이름 요청
            child_a_name, child_b_name = await self._propose_split_names(
                cat_name, members_a, members_b
            )

            # 분열 실행
            self._taxonomy.split_category(
                cat_name, child_a_name, child_b_name,
                members_a, members_b, centroid_a, centroid_b,
            )
            reason = f"intra-variance exceeded threshold, {len(members_a)}+{len(members_b)} members"
            self._lineage.record_split(cat_name, child_a_name, child_b_name, reason)

            splits.append({
                "parent": cat_name,
                "children": [child_a_name, child_b_name],
            })

        return splits

    async def _check_fusion(self) -> list[dict]:
        """병합 후보를 찾아 실행"""
        fusions = []
        candidates = self._taxonomy.get_candidates_for_fusion()

        for cat_a, cat_b in candidates:
            if cat_a not in self._taxonomy or cat_b not in self._taxonomy:
                continue

            # 두 centroid의 가중 평균
            node_a = self._taxonomy._graph.nodes[cat_a]
            node_b = self._taxonomy._graph.nodes[cat_b]
            n_a = max(node_a["member_count"], 1)
            n_b = max(node_b["member_count"], 1)
            c_a = np.array(node_a["centroid"])
            c_b = np.array(node_b["centroid"])
            new_centroid = ((c_a * n_a + c_b * n_b) / (n_a + n_b)).tolist()

            # LLM에게 병합 이름 요청
            merged_name = await self._propose_merge_name(cat_a, cat_b)

            # 병합 실행
            self._taxonomy.merge_categories(cat_a, cat_b, merged_name, new_centroid)
            reason = f"centroid similarity exceeded {MERGE_THRESHOLD}"
            self._lineage.record_merge(cat_a, cat_b, merged_name, reason)

            fusions.append({
                "parents": [cat_a, cat_b],
                "child": merged_name,
            })

        return fusions

    async def _propose_split_names(
        self, parent: str, members_a: list[str], members_b: list[str]
    ) -> tuple[str, str]:
        """LLM에게 분열 후 자식 이름을 요청"""
        prompt = f"""카테고리 "{parent}"가 두 그룹으로 나뉘었습니다.
그룹 A: {len(members_a)}개 항목
그룹 B: {len(members_b)}개 항목

각 그룹에 적합한 카테고리 이름을 제안하세요.
형식: 이름A, 이름B (영어 snake_case, 각 2-3단어)
이름만 출력하세요."""

        try:
            response = self._llm._client.chat.completions.create(
                model=self._llm._model,
                messages=[
                    {"role": "system", "content": "카테고리 이름 두 개를 쉼표로 구분하여 답하세요."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=50,
            )
            raw = response.choices[0].message.content.strip()
            parts = [p.strip().lower().replace(" ", "_").replace('"', "") for p in raw.split(",")]
            if len(parts) >= 2:
                return parts[0], parts[1]
        except Exception:
            pass
        # fallback
        return f"{parent}_group_a", f"{parent}_group_b"

    async def _propose_merge_name(self, cat_a: str, cat_b: str) -> str:
        """LLM에게 병합 후 이름을 요청"""
        prompt = f"""카테고리 "{cat_a}"와 "{cat_b}"를 하나로 합칩니다.
합쳐진 카테고리의 이름을 제안하세요.
영어 snake_case, 2-3단어. 이름만 출력하세요."""

        try:
            response = self._llm._client.chat.completions.create(
                model=self._llm._model,
                messages=[
                    {"role": "system", "content": "카테고리 이름 하나만 답하세요."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=30,
            )
            raw = response.choices[0].message.content.strip().lower()
            return raw.replace(" ", "_").replace('"', "").replace("'", "")
        except Exception:
            return f"{cat_a}_{cat_b}"

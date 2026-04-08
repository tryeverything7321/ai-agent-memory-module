"""Taxonomy Bootstrap — 초기 k-means 클러스터링 + LLM 네이밍 + EPHEMERAL 규칙 생성

콜드스타트 시퀀스:
  1. 첫 BUFFER_SIZE(30)개 메시지를 버퍼링
  2. k-means (k=auto, 3~7, silhouette score) 클러스터링
  3. LLM에게 각 클러스터 대표 텍스트 기반 이름 요청
  4. LLM에게 EPHEMERAL 패턴 30개 생성 요청
  5. TaxonomyGraph + Lineage 초기화
"""

from __future__ import annotations

import json
from typing import Optional

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from taxonomy.taxonomy_graph import TaxonomyGraph
from taxonomy.lineage import PhylogeneticLineage

# --- JSON 파싱 유틸 ---

import re


def _extract_json_array(raw: str, prefix_items: list[str] | None = None) -> list[str] | None:
    """LLM 출력에서 JSON 배열을 추출한다.

    LLM이 JSON만 출력하지 않고 설명을 덧붙이는 경우를 처리:
      1. 전체 문자열을 JSON으로 파싱 시도
      2. 실패 시 [...] 패턴을 찾아 파싱
      3. prefix_items가 있으면 LLM의 continuation 출력을 prefix와 합침
    """
    if not raw:
        return None

    # prefix continuation 모드: LLM이 "] 전까지만 출력한 경우
    if prefix_items:
        # LLM 출력이 continuation이면 prefix + continuation을 합침
        combined = '["' + '", "'.join(prefix_items) + '", ' + raw.lstrip(", ")
        # ] 보정: 닫는 괄호가 없으면 추가
        if "]" not in combined:
            combined += "]"
        try:
            result = json.loads(combined)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # 방법 1: 전체 파싱
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # 방법 2: [...] 패턴 추출
    match = re.search(r'\[.*?\]', raw, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    return None


# --- 상수 ---
BUFFER_SIZE = 30
K_MIN = 3
K_MAX = 7
DEFAULT_EPHEMERAL_PATTERNS = [
    "ㅋ", "ㅎ", "ㅇㅋ", "오키", "넵", "네네", "ㄴㄴ", "점심", "ㅇㅇ",
]


class TaxonomyBootstrap:
    """콜드스타트 시 버퍼링 → k-means → LLM 네이밍 → EPHEMERAL 규칙 생성

    사용 흐름:
        bootstrap = TaxonomyBootstrap(llm_client)
        bootstrap.add_message(text, embedding)  # 30번 반복
        if bootstrap.is_ready():
            taxonomy, lineage, patterns = await bootstrap.execute()
    """

    def __init__(self, llm_client):
        self._llm = llm_client
        self._buffer: list[dict] = []  # {"text": str, "embedding": list[float]}
        self._executed = False

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

    @property
    def is_executed(self) -> bool:
        return self._executed

    def add_message(self, text: str, embedding: list[float]) -> None:
        """메시지를 버퍼에 추가한다. BUFFER_SIZE 도달 전까지만."""
        if self._executed:
            raise RuntimeError("이미 bootstrap이 실행되었습니다")
        if len(self._buffer) < BUFFER_SIZE:
            self._buffer.append({"text": text, "embedding": embedding})

    def is_ready(self) -> bool:
        """버퍼가 BUFFER_SIZE에 도달했고, 아직 실행되지 않았는지 확인"""
        return len(self._buffer) >= BUFFER_SIZE and not self._executed

    async def execute(
        self,
    ) -> tuple[TaxonomyGraph, PhylogeneticLineage, list[str]]:
        """버퍼된 메시지로 초기 택소노미를 생성한다.

        Returns:
            (taxonomy, lineage, ephemeral_patterns)
        """
        if self._executed:
            raise RuntimeError("이미 bootstrap이 실행되었습니다")
        if len(self._buffer) < BUFFER_SIZE:
            raise RuntimeError(
                f"버퍼 부족: {len(self._buffer)}/{BUFFER_SIZE}"
            )

        # --- 1. k-means 클러스터링 (k 자동 결정) ---
        embeddings = np.array([m["embedding"] for m in self._buffer])
        texts = [m["text"] for m in self._buffer]

        best_k, labels, centroids = self._find_optimal_k(embeddings)

        # --- 2. 클러스터별 대표 텍스트 추출 ---
        cluster_texts = self._get_cluster_representative_texts(
            texts, labels, best_k
        )

        # --- 3. LLM에게 카테고리 이름 요청 ---
        category_names = await self._name_clusters(cluster_texts, best_k)

        # --- 4. TaxonomyGraph 초기화 ---
        taxonomy = TaxonomyGraph()
        lineage = PhylogeneticLineage()

        for k_idx in range(best_k):
            name = category_names[k_idx]
            centroid = centroids[k_idx].tolist()
            member_count = int(np.sum(labels == k_idx))
            taxonomy.add_category(name, centroid, created_by="bootstrap")
            lineage.record_bootstrap(name, member_count)

        # 멤버 등록
        for i, label in enumerate(labels):
            cat_name = category_names[label]
            taxonomy.add_member(cat_name, f"bootstrap_{i}")
            taxonomy.activate_category(cat_name, self._buffer[i]["embedding"])

        # --- 5. EPHEMERAL 패턴 LLM 생성 ---
        ephemeral_patterns = await self._generate_ephemeral_patterns()

        self._executed = True
        return taxonomy, lineage, ephemeral_patterns

    def _find_optimal_k(
        self, embeddings: np.ndarray
    ) -> tuple[int, np.ndarray, np.ndarray]:
        """silhouette score 기반으로 최적 k를 결정한다.

        Args:
            embeddings: (N, D) 임베딩 행렬

        Returns:
            (best_k, labels, centroids)
        """
        n_samples = len(embeddings)

        # 샘플이 적으면 k 범위 조정
        actual_k_max = min(K_MAX, n_samples - 1)
        actual_k_min = min(K_MIN, actual_k_max)

        if actual_k_min < 2:
            # 최소 2-클러스터라도 필요
            actual_k_min = 2

        best_k = actual_k_min
        best_score = -1.0
        best_labels = None
        best_centroids = None

        for k in range(actual_k_min, actual_k_max + 1):
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(embeddings)

            # silhouette score: -1 ~ 1, 높을수록 좋음
            score = silhouette_score(embeddings, labels)

            if score > best_score:
                best_score = score
                best_k = k
                best_labels = labels
                best_centroids = kmeans.cluster_centers_

        return best_k, best_labels, best_centroids

    def _get_cluster_representative_texts(
        self, texts: list[str], labels: np.ndarray, k: int
    ) -> dict[int, list[str]]:
        """각 클러스터의 대표 텍스트(최대 5개)를 추출한다."""
        cluster_texts: dict[int, list[str]] = {}
        for k_idx in range(k):
            members = [
                texts[i] for i, l in enumerate(labels) if l == k_idx
            ]
            # 최대 5개 샘플
            cluster_texts[k_idx] = members[:5]
        return cluster_texts

    async def _name_clusters(
        self, cluster_texts: dict[int, list[str]], k: int
    ) -> list[str]:
        """LLM에게 각 클러스터의 카테고리 이름을 요청한다.

        Returns:
            길이 k의 카테고리 이름 리스트
        """
        # 클러스터별 샘플 텍스트를 프롬프트로 구성
        clusters_desc = []
        for k_idx in range(k):
            samples = cluster_texts.get(k_idx, [])
            sample_str = " | ".join(s[:80] for s in samples)
            clusters_desc.append(f"클러스터 {k_idx+1}: [{sample_str}]")

        cluster_list = "\n".join(clusters_desc)

        prompt = f"""다음 {k}개의 메시지 그룹에 각각 카테고리 이름을 붙여주세요.

{cluster_list}

규칙:
1. 각 카테고리 이름은 영어 snake_case, 2-3단어
2. 서로 겹치지 않는 MECE 이름
3. JSON 배열로만 출력: ["name1", "name2", ...]
4. 다른 텍스트 없이 JSON만 출력"""

        try:
            response = self._llm._client.chat.completions.create(
                model=self._llm._model,
                messages=[
                    {
                        "role": "system",
                        "content": "JSON 배열만 답하세요. 다른 텍스트 없이.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            raw = response.choices[0].message.content.strip()
            names = _extract_json_array(raw)
            if names and len(names) >= k:
                cleaned = [
                    str(n).strip().lower().replace(" ", "_").replace('"', "")
                    for n in names[:k]
                ]
                return cleaned
        except Exception:
            pass

        # fallback: 기본 이름
        return [f"category_{i+1}" for i in range(k)]

    async def _generate_ephemeral_patterns(self) -> list[str]:
        """LLM에게 EPHEMERAL(단기 기억) 판별 패턴 30개를 생성 요청한다.

        Returns:
            30개의 패턴 문자열 리스트
        """
        # few-shot 예시를 포함한 구조화된 프롬프트 (JSON 출력 안정화)
        prompt = """업무 채팅에서 "기억할 필요 없는 짧은 반응"을 판별하는 한국어 패턴 30개를 JSON 배열로 출력하세요.

예시 출력:
["ㅋㅋ", "ㅎㅎ", "오키", "넵", "ㅇㅇ", "ㄴㄴ", "네네", "ㄱㄱ", "ㅇㅋ", "점심"]

포함 기준:
- 자모 반복: ㅋㅋㅋ, ㅎㅎㅎ, ㄷㄷ
- 축약 응대: 넵, 네네, 오키, 고고, 감사
- 단답 감탄: 와, 헐, 대박, 진짜
- 일상 잡담: 점심, 퇴근, 수고

위 예시 10개에 추가로 20개를 더 만들어 총 30개 배열을 출력하세요.
["ㅋㅋ", "ㅎㅎ", "오키", "넵", "ㅇㅇ", "ㄴㄴ", "네네", "ㄱㄱ", "ㅇㅋ", "점심","""

        try:
            response = self._llm._client.chat.completions.create(
                model=self._llm._model,
                messages=[
                    {
                        "role": "system",
                        "content": 'Continue the JSON array. Output ONLY the remaining items and closing bracket "]".',
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=400,
            )
            raw = response.choices[0].message.content.strip()
            patterns = _extract_json_array(raw, prefix_items=[
                "ㅋㅋ", "ㅎㅎ", "오키", "넵", "ㅇㅇ", "ㄴㄴ", "네네", "ㄱㄱ", "ㅇㅋ", "점심",
            ])
            if patterns and len(patterns) >= 15:
                return [str(p).strip() for p in patterns[:30]]
        except Exception:
            pass

        # fallback: 기본 패턴
        return list(DEFAULT_EPHEMERAL_PATTERNS)

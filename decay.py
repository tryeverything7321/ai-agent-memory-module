"""Decay Engine — Mnemosyne 스타일 Ebbinghaus 망각 곡선

수식: w(t) = e^(-λt) * (1 + boost * access_count)
  - 곱셈형: boost가 있어도 시간이 지나면 모든 메모리는 결국 감쇠
  - λ: 감쇠율 (ephemeral=0.3, important=0.05, critical=0.005)
  - boost: 반복 접근 시 가중치 부스트 (기본 0.05)

통합 모듈: calculator + booster + pruner + updater
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from config import settings
from models import Memory, Importance


class DecayEngine:
    """메모리 감쇠 계산, 프루닝, 팩트 갱신"""

    def __init__(self, boost_factor: float = None):
        self._boost = boost_factor or settings.decay_boost_factor

    def calculate_weight(
        self,
        lambda_val: float,
        days_elapsed: float,
        access_count: int = 0,
        boost_factor: float = None,
    ) -> float:
        """
        w(t) = e^(-λt) * (1 + boost * access_count)

        Args:
            lambda_val: 감쇠율 (0 < λ ≤ 1)
            days_elapsed: 생성 이후 경과 일수
            access_count: 접근 횟수
            boost_factor: 커스텀 boost (기본: config.decay_boost_factor)
        """
        if lambda_val < 0 or lambda_val > 1:
            raise ValueError(f"λ must be in [0, 1], got {lambda_val}")

        boost = boost_factor or self._boost
        base_decay = math.exp(-lambda_val * days_elapsed)
        boosted = base_decay * (1 + boost * access_count)
        return boosted

    def get_lambda_for_importance(self, importance: Importance) -> float:
        """중요도별 λ 값 반환"""
        return {
            Importance.ephemeral: settings.decay_lambda_ephemeral,
            Importance.important: settings.decay_lambda_important,
            Importance.critical: settings.decay_lambda_critical,
        }[importance]

    def compute_memory_weight(self, memory: Memory) -> float:
        """Memory 객체의 현재 decay weight 계산"""
        now = datetime.now()
        days_elapsed = (now - memory.created_at).total_seconds() / 86400
        return self.calculate_weight(
            lambda_val=memory.decay_lambda,
            days_elapsed=days_elapsed,
            access_count=memory.access_count,
        )

    # --- 프루닝 ---

    async def prune(
        self, metadata_store, threshold: float = None
    ) -> int:
        """임계치 미달 메모리 일괄 삭제"""
        threshold = threshold or settings.decay_prune_threshold
        return await metadata_store.delete_memories_below_threshold(threshold)

    # --- 팩트 갱신 ---

    async def update_fact(
        self, metadata_store, old_memory_id: str, new_content: str, user_id: str
    ) -> Memory:
        """기존 팩트 무효화 + 새 팩트 생성"""
        await metadata_store.invalidate_memory(old_memory_id)

        new_memory = Memory(
            user_id=user_id,
            content=new_content,
            importance=Importance.critical,
            decay_lambda=settings.decay_lambda_critical,
        )
        await metadata_store.save_memory(new_memory)
        return new_memory

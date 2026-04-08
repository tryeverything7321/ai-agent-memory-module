"""장기 시뮬레이션 데이터 생성 — 500+ turns, Mitosis/Extinction 유도

시나리오 설계:
  Phase 1 (Day 1-7):   4유저 일상 업무 — bootstrap 카테고리 형성 (60 turns)
  Phase 2 (Day 8-21):  안정기 — 기존 카테고리 강화 (120 turns)
  Phase 3 (Day 22-35): 전환기 — 온보딩/출장 카테고리 사용 중단 → Extinction 유도
                       + 기술토론 카테고리에 다양한 주제 유입 → Mitosis 유도 (150 turns)
  Phase 4 (Day 36-56): 새 프로젝트 — 완전히 새로운 카테고리 출현 (180 turns)

Mitosis 유도 전략:
  - "기술토론" 카테고리에 DB, Frontend, DevOps, ML 등 이질적 주제를 집중 투입
  - 이질적 임베딩이 모이면 intra-cluster variance > 0.5 → 분열

Extinction 유도 전략:
  - Phase 1-2에서 온보딩/출장 카테고리 활성화
  - Phase 3-4에서 완전히 사용 중단 → decay weight 자연 감소 → prune
"""

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import ConversationTurn, ConversationSession

# --- 메시지 풀 (카테고리별) ---

SCHEDULING = [
    "내일 오전 회의 일정 잡아줘",
    "다음 주 수요일 2시에 팀 미팅 가능한지 확인해줘",
    "금요일 오후 3시에 고객사 미팅 있어",
    "스프린트 플래닝 일정 조정해야 해",
    "이번 주 스탠드업 시간 변경됨, 10시로",
    "연차 신청 했는데 승인 됐나?",
    "출장 일정 확인 좀 해줘",
    "내일 재택근무 하겠습니다",
    "다음 달 프로젝트 마일스톤 일정 정리해줘",
    "팀 워크숍 날짜 투표 결과 알려줘",
]

ISSUE_TRACKING = [
    "JIRA-1234 이슈 상태 업데이트해줘",
    "이번 스프린트 미해결 이슈 몇 개야?",
    "프로덕션 버그 리포트 들어왔어",
    "핫픽스 배포 후 이슈 클로즈 해줘",
    "QA에서 발견된 버그 3건 트래킹 시작",
    "이슈 우선순위 재조정 필요해",
    "블로커 이슈 해결 상황 공유해줘",
    "고객 피드백 기반 이슈 생성해야 해",
    "스프린트 번다운 차트 확인해줘",
    "릴리스 노트에 포함할 이슈 목록 정리해줘",
]

CODE_REVIEW = [
    "PR #456 리뷰해줄 수 있어?",
    "이 코드 리팩토링 방향 어때?",
    "머지 컨플릭트 해결 방법 알려줘",
    "코드 컨벤션 가이드 어디 있어?",
    "유닛 테스트 커버리지 80% 넘겼어",
    "PR 코멘트 반영 완료했습니다",
    "린트 에러 수정하고 다시 올렸어",
    "CI 파이프라인 통과 확인해줘",
    "이 함수 네이밍 뭐가 좋을까?",
    "디자인 패턴 적용 리뷰 요청합니다",
]

# --- Mitosis 유도용: 이질적인 기술 주제들 ---

TECH_DB = [
    "PostgreSQL 인덱스 최적화 방법 알려줘",
    "Redis 캐시 만료 전략 어떤 게 좋을까?",
    "MongoDB 샤딩 전략 결정해야 해",
    "DB 마이그레이션 스크립트 작성 중이야",
    "쿼리 실행 계획 분석해봤는데 풀스캔 나와",
    "커넥션 풀 설정값 뭐가 적당해?",
    "트랜잭션 격리 수준 변경 검토 중",
    "슬로우 쿼리 로그 분석 결과 공유",
    "파티셔닝 적용 후 성능 개선 수치 확인",
    "ORM N+1 문제 해결 방법",
]

TECH_FRONTEND = [
    "React 컴포넌트 렌더링 최적화해야 해",
    "Tailwind CSS 커스텀 테마 설정 방법",
    "Next.js SSR vs SSG 어떤 걸 쓸까?",
    "웹 접근성 WCAG 2.1 AA 기준 맞춰야 해",
    "Storybook 컴포넌트 문서화 진행 상황",
    "반응형 레이아웃 브레이크포인트 확인",
    "크로스 브라우저 호환성 이슈 있어",
    "번들 사이즈 줄이는 방법 찾아봐",
    "E2E 테스트 Playwright로 전환 검토 중",
    "디자인 시스템 피그마 연동 방법",
]

TECH_DEVOPS = [
    "k8s 클러스터 HPA 설정 변경해야 해",
    "Docker 이미지 빌드 시간 단축 방법",
    "CI/CD 파이프라인 stages 최적화 필요",
    "Terraform 모듈 리팩토링 계획 있어?",
    "모니터링 대시보드 Grafana 알럿 설정",
    "로그 수집 ELK 스택에서 Loki로 전환",
    "블루그린 배포 vs 카나리 배포 결정",
    "시크릿 매니저 HashiCorp Vault 도입",
    "서비스 메시 Istio 적용 검토",
    "인프라 비용 최적화 리포트 작성 중",
]

TECH_ML = [
    "학습 데이터 전처리 파이프라인 구축",
    "모델 A/B 테스트 설계 방법",
    "GPU 서버 리소스 할당 요청",
    "MLflow로 실험 추적 설정",
    "피처 엔지니어링 자동화 검토",
    "추론 레이턴시 최적화 TensorRT 적용",
    "데이터 라벨링 품질 관리 방안",
    "모델 성능 메트릭 비교 결과 공유",
    "배치 추론 스케줄링 설정",
    "벡터 DB 임베딩 인덱싱 벤치마크",
]

# --- Extinction 유도용 ---

ONBOARDING = [
    "신입 온보딩 체크리스트 확인해줘",
    "개발환경 세팅 가이드 어디 있어?",
    "팀 위키 접근 권한 요청했어",
    "멘토링 미팅 일정 잡아줘",
    "사내 시스템 계정 발급 요청",
    "코드 리포지토리 접근 권한 필요해",
    "팀 소개 문서 읽었습니다",
    "개발 컨벤션 가이드 숙지 완료",
]

TRAVEL = [
    "출장 비용 정산 서류 제출",
    "해외 출장 비자 발급 상황",
    "출장지 미팅 자료 준비",
    "호텔 예약 확인해줘",
    "출장 복귀 후 보고서 작성",
]

DATA_ANALYSIS = [
    "주간 매출 데이터 분석 결과 공유",
    "사용자 행동 퍼널 분석해줘",
    "A/B 테스트 통계적 유의성 검증",
    "SQL 쿼리 최적화 도움 필요",
    "Pandas 데이터프레임 피벗 방법",
    "시각화 차트 어떤 타입이 좋을까?",
    "이상치 탐지 알고리즘 적용 결과",
    "코호트 분석 리포트 작성 중",
    "대시보드 KPI 지표 정의 변경",
    "데이터 파이프라인 Airflow DAG 수정",
]

DOCUMENT = [
    "API 문서 업데이트해야 해",
    "기술 명세서 초안 작성 완료",
    "주간 보고서 작성 도와줘",
    "회의록 정리해서 공유해줘",
    "프로젝트 제안서 검토 요청",
    "릴리스 가이드 문서화 진행 중",
]

# --- 새 프로젝트 카테고리 (Phase 4) ---

SECURITY = [
    "보안 취약점 스캔 결과 리뷰",
    "OWASP Top 10 대응 현황 점검",
    "인증/인가 체계 개선 방안",
    "SSL 인증서 갱신 일정 확인",
    "침투 테스트 결과 보고서",
    "보안 교육 이수 현황 확인",
    "접근 로그 감사 결과 공유",
    "데이터 암호화 정책 업데이트",
]

EPHEMERAL = [
    "ㅋㅋ", "ㅎㅎ", "넵", "오키", "ㅇㅇ", "감사", "고고", "ㄱㄱ",
    "네네", "점심 뭐 먹지?", "수고하셨습니다", "확인했어요",
]


def _turn(role, content, ts, intent=None):
    return ConversationTurn(role=role, content=content, timestamp=ts, intent=intent)


def _session(uid, ts, turns):
    s = ConversationSession(user_id=uid, created_at=ts)
    s.turns = turns
    return s


def _pick(pool, n=1, rng=None):
    """pool에서 n개 메시지를 랜덤 선택 (중복 허용)"""
    r = rng or random
    return [r.choice(pool) for _ in range(n)]


def generate_long_simulation() -> dict:
    """500+ turns 장기 시뮬레이션 데이터 생성"""
    rng = random.Random(42)
    base = datetime(2026, 4, 1, 9, 0)
    sessions = []
    users = ["user_pm", "user_dev", "user_new", "user_analyst"]

    # --- Phase 1: Day 1-7, 일상 업무 (60 turns) ---
    for day in range(7):
        for uid in users:
            ts = base + timedelta(days=day, hours=9 + rng.randint(0, 2))
            turns = []

            if uid == "user_pm":
                msgs = _pick(SCHEDULING, 2, rng) + _pick(ISSUE_TRACKING, 1, rng)
                intents = ["scheduling", "scheduling", "issue_tracking"]
            elif uid == "user_dev":
                msgs = _pick(CODE_REVIEW, 1, rng) + _pick(TECH_DB[:3], 1, rng)
                intents = ["code_review", "knowledge_lookup"]
            elif uid == "user_new":
                msgs = _pick(ONBOARDING, 2, rng)
                intents = ["onboarding", "onboarding"]
            else:  # analyst
                msgs = _pick(DATA_ANALYSIS, 1, rng) + _pick(DOCUMENT, 1, rng)
                intents = ["data_analysis", "document_drafting"]

            # ephemeral 삽입 (~15%)
            if rng.random() < 0.15:
                msgs.append(rng.choice(EPHEMERAL))
                intents.append(None)

            for i, (msg, intent) in enumerate(zip(msgs, intents)):
                t = ts + timedelta(minutes=i * 5)
                turns.append(_turn("user", msg, t, intent=intent))
                turns.append(_turn("assistant", f"[응답] {msg[:20]}...", t + timedelta(seconds=30)))

            sessions.append(_session(uid, ts, turns))

    # --- Phase 2: Day 8-21, 안정기 + 출장 카테고리 활성화 (120 turns) ---
    for day in range(7, 21):
        for uid in users:
            ts = base + timedelta(days=day, hours=9 + rng.randint(0, 3))
            turns = []

            if uid == "user_pm":
                # PM은 출장 카테고리도 사용 (Day 10-14)
                if 10 <= day <= 14:
                    msgs = _pick(TRAVEL, 2, rng) + _pick(SCHEDULING, 1, rng)
                    intents = ["scheduling", "scheduling", "scheduling"]
                else:
                    msgs = _pick(SCHEDULING, 1, rng) + _pick(ISSUE_TRACKING, 1, rng) + _pick(DOCUMENT, 1, rng)
                    intents = ["scheduling", "issue_tracking", "document_drafting"]
            elif uid == "user_dev":
                msgs = _pick(CODE_REVIEW, 1, rng) + _pick(TECH_DB[:5], 1, rng) + _pick(ISSUE_TRACKING, 1, rng)
                intents = ["code_review", "knowledge_lookup", "issue_tracking"]
            elif uid == "user_new":
                # 신입은 온보딩 중 (Day 8-14까지)
                if day <= 14:
                    msgs = _pick(ONBOARDING, 1, rng) + _pick(CODE_REVIEW, 1, rng)
                    intents = ["onboarding", "code_review"]
                else:
                    msgs = _pick(CODE_REVIEW, 2, rng)
                    intents = ["code_review", "code_review"]
            else:
                msgs = _pick(DATA_ANALYSIS, 2, rng)
                intents = ["data_analysis", "data_analysis"]

            if rng.random() < 0.15:
                msgs.append(rng.choice(EPHEMERAL))
                intents.append(None)

            for i, (msg, intent) in enumerate(zip(msgs, intents)):
                t = ts + timedelta(minutes=i * 5)
                turns.append(_turn("user", msg, t, intent=intent))
                turns.append(_turn("assistant", f"[응답] {msg[:20]}...", t + timedelta(seconds=30)))

            sessions.append(_session(uid, ts, turns))

    # --- Phase 3: Day 22-35, 전환기 — Extinction + Mitosis 유도 (150 turns) ---
    for day in range(21, 35):
        for uid in users:
            ts = base + timedelta(days=day, hours=9 + rng.randint(0, 3))
            turns = []

            if uid == "user_pm":
                # 출장 완전 종료, 이슈트래킹 집중
                msgs = _pick(ISSUE_TRACKING, 2, rng) + _pick(SCHEDULING, 1, rng)
                intents = ["issue_tracking", "issue_tracking", "scheduling"]
            elif uid == "user_dev":
                # Mitosis 유도: 이질적 기술 주제 집중 투입
                pool = TECH_DB + TECH_FRONTEND + TECH_DEVOPS + TECH_ML
                msgs = _pick(pool, 3, rng)
                intents = ["knowledge_lookup"] * 3
            elif uid == "user_new":
                # 온보딩 완전 종료 → 실전 코드 리뷰 + 기술 토론
                msgs = _pick(CODE_REVIEW, 1, rng) + _pick(TECH_FRONTEND, 1, rng) + _pick(TECH_DEVOPS, 1, rng)
                intents = ["code_review", "knowledge_lookup", "knowledge_lookup"]
            else:
                msgs = _pick(DATA_ANALYSIS, 1, rng) + _pick(TECH_ML, 1, rng) + _pick(DOCUMENT, 1, rng)
                intents = ["data_analysis", "knowledge_lookup", "document_drafting"]

            if rng.random() < 0.1:
                msgs.append(rng.choice(EPHEMERAL))
                intents.append(None)

            for i, (msg, intent) in enumerate(zip(msgs, intents)):
                t = ts + timedelta(minutes=i * 5)
                turns.append(_turn("user", msg, t, intent=intent))
                turns.append(_turn("assistant", f"[응답] {msg[:20]}...", t + timedelta(seconds=30)))

            sessions.append(_session(uid, ts, turns))

    # --- Phase 4: Day 36-56, 새 프로젝트 — 보안 카테고리 출현 (180 turns) ---
    for day in range(35, 56):
        for uid in users:
            ts = base + timedelta(days=day, hours=9 + rng.randint(0, 3))
            turns = []

            if uid == "user_pm":
                msgs = _pick(ISSUE_TRACKING, 1, rng) + _pick(SECURITY, 1, rng) + _pick(SCHEDULING, 1, rng)
                intents = ["issue_tracking", "troubleshooting", "scheduling"]
            elif uid == "user_dev":
                # 다양한 기술 주제 지속 (Mitosis 강화)
                pool_a = TECH_DB + TECH_FRONTEND
                pool_b = TECH_DEVOPS + TECH_ML
                msgs = _pick(pool_a, 1, rng) + _pick(pool_b, 1, rng) + _pick(SECURITY, 1, rng)
                intents = ["knowledge_lookup", "knowledge_lookup", "troubleshooting"]
            elif uid == "user_new":
                msgs = _pick(CODE_REVIEW, 1, rng) + _pick(TECH_DEVOPS, 1, rng) + _pick(SECURITY, 1, rng)
                intents = ["code_review", "knowledge_lookup", "troubleshooting"]
            else:
                msgs = _pick(DATA_ANALYSIS, 1, rng) + _pick(SECURITY, 1, rng)
                intents = ["data_analysis", "troubleshooting"]

            if rng.random() < 0.1:
                msgs.append(rng.choice(EPHEMERAL))
                intents.append(None)

            for i, (msg, intent) in enumerate(zip(msgs, intents)):
                t = ts + timedelta(minutes=i * 5)
                turns.append(_turn("user", msg, t, intent=intent))
                turns.append(_turn("assistant", f"[응답] {msg[:20]}...", t + timedelta(seconds=30)))

            sessions.append(_session(uid, ts, turns))

    # --- 직렬화 ---
    sessions_data = []
    total_user_turns = 0
    for s in sessions:
        turns_data = []
        for t in s.turns:
            td = {
                "role": t.role,
                "content": t.content,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            }
            if t.intent:
                td["intent"] = t.intent
            if t.role == "user":
                total_user_turns += 1
            turns_data.append(td)

        sessions_data.append({
            "session_id": s.session_id,
            "user_id": s.user_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "turns": turns_data,
        })

    output = {
        "metadata": {
            "description": "장기 시뮬레이션 데이터 — 500+ turns, Mitosis/Extinction 유도",
            "users": users,
            "total_sessions": len(sessions),
            "total_user_turns": total_user_turns,
            "duration_days": 56,
            "phases": {
                "phase1": "Day 1-7: 일상 업무 + 온보딩/출장 활성화",
                "phase2": "Day 8-21: 안정기",
                "phase3": "Day 22-35: 온보딩/출장 사용 중단 → Extinction 유도, 이질적 기술 주제 → Mitosis 유도",
                "phase4": "Day 36-56: 보안 카테고리 신규 출현",
            },
        },
        "sessions": sessions_data,
    }

    return output


def main():
    data = generate_long_simulation()
    out_path = Path(__file__).parent / "long_simulation.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"장기 시뮬레이션 데이터 생성 완료: {out_path}")
    print(f"  총 {data['metadata']['total_sessions']} sessions")
    print(f"  총 {data['metadata']['total_user_turns']} user turns")
    print(f"  기간: {data['metadata']['duration_days']}일 (4 phases)")


if __name__ == "__main__":
    main()

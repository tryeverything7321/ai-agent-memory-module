"""
합성 대화 데이터 생성기
- 3명의 가상 유저, 각 ~50턴, 2주치 시뮬레이션
- 반복 패턴(주간보고, 일일스탠드업 등) 포함 → Prediction Layer 콜드스타트 해결용

유저 프로파일:
  1. user_pm (프로젝트 매니저): 주간보고, 일정관리, 이슈추적
  2. user_dev (개발자): 코드리뷰, 트러블슈팅, 기술조사
  3. user_new (신입): 온보딩, 질문, 문서작성
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from models import ConversationTurn, ConversationSession, IntentCategory


def _t(base: datetime, day: int, hour: int, minute: int = 0) -> datetime:
    return base + timedelta(days=day, hours=hour, minutes=minute)


def generate_user_pm(base_date: datetime) -> list[ConversationSession]:
    """PM 유저: 주간보고(월), 일일스탠드업(매일), 일정관리, 이슈추적 패턴"""
    uid = "user_pm"
    sessions = []

    for week in range(2):
        week_offset = week * 7

        # --- 월요일: 주간 보고 패턴 (weekly_report → issue_tracking) ---
        s = ConversationSession(user_id=uid, created_at=_t(base_date, week_offset, 9))
        s.turns = [
            ConversationTurn(role="user", content="주간 보고서 작성해야 하는데",
                             timestamp=_t(base_date, week_offset, 9, 0), intent=IntentCategory.weekly_report),
            ConversationTurn(role="assistant", content="지난 주 주요 이슈를 정리해드릴까요?",
                             timestamp=_t(base_date, week_offset, 9, 1)),
            ConversationTurn(role="user", content="응 지난주 이슈 뭐 있었지?",
                             timestamp=_t(base_date, week_offset, 9, 2), intent=IntentCategory.issue_tracking),
            ConversationTurn(role="assistant", content="지난 주 이슈: 1) API 서버 레이턴시 문제 2) QA 커버리지 80% 달성 3) 신규 고객 온보딩 3건",
                             timestamp=_t(base_date, week_offset, 9, 3)),
            ConversationTurn(role="user", content="그리고 이번 주 일정 정리 좀 해줘",
                             timestamp=_t(base_date, week_offset, 9, 5), intent=IntentCategory.scheduling),
            ConversationTurn(role="assistant", content="이번 주 주요 일정: 화요일 디자인 리뷰, 수요일 스프린트 플래닝, 금요일 회고",
                             timestamp=_t(base_date, week_offset, 9, 6)),
        ]
        sessions.append(s)

        # --- 화요일: 일일 스탠드업 + 이슈 ---
        s = ConversationSession(user_id=uid, created_at=_t(base_date, week_offset + 1, 9))
        s.turns = [
            ConversationTurn(role="user", content="오늘 스탠드업 내용 정리해줘",
                             timestamp=_t(base_date, week_offset + 1, 9, 0), intent=IntentCategory.project_status),
            ConversationTurn(role="assistant", content="어제: API 레이턴시 핫픽스 배포. 오늘: 디자인 리뷰 미팅. 블로커: 없음",
                             timestamp=_t(base_date, week_offset + 1, 9, 1)),
            ConversationTurn(role="user", content="디자인 리뷰 미팅 자료 준비해야 하는데",
                             timestamp=_t(base_date, week_offset + 1, 10, 0), intent=IntentCategory.meeting_prep),
            ConversationTurn(role="assistant", content="지난 스프린트 디자인 변경사항과 사용자 피드백을 정리하겠습니다.",
                             timestamp=_t(base_date, week_offset + 1, 10, 1)),
        ]
        sessions.append(s)

        # --- 수요일: 스프린트 플래닝 ---
        s = ConversationSession(user_id=uid, created_at=_t(base_date, week_offset + 2, 14))
        s.turns = [
            ConversationTurn(role="user", content="이번 스프린트 백로그에서 우선순위 높은 거 뭐야?",
                             timestamp=_t(base_date, week_offset + 2, 14, 0), intent=IntentCategory.issue_tracking),
            ConversationTurn(role="assistant", content="P0: 결제 모듈 버그 수정, P1: 대시보드 리뉴얼, P2: 문서 업데이트",
                             timestamp=_t(base_date, week_offset + 2, 14, 1)),
            ConversationTurn(role="user", content="결제 모듈 버그 담당 누구지?",
                             timestamp=_t(base_date, week_offset + 2, 14, 3), intent=IntentCategory.team_communication),
            ConversationTurn(role="assistant", content="김개발님이 담당하고 있습니다. 목요일까지 핫픽스 예정입니다.",
                             timestamp=_t(base_date, week_offset + 2, 14, 4)),
        ]
        sessions.append(s)

        # --- 목요일: 일정 관리 ---
        s = ConversationSession(user_id=uid, created_at=_t(base_date, week_offset + 3, 11))
        s.turns = [
            ConversationTurn(role="user", content="다음 주 대만 출장 준비해야 해",
                             timestamp=_t(base_date, week_offset + 3, 11, 0), intent=IntentCategory.scheduling),
            ConversationTurn(role="assistant", content="출장 일정, 항공편, 숙소 예약 상태를 확인해드릴까요?",
                             timestamp=_t(base_date, week_offset + 3, 11, 1)),
            ConversationTurn(role="user", content="팀원들한테 출장 공유 메일 보내줘",
                             timestamp=_t(base_date, week_offset + 3, 11, 5), intent=IntentCategory.team_communication),
            ConversationTurn(role="assistant", content="출장 안내 메일 초안을 작성했습니다.",
                             timestamp=_t(base_date, week_offset + 3, 11, 6)),
        ]
        sessions.append(s)

        # --- 금요일: 회고 + 데이터 분석 ---
        s = ConversationSession(user_id=uid, created_at=_t(base_date, week_offset + 4, 16))
        s.turns = [
            ConversationTurn(role="user", content="이번 주 스프린트 벨로시티 데이터 보여줘",
                             timestamp=_t(base_date, week_offset + 4, 16, 0), intent=IntentCategory.data_analysis),
            ConversationTurn(role="assistant", content="이번 주 벨로시티: 완료 21pt / 계획 25pt (84%). 지난 주 대비 +3pt",
                             timestamp=_t(base_date, week_offset + 4, 16, 1)),
            ConversationTurn(role="user", content="회고 문서 작성해줘",
                             timestamp=_t(base_date, week_offset + 4, 16, 10), intent=IntentCategory.document_drafting),
            ConversationTurn(role="assistant", content="스프린트 회고 문서 초안을 작성하겠습니다.",
                             timestamp=_t(base_date, week_offset + 4, 16, 11)),
        ]
        sessions.append(s)

    return sessions  # 10 sessions, ~46 turns


def generate_user_dev(base_date: datetime) -> list[ConversationSession]:
    """개발자 유저: 코드리뷰, 트러블슈팅, 기술조사 패턴"""
    uid = "user_dev"
    sessions = []

    for week in range(2):
        wo = week * 7

        # --- 매일 아침: 코드리뷰 패턴 ---
        for day in range(5):
            s = ConversationSession(user_id=uid, created_at=_t(base_date, wo + day, 10))
            turns = [
                ConversationTurn(role="user", content="오늘 리뷰할 PR 있어?",
                                 timestamp=_t(base_date, wo + day, 10, 0), intent=IntentCategory.code_review),
                ConversationTurn(role="assistant",
                                 content=f"오늘 리뷰 대기 PR: #{100 + wo + day} 결제 모듈 리팩토링, #{101 + wo + day} 테스트 추가",
                                 timestamp=_t(base_date, wo + day, 10, 1)),
            ]

            # 월/수: 코드리뷰 → 트러블슈팅 패턴
            if day in (0, 2):
                turns.extend([
                    ConversationTurn(role="user", content="PR 리뷰하다가 이상한 버그 발견했어. 결제 API가 간헐적으로 500 에러 뱉어",
                                     timestamp=_t(base_date, wo + day, 11, 0), intent=IntentCategory.troubleshooting),
                    ConversationTurn(role="assistant",
                                     content="최근 결제 API 에러 로그를 확인해보겠습니다. DB 커넥션 풀 고갈 가능성이 있습니다.",
                                     timestamp=_t(base_date, wo + day, 11, 1)),
                ])

            # 화/목: 기술 조사
            if day in (1, 3):
                turns.extend([
                    ConversationTurn(role="user", content="Redis 캐시 만료 전략 어떤 게 좋을까?",
                                     timestamp=_t(base_date, wo + day, 14, 0), intent=IntentCategory.knowledge_lookup),
                    ConversationTurn(role="assistant",
                                     content="TTL 기반 vs LRU vs Write-through 세 가지 전략을 비교해드리겠습니다.",
                                     timestamp=_t(base_date, wo + day, 14, 1)),
                ])

            s.turns = turns
            sessions.append(s)

    return sessions  # 10 sessions, ~48 turns


def generate_user_new(base_date: datetime) -> list[ConversationSession]:
    """신입 유저: 온보딩, 질문, 문서 작성 패턴"""
    uid = "user_new"
    sessions = []

    for week in range(2):
        wo = week * 7

        # --- 1주차: 온보딩 집중 ---
        if week == 0:
            # 월: 첫 출근
            s = ConversationSession(user_id=uid, created_at=_t(base_date, wo, 9))
            s.turns = [
                ConversationTurn(role="user", content="안녕하세요 오늘 첫 출근인데 뭐부터 하면 될까요?",
                                 timestamp=_t(base_date, wo, 9, 0), intent=IntentCategory.onboarding),
                ConversationTurn(role="assistant", content="환영합니다! 먼저 개발 환경 설정부터 시작하시면 됩니다.",
                                 timestamp=_t(base_date, wo, 9, 1)),
                ConversationTurn(role="user", content="개발 환경 설정 문서 어디 있어요?",
                                 timestamp=_t(base_date, wo, 9, 5), intent=IntentCategory.knowledge_lookup),
                ConversationTurn(role="assistant", content="Confluence의 'Developer Onboarding' 페이지에 있습니다.",
                                 timestamp=_t(base_date, wo, 9, 6)),
                ConversationTurn(role="user", content="점심 뭐 먹을까요",
                                 timestamp=_t(base_date, wo, 12, 0), intent=None),  # ephemeral
                ConversationTurn(role="assistant", content="근처에 맛있는 파스타집이 있어요!",
                                 timestamp=_t(base_date, wo, 12, 1)),
            ]
            sessions.append(s)

            # 화~목: 온보딩 + 질문
            for day in range(1, 4):
                s = ConversationSession(user_id=uid, created_at=_t(base_date, wo + day, 10))
                s.turns = [
                    ConversationTurn(role="user", content="우리 팀 코드 컨벤션이 어떻게 돼요?",
                                     timestamp=_t(base_date, wo + day, 10, 0), intent=IntentCategory.knowledge_lookup),
                    ConversationTurn(role="assistant", content="ESLint + Prettier 조합을 사용합니다. .eslintrc 파일을 참고하세요.",
                                     timestamp=_t(base_date, wo + day, 10, 1)),
                    ConversationTurn(role="user", content="첫 PR 올려도 될까요?",
                                     timestamp=_t(base_date, wo + day, 15, 0), intent=IntentCategory.code_review),
                    ConversationTurn(role="assistant", content="네! 리뷰어로 김개발님을 지정해주세요.",
                                     timestamp=_t(base_date, wo + day, 15, 1)),
                ]
                sessions.append(s)

            # 금: 주간 문서 작성
            s = ConversationSession(user_id=uid, created_at=_t(base_date, wo + 4, 16))
            s.turns = [
                ConversationTurn(role="user", content="이번 주 온보딩 학습 내용 정리해서 문서로 만들어야 해요",
                                 timestamp=_t(base_date, wo + 4, 16, 0), intent=IntentCategory.document_drafting),
                ConversationTurn(role="assistant", content="이번 주 배운 내용을 카테고리별로 정리해드리겠습니다.",
                                 timestamp=_t(base_date, wo + 4, 16, 1)),
            ]
            sessions.append(s)

        # --- 2주차: 실전 투입 ---
        else:
            for day in range(5):
                s = ConversationSession(user_id=uid, created_at=_t(base_date, wo + day, 10))
                turns = [
                    ConversationTurn(role="user", content="오늘 할 일 정리해줘",
                                     timestamp=_t(base_date, wo + day, 10, 0), intent=IntentCategory.project_status),
                    ConversationTurn(role="assistant", content="오늘 할 일: 1) 결제 모듈 테스트 작성 2) PR 리뷰 반영",
                                     timestamp=_t(base_date, wo + day, 10, 1)),
                ]

                if day % 2 == 0:
                    turns.extend([
                        ConversationTurn(role="user", content="테스트 작성하다가 모르는 게 있는데 pytest fixture 어떻게 써요?",
                                         timestamp=_t(base_date, wo + day, 14, 0), intent=IntentCategory.knowledge_lookup),
                        ConversationTurn(role="assistant", content="conftest.py에 공통 fixture를 정의하면 됩니다.",
                                         timestamp=_t(base_date, wo + day, 14, 1)),
                    ])
                else:
                    turns.extend([
                        ConversationTurn(role="user", content="코드 리뷰 피드백 반영했는데 확인해주세요",
                                         timestamp=_t(base_date, wo + day, 15, 0), intent=IntentCategory.code_review),
                        ConversationTurn(role="assistant", content="변경사항 확인했습니다. LGTM!",
                                         timestamp=_t(base_date, wo + day, 15, 1)),
                    ])

                s.turns = turns
                sessions.append(s)

    return sessions  # 10 sessions, ~40 turns


def generate_all() -> dict:
    """전체 합성 데이터 생성"""
    base_date = datetime(2026, 3, 23, 0, 0, 0)  # 월요일 시작

    pm_sessions = generate_user_pm(base_date)
    dev_sessions = generate_user_dev(base_date)
    new_sessions = generate_user_new(base_date)

    all_sessions = pm_sessions + dev_sessions + new_sessions

    # 통계
    total_turns = sum(len(s.turns) for s in all_sessions)
    intent_counts: dict[str, int] = {}
    for s in all_sessions:
        for t in s.turns:
            if t.intent:
                key = t.intent.value
                intent_counts[key] = intent_counts.get(key, 0) + 1

    data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "base_date": base_date.isoformat(),
            "duration_days": 14,
            "users": ["user_pm", "user_dev", "user_new"],
            "total_sessions": len(all_sessions),
            "total_turns": total_turns,
            "intent_distribution": dict(sorted(intent_counts.items(), key=lambda x: -x[1])),
        },
        "sessions": [s.model_dump(mode="json") for s in all_sessions],
    }

    return data


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    data = generate_all()

    output_path = Path(__file__).parent / "synthetic_conversations.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    meta = data["metadata"]
    print(f"생성 완료!")
    print(f"  세션: {meta['total_sessions']}개")
    print(f"  턴: {meta['total_turns']}개")
    print(f"  유저: {', '.join(meta['users'])}")
    print(f"  Intent 분포:")
    for intent, count in meta["intent_distribution"].items():
        print(f"    {intent}: {count}")
    print(f"\n저장: {output_path}")

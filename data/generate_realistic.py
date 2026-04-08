"""
리얼리스틱 대화 데이터 생성기
- 4명의 가상 유저, 4주(28일), ~200 user turns, ~50-60 sessions
- 카테고리 소멸(onboarding, 출장), 카테고리 발견(CI/CD, 대시보드) 시나리오 포함
- ephemeral 메시지 ~15% 삽입

유저 프로파일:
  1. user_pm (김과장, PM): 주간보고, 이슈트래킹, 일정조율, 출장(2-3주만)
  2. user_dev (이대리, Backend Dev): PR리뷰, 트러블슈팅, 기술질문, CI/CD파이프라인
  3. user_new (박사원, 신입): 온보딩→실전 전환, code_review/knowledge_lookup 증가
  4. user_analyst (최주임, Data Analyst): 데이터분석, SQL/Pandas, 대시보드/시각화
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 런타임 import를 위해 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import ConversationTurn, ConversationSession, IntentCategory


def _t(base: datetime, day: int, hour: int, minute: int = 0) -> datetime:
    """기준일 + day일 + hour시 + minute분 → datetime"""
    return base + timedelta(days=day, hours=hour, minutes=minute)


def _turn(role: str, content: str, ts: datetime,
          intent=None) -> ConversationTurn:
    """ConversationTurn 생성 헬퍼"""
    return ConversationTurn(
        role=role, content=content, timestamp=ts, intent=intent
    )


def _session(uid: str, ts: datetime,
             turns: list[ConversationTurn]) -> ConversationSession:
    """ConversationSession 생성 헬퍼"""
    s = ConversationSession(user_id=uid, created_at=ts)
    s.turns = turns
    return s


# ──────────────────────────────────────────────
# user_pm: 김과장 (PM)
# 목표: ~50 user turns, ~16 sessions
# ──────────────────────────────────────────────
def generate_user_pm(base: datetime) -> list[ConversationSession]:
    """
    PM 패턴:
    - 월: 주간보고 → 이슈 트래킹 → 일정 조율
    - 수: 디자인 리뷰 → 피드백 정리 → 문서 작성
    - 금: 회고 → 다음 주 계획
    - week 1-2: 출장 관련 (scheduling, team_communication)
    - week 3: 출장 소멸 → category extinction 테스트
    - ephemeral 산발
    """
    uid = "user_pm"
    sessions = []

    for week in range(4):
        wo = week * 7

        # --- 월요일: 주간보고 → 이슈 트래킹 → 일정 조율 ---
        mon_turns = [
            _turn("user", "주간 보고 작성해야 하는데 지난주 핵심 이슈 뭐였지?",
                  _t(base, wo, 9, 0), IntentCategory.weekly_report),
            _turn("assistant", "지난 주 주요 이슈를 정리해드리겠습니다.",
                  _t(base, wo, 9, 1)),
            _turn("user", "이슈 중에 결제 쪽은 해결됐어?",
                  _t(base, wo, 9, 5), IntentCategory.issue_tracking),
            _turn("assistant",
                  "결제 API 레이턴시 이슈는 핫픽스 배포로 해결됐습니다. P95 응답시간 200ms 이하로 안정화됐어요.",
                  _t(base, wo, 9, 6)),
            _turn("user", "이번 주 일정 정리해줘",
                  _t(base, wo, 9, 10), IntentCategory.scheduling),
            _turn("assistant", "이번 주: 화 디자인리뷰, 수 스프린트플래닝, 금 회고입니다.",
                  _t(base, wo, 9, 11)),
        ]
        if week == 2:
            mon_turns.extend([
                _turn("user", "출장 일정도 포함시켜줘",
                      _t(base, wo, 9, 15), IntentCategory.scheduling),
                _turn("assistant", "네, 수~금 부산 출장 일정을 반영하겠습니다.",
                      _t(base, wo, 9, 16)),
            ])
        # 월요일 세션 끝에 간단한 확인 추가 (격주)
        if week in (1, 3):
            mon_turns.extend([
                _turn("user", "넵 확인",
                      _t(base, wo, 9, 20), None),  # ephemeral
                _turn("assistant", "필요하시면 말씀해주세요.",
                      _t(base, wo, 9, 21)),
            ])
        sessions.append(_session(uid, _t(base, wo, 9), mon_turns))

        # --- 화요일: 이슈 트래킹 + 팀 커뮤니케이션 ---
        tue = wo + 1
        tue_turns = [
            _turn("user", "오늘 스탠드업 내용 정리해줘",
                  _t(base, tue, 9, 0), IntentCategory.project_status),
            _turn("assistant",
                  f"어제: 핫픽스 배포 완료. 오늘: 디자인 리뷰. 블로커: 없음.",
                  _t(base, tue, 9, 1)),
        ]
        if week in (0, 2):
            tue_turns.extend([
                _turn("user", "블로커 없다니 다행이다 ㅋㅋ",
                      _t(base, tue, 9, 5), None),  # ephemeral
                _turn("assistant", "네, 순조롭게 진행 중입니다.",
                      _t(base, tue, 9, 6)),
            ])
        if week in (1, 3):
            tue_turns.extend([
                _turn("user", "이대리한테 PR 리뷰 독촉 좀 해줘",
                      _t(base, tue, 9, 5), IntentCategory.team_communication),
                _turn("assistant", "이대리님에게 PR 리뷰 요청 메시지를 보내겠습니다.",
                      _t(base, tue, 9, 6)),
            ])
        sessions.append(_session(uid, _t(base, tue, 9), tue_turns))

        # --- 수요일: 디자인 리뷰 → 피드백 → 문서 ---
        wed = wo + 2
        wed_turns = [
            _turn("user", "디자인 리뷰 미팅 준비해야 하는데 변경사항 정리해줘",
                  _t(base, wed, 14, 0), IntentCategory.meeting_prep),
            _turn("assistant",
                  "지난 스프린트 UI 변경사항을 정리했습니다. 결제 흐름 개선, 대시보드 차트 추가.",
                  _t(base, wed, 14, 1)),
            _turn("user", "피드백 내용 문서로 정리해줘",
                  _t(base, wed, 15, 0), IntentCategory.document_drafting),
            _turn("assistant", "디자인 리뷰 피드백 문서 초안을 작성하겠습니다.",
                  _t(base, wed, 15, 1)),
        ]
        if week % 2 == 1:
            wed_turns.extend([
                _turn("user", "ㅋㅋ 디자인팀이 또 전면 수정했네",
                      _t(base, wed, 15, 10), None),  # ephemeral
                _turn("assistant", "변경 범위가 넓어서 스프린트 일정에 영향이 있을 수 있습니다.",
                      _t(base, wed, 15, 11)),
                _turn("user", "팀원들한테 일정 변경 공유해줘",
                      _t(base, wed, 15, 15), IntentCategory.team_communication),
                _turn("assistant", "일정 변경 안내를 전달하겠습니다.",
                      _t(base, wed, 15, 16)),
            ])
        sessions.append(_session(uid, _t(base, wed, 14), wed_turns))

        # --- 금요일: 회고 → 다음 주 계획 ---
        fri = wo + 4
        fri_turns = [
            _turn("user", "이번 주 스프린트 회고할 건데 데이터 좀 뽑아줘",
                  _t(base, fri, 16, 0), IntentCategory.data_analysis),
            _turn("assistant",
                  f"이번 주 벨로시티: 완료 {20 + week * 2}pt / 계획 25pt. 지난 주 대비 +{week + 1}pt.",
                  _t(base, fri, 16, 1)),
            _turn("user", "회고 문서 작성해줘",
                  _t(base, fri, 16, 5), IntentCategory.document_drafting),
            _turn("assistant", "스프린트 회고 문서를 작성하겠습니다.",
                  _t(base, fri, 16, 6)),
            _turn("user", "다음 주 계획도 같이 정리해",
                  _t(base, fri, 16, 10), IntentCategory.scheduling),
            _turn("assistant", "다음 주 주요 일정과 목표를 정리하겠습니다.",
                  _t(base, fri, 16, 11)),
        ]
        sessions.append(_session(uid, _t(base, fri, 16), fri_turns))

        # --- week 1-2: 출장 관련 세션 (목요일) ---
        if week in (1, 2):
            trip_day = wo + 3
            if week == 1:
                trip_turns = [
                    _turn("user", "부산 출장 준비해야 하는데 항공편 확인해줘",
                          _t(base, trip_day, 11, 0), IntentCategory.scheduling),
                    _turn("assistant", "부산행 KTX 예약 현황을 확인하겠습니다.",
                          _t(base, trip_day, 11, 1)),
                    _turn("user", "팀원들한테 출장 일정 공유 좀",
                          _t(base, trip_day, 11, 5), IntentCategory.team_communication),
                    _turn("assistant", "출장 안내 메일 초안을 작성했습니다.",
                          _t(base, trip_day, 11, 6)),
                    _turn("user", "고객사 미팅 자료도 준비해줘",
                          _t(base, trip_day, 11, 10), IntentCategory.meeting_prep),
                    _turn("assistant", "고객사 미팅용 발표 자료 초안을 작성하겠습니다.",
                          _t(base, trip_day, 11, 11)),
                ]
            else:
                trip_turns = [
                    _turn("user", "부산 출장 결과 보고서 작성해야 해",
                          _t(base, trip_day, 11, 0), IntentCategory.document_drafting),
                    _turn("assistant", "출장 결과 보고서 초안을 작성하겠습니다.",
                          _t(base, trip_day, 11, 1)),
                    _turn("user", "고객 미팅 결과도 넣어줘",
                          _t(base, trip_day, 11, 5), IntentCategory.document_drafting),
                    _turn("assistant", "고객 미팅 요약을 포함하여 업데이트하겠습니다.",
                          _t(base, trip_day, 11, 6)),
                ]
            sessions.append(_session(uid, _t(base, trip_day, 11), trip_turns))

        # --- 목요일(출장 없는 주): 이슈 트래킹 ---
        if week not in (1, 2):
            thu = wo + 3
            thu_turns = [
                _turn("user", "백로그 우선순위 정리해줘",
                      _t(base, thu, 14, 0), IntentCategory.issue_tracking),
                _turn("assistant",
                      "P0: 결제 버그 수정, P1: 대시보드 리뉴얼, P2: 문서 업데이트",
                      _t(base, thu, 14, 1)),
                _turn("user", "결제 버그 담당 누구지?",
                      _t(base, thu, 14, 5), IntentCategory.team_communication),
                _turn("assistant", "이대리님이 담당하고 있습니다.",
                      _t(base, thu, 14, 6)),
            ]
            sessions.append(_session(uid, _t(base, thu, 14), thu_turns))

        # PM ephemeral은 기존 세션 내에서 이미 포함됨 (월/화 세션 내 넵/확인 등)

    return sessions


# ──────────────────────────────────────────────
# user_dev: 이대리 (Backend Dev)
# 목표: ~55 user turns, ~18 sessions
# ──────────────────────────────────────────────
def generate_user_dev(base: datetime) -> list[ConversationSession]:
    """
    개발자 패턴:
    - 매일: PR 리뷰 → 가끔 버그 발견 → 트러블슈팅
    - 기술 질문: Redis, K8s, Docker, CI/CD
    - CI/CD 파이프라인 이슈: v1 12 intent에 없음 → category discovery 테스트
    - 아키텍처 토론: 드물게 (code_review에서 분리 가능)
    - ephemeral: "ㅇㅋ", "ㄱㄱ", "점심 뭐 먹지"
    """
    uid = "user_dev"
    sessions = []

    # --- 버그/트러블슈팅 메시지 풀 ---
    bug_msgs = [
        ("PR 리뷰하다가 이상한 버그 발견. 결제 API가 간헐적으로 500 에러 뱉어",
         "해당 코드를 분석해보겠습니다. DB 커넥션 풀 고갈 가능성이 있습니다."),
        ("리뷰 중에 N+1 쿼리 발견했어 이거 성능 터질듯",
         "select_related/prefetch_related로 쿼리를 최적화해야 합니다. 실행 계획을 확인해볼게요."),
        ("null 체크 안 하고 있어서 프로덕션에서 NPE 터질 수 있을 것 같아",
         "Optional 타입 체크와 early return 패턴 적용을 권장합니다."),
        ("race condition 있을 것 같아 동시 결제 요청 들어오면 어떡해",
         "비관적 락(SELECT FOR UPDATE) 또는 분산 락(Redis Lock) 적용을 검토해보겠습니다."),
        ("메모리 누수 의심돼 서버 장시간 돌리면 RSS가 계속 올라가",
         "메모리 프로파일링 도구(tracemalloc)로 누수 지점을 추적해보겠습니다."),
        ("API 응답 시간이 갑자기 3배 느려졌어 뭐가 바뀐 거지?",
         "최근 배포 diff와 쿼리 실행 계획을 비교해보겠습니다."),
    ]

    # --- CI/CD 관련 메시지 풀 (기존 12 intent에 없음) ---
    cicd_msgs = [
        ("CI 파이프라인이 자꾸 타임아웃 나는데 뭐가 문제지?",
         "CI 로그를 확인해보겠습니다. Docker 이미지 빌드 단계에서 캐시 미스가 발생하고 있을 수 있습니다.",
         "빌드 캐시 어떻게 설정해?",
         "GitHub Actions의 actions/cache를 사용하시면 빌드 시간을 크게 줄일 수 있습니다."),
        ("GitHub Actions workflow 파일 수정했는데 리뷰 좀",
         "workflow 파일을 확인하겠습니다. 캐시 키 설정과 매트릭스 전략을 검토해볼게요.",
         "매트릭스에 Python 3.11이랑 3.12 같이 넣으면 되지?",
         "네, strategy.matrix.python-version에 ['3.11', '3.12'] 설정하시면 됩니다."),
        ("배포 파이프라인에서 도커 이미지 태깅이 안 돼",
         "docker build 스텝에서 tag 설정을 확인해보겠습니다.",
         "태그를 커밋 SHA로 자동 설정하는 방법은?",
         "GITHUB_SHA 환경 변수를 docker tag에 사용하시면 됩니다."),
        ("스테이징 배포가 롤백됐어 왜 그런 거야",
         "배포 로그를 확인해봤습니다. 헬스체크 실패로 자동 롤백된 것 같습니다.",
         "헬스체크 엔드포인트를 좀 더 관대하게 설정할 수 있어?",
         "초기화 시간을 고려해 initialDelaySeconds를 늘리는 것을 권장합니다."),
    ]

    # --- 기술 질문 풀 ---
    tech_qs = [
        ("Redis 캐시 만료 전략 어떤 게 좋을까?",
         "TTL 기반 vs LRU vs Write-through 세 가지 전략을 비교해드리겠습니다."),
        ("K8s pod가 OOMKilled 되는데 메모리 설정 어떻게 해야 해?",
         "현재 request/limit 설정을 확인하고 메모리 프로파일링을 추천합니다."),
        ("Docker 멀티스테이지 빌드로 이미지 사이즈 줄이고 싶은데",
         "빌드 스테이지와 런타임 스테이지를 분리하면 이미지 크기를 크게 줄일 수 있습니다."),
        ("gRPC vs REST 어떤 상황에서 뭐 써야 해?",
         "내부 마이크로서비스 간 통신은 gRPC, 외부 API는 REST가 일반적입니다."),
        ("Celery worker가 간헐적으로 죽어 모니터링 어떻게 해?",
         "Flower 대시보드와 Sentry 에러 트래킹을 병행하시면 됩니다."),
        ("SQLAlchemy 2.0 마이그레이션 가이드 있어?",
         "공식 migration guide를 참고하시면 됩니다. 주요 변경점은 Session.execute() 방식입니다."),
    ]

    bug_idx = 0
    cicd_idx = 0
    tech_idx = 0

    for week in range(4):
        wo = week * 7

        # --- 월요일: 코드리뷰 + 버그 발견 → 트러블슈팅 ---
        mon = wo
        pr_num = 200 + mon
        mon_turns = [
            _turn("user", "오늘 리뷰할 PR 있어?",
                  _t(base, mon, 10, 0), IntentCategory.code_review),
            _turn("assistant",
                  f"리뷰 대기 PR: #{pr_num} 인증 리팩토링, #{pr_num + 1} 테스트 추가",
                  _t(base, mon, 10, 1)),
        ]
        if bug_idx < len(bug_msgs):
            bq, ba = bug_msgs[bug_idx]
            mon_turns.extend([
                _turn("user", bq,
                      _t(base, mon, 11, 0), IntentCategory.troubleshooting),
                _turn("assistant", ba,
                      _t(base, mon, 11, 1)),
            ])
            if week % 2 == 0:
                mon_turns.extend([
                    _turn("user", "로그 좀 더 자세히 봐줘",
                          _t(base, mon, 11, 5), IntentCategory.troubleshooting),
                    _turn("assistant",
                          "스택 트레이스와 최근 배포 로그를 함께 분석하겠습니다.",
                          _t(base, mon, 11, 6)),
                ])
            bug_idx += 1
        sessions.append(_session(uid, _t(base, mon, 10), mon_turns))

        # --- 수요일: 코드리뷰 + 버그 (격주만) ---
        if week % 2 == 0 and bug_idx < len(bug_msgs):
            wed_d = wo + 2
            pr_num2 = 200 + wed_d
            bq2, ba2 = bug_msgs[bug_idx]
            sessions.append(_session(uid, _t(base, wed_d, 10), [
                _turn("user", "수요일 PR 리뷰하려고",
                      _t(base, wed_d, 10, 0), IntentCategory.code_review),
                _turn("assistant",
                      f"리뷰 대기: #{pr_num2} 캐시 레이어 추가",
                      _t(base, wed_d, 10, 1)),
                _turn("user", bq2,
                      _t(base, wed_d, 11, 0), IntentCategory.troubleshooting),
                _turn("assistant", ba2,
                      _t(base, wed_d, 11, 1)),
            ]))
            bug_idx += 1

        # --- 금요일: 코드리뷰 + 문서 정리 ---
        fri_d = wo + 4
        pr_num3 = 200 + fri_d
        fri_turns = [
            _turn("user", "금요일 PR 리뷰 뭐 남았어?",
                  _t(base, fri_d, 10, 0), IntentCategory.code_review),
            _turn("assistant",
                  f"리뷰 대기: #{pr_num3} 에러 핸들링 개선",
                  _t(base, fri_d, 10, 1)),
            _turn("user", "리뷰 완료된 PR 변경사항 정리해줘",
                  _t(base, fri_d, 11, 0), IntentCategory.document_drafting),
            _turn("assistant",
                  "이번 주 머지된 PR의 주요 변경사항을 정리하겠습니다.",
                  _t(base, fri_d, 11, 1)),
        ]
        # 격주 금요일: 주간 코드 품질 체크
        if week % 2 == 1:
            fri_turns.extend([
                _turn("user", "이번 주 테스트 커버리지 어떻게 돼?",
                      _t(base, fri_d, 11, 5), IntentCategory.project_status),
                _turn("assistant",
                      f"현재 테스트 커버리지: {78 + week * 2}%. 목표 대비 양호합니다.",
                      _t(base, fri_d, 11, 6)),
            ])
        sessions.append(_session(uid, _t(base, fri_d, 10), fri_turns))

        # --- 화요일: 기술 질문 ---
        if tech_idx < len(tech_qs):
            q, a = tech_qs[tech_idx]
            tue = wo + 1
            turns = [
                _turn("user", q,
                      _t(base, tue, 14, 0), IntentCategory.knowledge_lookup),
                _turn("assistant", a,
                      _t(base, tue, 14, 1)),
            ]
            # 격주 후속 질문
            if week % 2 == 0 and tech_idx + 1 < len(tech_qs):
                fq, fa = tech_qs[tech_idx + 1]
                turns.extend([
                    _turn("user", "그리고 하나 더, " + fq.lower(),
                          _t(base, tue, 14, 10), IntentCategory.knowledge_lookup),
                    _turn("assistant", fa,
                          _t(base, tue, 14, 11)),
                ])
                tech_idx += 1
            else:
                # 홀수 주: 기술 질문 끝에 간단 확인
                turns.extend([
                    _turn("user", "ㅇㅋ 고마워",
                          _t(base, tue, 14, 5), None),  # ephemeral
                    _turn("assistant", "언제든 물어보세요!",
                          _t(base, tue, 14, 6)),
                ])
            sessions.append(_session(uid, _t(base, tue, 14), turns))
            tech_idx += 1

        # --- 목요일 week 0: 프로젝트 현황 + 문서 ---
        if week == 0:
            thu = wo + 3
            sessions.append(_session(uid, _t(base, thu, 14), [
                _turn("user", "이번 스프린트 진행 상황 어떻게 돼?",
                      _t(base, thu, 14, 0), IntentCategory.project_status),
                _turn("assistant",
                      "현재 스프린트: 결제 모듈 60% 완료, 테스트 커버리지 75%입니다.",
                      _t(base, thu, 14, 1)),
                _turn("user", "API 문서도 업데이트해야 하는데 변경된 엔드포인트 정리해줘",
                      _t(base, thu, 14, 5), IntentCategory.document_drafting),
                _turn("assistant",
                      "변경된 API 엔드포인트 목록을 정리하겠습니다.",
                      _t(base, thu, 14, 6)),
                _turn("user", "Swagger 문서도 같이 업데이트해줘",
                      _t(base, thu, 14, 10), IntentCategory.document_drafting),
                _turn("assistant",
                      "OpenAPI spec 파일을 업데이트하고 Swagger UI에 반영하겠습니다.",
                      _t(base, thu, 14, 11)),
            ]))

        # --- 목요일: CI/CD 이슈 (week 1-3, 새 카테고리) ---
        if week >= 1 and cicd_idx < len(cicd_msgs):
            cq, ca, cq2, ca2 = cicd_msgs[cicd_idx]
            thu = wo + 3
            turns = [
                _turn("user", cq,
                      _t(base, thu, 15, 0), None),  # intent=None → 새 카테고리
                _turn("assistant", ca,
                      _t(base, thu, 15, 1)),
                _turn("user", cq2,
                      _t(base, thu, 15, 10), None),  # CI/CD 후속
                _turn("assistant", ca2,
                      _t(base, thu, 15, 11)),
            ]
            sessions.append(_session(uid, _t(base, thu, 15), turns))
            cicd_idx += 1

        # --- 아키텍처 토론 (week 2, 3) ---
        if week == 2:
            arch_day = wo + 4
            sessions.append(_session(uid, _t(base, arch_day, 16), [
                _turn("user",
                      "결제 모듈 아키텍처를 이벤트 드리븐으로 바꾸는 거 어떻게 생각해?",
                      _t(base, arch_day, 16, 0), IntentCategory.code_review),
                _turn("assistant",
                      "이벤트 소싱 패턴을 적용하면 결제 상태 추적이 용이해집니다. 복잡도 증가는 주의해야 합니다.",
                      _t(base, arch_day, 16, 1)),
                _turn("user", "관련 레퍼런스 문서 찾아줘",
                      _t(base, arch_day, 16, 10), IntentCategory.knowledge_lookup),
                _turn("assistant",
                      "Martin Fowler의 Event Sourcing 글과 AWS 이벤트 드리븐 아키텍처 가이드를 추천합니다.",
                      _t(base, arch_day, 16, 11)),
            ]))
        if week == 3:
            arch_day = wo + 4
            sessions.append(_session(uid, _t(base, arch_day, 16), [
                _turn("user",
                      "모놀리스에서 마이크로서비스로 전환할 때 뭐부터 분리해야 해?",
                      _t(base, arch_day, 16, 0), IntentCategory.code_review),
                _turn("assistant",
                      "비즈니스 도메인 경계가 명확한 모듈부터 분리하세요. Strangler Fig 패턴을 고려해보세요.",
                      _t(base, arch_day, 16, 1)),
                _turn("user", "우리 서비스에서는 인증 모듈이 제일 독립적인 것 같은데",
                      _t(base, arch_day, 16, 10), IntentCategory.code_review),
                _turn("assistant",
                      "인증 모듈은 좋은 후보입니다. API Gateway 뒤에 별도 서비스로 분리하는 것을 권장합니다.",
                      _t(base, arch_day, 16, 11)),
            ]))

        # dev ephemeral은 기존 세션 내 트레일링 턴으로 이미 포함됨

    return sessions


# ──────────────────────────────────────────────
# user_new: 박사원 (신입)
# 목표: ~50 user turns, ~18 sessions
# ──────────────────────────────────────────────
def generate_user_new(base: datetime) -> list[ConversationSession]:
    """
    신입 패턴:
    - week 0-1: 온보딩 집중 (환경설정, 코드 컨벤션, 팀 소개)
    - week 2-3: 온보딩 ↓↓, code_review/knowledge_lookup ↑↑
    - ephemeral: "안녕하세요~", "감사합니다!", "넵"
    """
    uid = "user_new"
    sessions = []

    # ──── Week 0: 첫 출근, 온보딩 집중 ────

    # 월: 첫 출근
    sessions.append(_session(uid, _t(base, 0, 9), [
        _turn("user", "안녕하세요~ 오늘 첫 출근인데 뭐부터 하면 될까요?",
              _t(base, 0, 9, 0), IntentCategory.onboarding),
        _turn("assistant",
              "환영합니다! 개발 환경 설정부터 시작하세요. 온보딩 가이드를 안내해드릴게요.",
              _t(base, 0, 9, 1)),
        _turn("user", "개발 환경 설정 문서 어디 있어요?",
              _t(base, 0, 9, 5), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "Confluence의 'Developer Onboarding' 페이지에 있습니다.",
              _t(base, 0, 9, 6)),
        _turn("user", "감사합니다!",
              _t(base, 0, 9, 10), None),  # ephemeral
        _turn("assistant", "궁금한 점 있으시면 편하게 물어보세요!",
              _t(base, 0, 9, 11)),
    ]))

    # 화: IDE + 플러그인
    sessions.append(_session(uid, _t(base, 1, 10), [
        _turn("user", "IDE 설정 하려는데 우리 팀 추천 플러그인이 뭐예요?",
              _t(base, 1, 10, 0), IntentCategory.onboarding),
        _turn("assistant",
              "VSCode 기준으로 ESLint, Prettier, GitLens, Python 확장을 권장합니다.",
              _t(base, 1, 10, 1)),
        _turn("user", "Python 확장은 어떤 걸 설치해야 하나요?",
              _t(base, 1, 10, 5), IntentCategory.onboarding),
        _turn("assistant",
              "ms-python.python 확장과 Pylance를 설치하시면 됩니다.",
              _t(base, 1, 10, 6)),
        _turn("user", "넵 감사합니다~",
              _t(base, 1, 10, 10), None),  # ephemeral
        _turn("assistant", "궁금한 점 있으시면 편하게 물어보세요!",
              _t(base, 1, 10, 11)),
    ]))

    # 수: 코드 컨벤션 + 브랜치 전략
    sessions.append(_session(uid, _t(base, 2, 10), [
        _turn("user", "우리 팀 코드 컨벤션이 어떻게 돼요?",
              _t(base, 2, 10, 0), IntentCategory.onboarding),
        _turn("assistant",
              "ESLint + Prettier 조합을 사용합니다. .eslintrc 파일을 참고하세요.",
              _t(base, 2, 10, 1)),
        _turn("user", "브랜치 전략은요? Git flow 쓰나요?",
              _t(base, 2, 10, 5), IntentCategory.onboarding),
        _turn("assistant",
              "trunk-based development입니다. feature 브랜치 → PR → 머지.",
              _t(base, 2, 10, 6)),
        _turn("user", "커밋 메시지 규칙도 있나요?",
              _t(base, 2, 10, 10), IntentCategory.onboarding),
        _turn("assistant",
              "Conventional Commits를 따릅니다. feat:, fix:, docs: 접두사를 사용하세요.",
              _t(base, 2, 10, 11)),
    ]))

    # 목: 팀 소개
    sessions.append(_session(uid, _t(base, 3, 14), [
        _turn("user", "팀 구성원이 어떻게 되는지 알 수 있을까요?",
              _t(base, 3, 14, 0), IntentCategory.onboarding),
        _turn("assistant",
              "팀: PM 김과장님, 백엔드 이대리님, 데이터 최주임님, 그리고 박사원님입니다.",
              _t(base, 3, 14, 1)),
        _turn("user", "각 분이 어떤 업무를 담당하시나요?",
              _t(base, 3, 14, 5), IntentCategory.onboarding),
        _turn("assistant",
              "김과장: 프로젝트 관리, 이대리: 백엔드 개발, 최주임: 데이터 분석입니다.",
              _t(base, 3, 14, 6)),
    ]))

    # 금: 온보딩 문서 정리
    sessions.append(_session(uid, _t(base, 4, 16), [
        _turn("user", "이번 주 온보딩 학습 내용 정리해서 문서로 만들어야 해요",
              _t(base, 4, 16, 0), IntentCategory.document_drafting),
        _turn("assistant", "이번 주 배운 내용을 카테고리별로 정리해드리겠습니다.",
              _t(base, 4, 16, 1)),
        _turn("user", "환경설정, 컨벤션, 팀 구조로 나눠서 정리해주세요",
              _t(base, 4, 16, 5), IntentCategory.document_drafting),
        _turn("assistant", "세 개 섹션으로 구분하여 정리하겠습니다.",
              _t(base, 4, 16, 6)),
    ]))

    # ──── Week 1: 온보딩 후반 + 첫 작업 ────
    wo = 7

    # 월: 온보딩 마무리
    sessions.append(_session(uid, _t(base, wo, 9), [
        _turn("user", "안녕하세요~ DB 스키마 문서는 어디서 볼 수 있나요?",
              _t(base, wo, 9, 0), IntentCategory.onboarding),
        _turn("assistant",
              "dbdocs.io에 ERD가 있습니다. 주요 테이블 관계도 설명되어 있어요.",
              _t(base, wo, 9, 1)),
        _turn("user", "API 문서는요?",
              _t(base, wo, 9, 5), IntentCategory.onboarding),
        _turn("assistant",
              "Swagger UI가 /docs 경로에 있고, Postman 컬렉션도 공유되어 있습니다.",
              _t(base, wo, 9, 6)),
    ]))

    # 화: 첫 PR
    sessions.append(_session(uid, _t(base, wo + 1, 10), [
        _turn("user", "첫 PR 올려도 될까요? 리뷰어 누구로 지정하면 되나요?",
              _t(base, wo + 1, 10, 0), IntentCategory.code_review),
        _turn("assistant", "네! 리뷰어는 이대리님을 지정해주세요.",
              _t(base, wo + 1, 10, 1)),
        _turn("user", "감사합니다! 올렸어요",
              _t(base, wo + 1, 10, 10), None),  # ephemeral
        _turn("assistant", "확인하겠습니다!",
              _t(base, wo + 1, 10, 11)),
    ]))

    # 수: 테스트 작성
    sessions.append(_session(uid, _t(base, wo + 2, 14), [
        _turn("user", "pytest fixture 어떻게 써요? conftest.py에 넣으면 되나요?",
              _t(base, wo + 2, 14, 0), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "네, conftest.py에 공통 fixture를 정의하면 자동 인식됩니다.",
              _t(base, wo + 2, 14, 1)),
        _turn("user", "mock이랑 fixture 차이가 뭐예요?",
              _t(base, wo + 2, 14, 5), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "fixture는 데이터/환경 셋업, mock은 외부 의존성을 가짜로 대체합니다.",
              _t(base, wo + 2, 14, 6)),
    ]))

    # 목: 리뷰 피드백 반영
    sessions.append(_session(uid, _t(base, wo + 3, 15), [
        _turn("user", "코드 리뷰 피드백 반영했는데 확인해주세요",
              _t(base, wo + 3, 15, 0), IntentCategory.code_review),
        _turn("assistant", "변경사항 확인했습니다. 에러 핸들링만 수정하면 LGTM입니다.",
              _t(base, wo + 3, 15, 1)),
        _turn("user", "넵 수정했어요!",
              _t(base, wo + 3, 15, 5), None),  # ephemeral
        _turn("assistant", "확인 완료! 머지하겠습니다.",
              _t(base, wo + 3, 15, 6)),
    ]))

    # 금: 주간 정리
    sessions.append(_session(uid, _t(base, wo + 4, 16), [
        _turn("user", "이번 주 한 일 정리해주세요",
              _t(base, wo + 4, 16, 0), IntentCategory.project_status),
        _turn("assistant",
              "이번 주: 1) 온보딩 마무리 2) 첫 PR 머지 3) 테스트 작성 학습",
              _t(base, wo + 4, 16, 1)),
        _turn("user", "다음 주부터 실전 투입이죠?",
              _t(base, wo + 4, 16, 5), IntentCategory.project_status),
        _turn("assistant",
              "네, 프로필 API 구현 태스크가 배정될 예정입니다.",
              _t(base, wo + 4, 16, 6)),
    ]))

    # ──── Week 2: 온보딩 거의 없음, 실전 작업 ────
    wo = 14

    # 월: 태스크 확인
    sessions.append(_session(uid, _t(base, wo, 9), [
        _turn("user", "이번 주 제 담당 태스크 뭐예요?",
              _t(base, wo, 9, 0), IntentCategory.project_status),
        _turn("assistant",
              "이번 주: 1) 사용자 프로필 API 구현 2) 테스트 작성 3) PR 피드백 반영",
              _t(base, wo, 9, 1)),
        _turn("user", "프로필 API 스펙 문서 어디 있어요?",
              _t(base, wo, 9, 5), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "API 스펙은 Notion의 'API Design' 페이지에 정리되어 있습니다.",
              _t(base, wo, 9, 6)),
    ]))

    # 화: 코드리뷰 피드백
    sessions.append(_session(uid, _t(base, wo + 1, 10), [
        _turn("user", "코드 리뷰 피드백 반영했는데 확인해주세요",
              _t(base, wo + 1, 10, 0), IntentCategory.code_review),
        _turn("assistant",
              "확인했습니다. 에러 핸들링 부분만 수정하시면 LGTM입니다.",
              _t(base, wo + 1, 10, 1)),
        _turn("user", "에러 핸들링은 어떤 패턴이 좋을까요?",
              _t(base, wo + 1, 10, 5), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "커스텀 예외 + 글로벌 에러 핸들러 패턴을 추천합니다.",
              _t(base, wo + 1, 10, 6)),
        _turn("user", "감사합니다!",
              _t(base, wo + 1, 10, 10), None),  # ephemeral
        _turn("assistant", "화이팅입니다!",
              _t(base, wo + 1, 10, 11)),
    ]))

    # 수: FastAPI 질문
    sessions.append(_session(uid, _t(base, wo + 2, 14), [
        _turn("user", "FastAPI에서 Depends 패턴 어떻게 쓰는 건가요?",
              _t(base, wo + 2, 14, 0), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "Depends로 의존성 주입을 선언적으로 처리합니다. DB 세션, 인증 등에 활용합니다.",
              _t(base, wo + 2, 14, 1)),
        _turn("user", "Pydantic validation은 자동으로 되는 건가요?",
              _t(base, wo + 2, 14, 5), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "네, request body에 Pydantic 모델을 지정하면 자동 validation 됩니다.",
              _t(base, wo + 2, 14, 6)),
    ]))

    # 수 오후: 트러블슈팅 (처음으로 혼자 디버깅)
    sessions.append(_session(uid, _t(base, wo + 2, 16), [
        _turn("user", "API 테스트 중에 422 에러가 나는데 뭐가 문제인 건가요?",
              _t(base, wo + 2, 16, 0), IntentCategory.troubleshooting),
        _turn("assistant",
              "422는 validation 에러입니다. 요청 body의 필드 타입과 스키마를 확인해보세요.",
              _t(base, wo + 2, 16, 1)),
        _turn("user", "아 날짜 포맷이 잘못됐었네요 감사합니다!",
              _t(base, wo + 2, 16, 5), None),  # ephemeral
        _turn("assistant", "자주 있는 실수예요. ISO 8601 포맷(YYYY-MM-DD)을 사용하시면 됩니다.",
              _t(base, wo + 2, 16, 6)),
    ]))

    # 목: 구현 + PR
    sessions.append(_session(uid, _t(base, wo + 3, 10), [
        _turn("user", "프로필 API 구현 다 했어요 PR 올렸는데 리뷰 부탁드려요",
              _t(base, wo + 3, 10, 0), IntentCategory.code_review),
        _turn("assistant", "PR 확인하겠습니다. 테스트 커버리지도 체크할게요.",
              _t(base, wo + 3, 10, 1)),
        _turn("user", "테스트 커버리지 80% 넘겼어요",
              _t(base, wo + 3, 10, 5), IntentCategory.code_review),
        _turn("assistant", "훌륭합니다! edge case 테스트도 포함되어 있어서 좋습니다.",
              _t(base, wo + 3, 10, 6)),
    ]))

    # 금: 주간 회고
    sessions.append(_session(uid, _t(base, wo + 4, 15), [
        _turn("user", "이번 주 진행 상황 정리해주세요",
              _t(base, wo + 4, 15, 0), IntentCategory.project_status),
        _turn("assistant",
              "이번 주: 프로필 API 구현 완료, PR 리뷰 진행 중, 테스트 90% 작성 완료.",
              _t(base, wo + 4, 15, 1)),
        _turn("user", "다음 주에는 뭐 하면 돼요?",
              _t(base, wo + 4, 15, 5), IntentCategory.project_status),
        _turn("assistant",
              "다음 주: 알림 서비스 구현, 통합 테스트 작성이 예정되어 있습니다.",
              _t(base, wo + 4, 15, 6)),
    ]))

    # ──── Week 3: 온보딩 완전 소멸, code_review + knowledge_lookup 중심 ────
    wo = 21

    # 월: 태스크
    sessions.append(_session(uid, _t(base, wo, 9), [
        _turn("user", "이번 주 담당 태스크 확인할게요",
              _t(base, wo, 9, 0), IntentCategory.project_status),
        _turn("assistant",
              "이번 주: 1) 알림 서비스 구현 2) 통합 테스트 작성",
              _t(base, wo, 9, 1)),
        _turn("user", "알림 서비스 설계 문서 먼저 봐야겠어요",
              _t(base, wo, 9, 5), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "알림 서비스 설계 문서는 Wiki에 있습니다. 이벤트 기반 아키텍처로 설계되어 있어요.",
              _t(base, wo, 9, 6)),
    ]))

    # 화: 기술 질문
    sessions.append(_session(uid, _t(base, wo + 1, 10), [
        _turn("user",
              "WebSocket으로 실시간 알림 구현하려면 어떻게 해야 하나요?",
              _t(base, wo + 1, 10, 0), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "FastAPI WebSocket 엔드포인트를 사용하세요. ConnectionManager 패턴을 추천합니다.",
              _t(base, wo + 1, 10, 1)),
        _turn("user", "Redis Pub/Sub이랑 연동도 가능해요?",
              _t(base, wo + 1, 10, 5), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "네, Redis Pub/Sub을 백엔드로 사용하면 다중 서버에서도 실시간 알림 가능합니다.",
              _t(base, wo + 1, 10, 6)),
    ]))

    # 수: PR 리뷰
    sessions.append(_session(uid, _t(base, wo + 2, 14), [
        _turn("user", "알림 서비스 PR 올렸어요 설계 리뷰 부탁드려요",
              _t(base, wo + 2, 14, 0), IntentCategory.code_review),
        _turn("assistant",
              "PR 확인했습니다. 구조가 깔끔합니다. 에러 재시도 로직 추가를 제안합니다.",
              _t(base, wo + 2, 14, 1)),
        _turn("user", "재시도 로직은 exponential backoff로 하면 될까요?",
              _t(base, wo + 2, 14, 5), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "네, tenacity 라이브러리의 @retry 데코레이터를 사용하시면 편리합니다.",
              _t(base, wo + 2, 14, 6)),
    ]))

    # 목: 트러블슈팅 + 문서 작성
    sessions.append(_session(uid, _t(base, wo + 3, 10), [
        _turn("user", "WebSocket 연결이 간헐적으로 끊기는데 왜 그런 건가요?",
              _t(base, wo + 3, 10, 0), IntentCategory.troubleshooting),
        _turn("assistant",
              "ping/pong heartbeat 미설정이 원인일 수 있습니다. WebSocket keepalive 설정을 확인해보세요.",
              _t(base, wo + 3, 10, 1)),
        _turn("user", "해결됐어요! 트러블슈팅 과정을 문서로 남겨야 할 것 같아요",
              _t(base, wo + 3, 10, 5), IntentCategory.document_drafting),
        _turn("assistant",
              "좋은 습관입니다. 문제 상황, 원인, 해결책을 포함한 TIL 문서를 작성하겠습니다.",
              _t(base, wo + 3, 10, 6)),
    ]))

    # 금: 통합 테스트 + ephemeral
    sessions.append(_session(uid, _t(base, wo + 4, 15), [
        _turn("user",
              "통합 테스트에서 외부 API 호출은 어떻게 처리하나요?",
              _t(base, wo + 4, 15, 0), IntentCategory.knowledge_lookup),
        _turn("assistant",
              "VCR 패턴이나 responses 라이브러리로 HTTP 요청을 모킹하면 됩니다.",
              _t(base, wo + 4, 15, 1)),
        _turn("user", "테스트 다 통과시켰어요 이번 주 정리해주세요",
              _t(base, wo + 4, 15, 5), IntentCategory.project_status),
        _turn("assistant",
              "이번 주: 알림 서비스 구현 완료, 통합 테스트 작성 완료, WebSocket 이슈 해결.",
              _t(base, wo + 4, 15, 6)),
        _turn("user", "넵 감사합니다!",
              _t(base, wo + 4, 15, 10), None),  # ephemeral
        _turn("assistant", "수고하셨습니다!",
              _t(base, wo + 4, 15, 11)),
    ]))

    return sessions


# ──────────────────────────────────────────────
# user_analyst: 최주임 (Data Analyst)
# 목표: ~50 user turns, ~18 sessions
# ──────────────────────────────────────────────
def generate_user_analyst(base: datetime) -> list[ConversationSession]:
    """
    데이터 분석가 패턴:
    - 데이터 분석 + 시각화 (Pandas, SQL, Grafana)
    - 대시보드/리포트: v1 12 intent에 없음 → category discovery 테스트
    - PM과 project_status 겹침 → fusion/split 테스트
    - ephemeral: "오키", "넵넵"
    """
    uid = "user_analyst"
    sessions = []

    # --- 대시보드/시각화 메시지 풀 (기존 12 intent에 없음) ---
    dashboard_convos = [
        ("Grafana 대시보드에 신규 메트릭 추가하고 싶은데",
         "어떤 메트릭을 추가하실 건가요? 데이터소스 연결부터 확인해드리겠습니다.",
         "커스텀 패널 만드는 방법 알려줘",
         "Add Panel → SQL 쿼리 설정 → Visualization 타입 선택하시면 됩니다."),
        ("주간 리포트 자동화 대시보드 만들려고 하는데",
         "Grafana Provisioning이나 Superset을 활용하시면 됩니다.",
         "DAU, WAU, 매출 추이를 한 화면에 보고 싶어",
         "멀티 패널 대시보드로 구성하겠습니다. 시계열 + 바 차트 조합이 적합합니다."),
        ("경영진 대시보드에 Funnel 차트 추가해야 해",
         "Google Analytics 연동이나 자체 이벤트 로그 기반으로 Funnel 구성 가능합니다.",
         "전환율 단계별로 보여줘야 하는데 어떤 차트가 좋을까",
         "Plotly funnel chart나 D3.js 기반 커스텀 차트를 추천합니다."),
        ("리텐션 코호트 분석 시각화하려면 어떻게 해?",
         "Pandas 코호트 테이블 → seaborn heatmap으로 시각화하면 됩니다.",
         "matplotlib로도 할 수 있어?",
         "네, plt.pcolormesh로도 가능합니다. 다만 seaborn이 더 깔끔합니다."),
    ]

    for week in range(4):
        wo = week * 7

        # --- 월요일: SQL 데이터 분석 ---
        sql_qs = [
            ("지난주 매출 데이터 쿼리 좀 도와줘. GROUP BY 절이 잘 안 돼",
             "GROUP BY에 집계 함수와 컬럼을 정리해드릴게요."),
            ("사용자 세그먼트별 리텐션율 쿼리 작성해줘",
             "코호트별 리텐션 분석 쿼리를 작성해드리겠습니다. DATE_TRUNC 활용합니다."),
            ("이번 달 신규 가입자 퍼널 분석 쿼리 필요해",
             "퍼널 분석용 CTE 기반 쿼리를 작성해드리겠습니다."),
            ("A/B 테스트 결과 데이터 추출 쿼리 작성해줘",
             "A/B 그룹별 주요 지표 비교 쿼리를 작성하겠습니다."),
        ]
        sq, sa = sql_qs[week]
        mon_turns = [
            _turn("user", sq,
                  _t(base, wo, 10, 0), IntentCategory.data_analysis),
            _turn("assistant", sa,
                  _t(base, wo, 10, 1)),
        ]
        # 후속 질문 추가
        follow_ups = [
            ("서브쿼리 대신 CTE로 쓸 수 있어?",
             "네, WITH절을 사용하면 가독성이 좋아집니다."),
            ("WINDOW 함수 사용법도 알려줘",
             "ROW_NUMBER, LAG, LEAD 등의 윈도우 함수를 안내해드리겠습니다."),
            ("인덱스 안 타는 것 같은데 실행 계획 봐줘",
             "EXPLAIN ANALYZE로 실행 계획을 확인해보겠습니다."),
            ("통계적 유의성은 어떻게 계산해?",
             "scipy.stats의 chi2_contingency나 t-test를 활용하시면 됩니다."),
        ]
        fq, fa = follow_ups[week]
        mon_turns.extend([
            _turn("user", fq,
                  _t(base, wo, 10, 10), IntentCategory.data_analysis),
            _turn("assistant", fa,
                  _t(base, wo, 10, 11)),
        ])
        # 월 오후: 도구 관련 후속 질문 (같은 세션에 추가)
        tool_qs = [
            ("그리고 Jupyter에서 SQL 바로 실행하는 방법 있어?",
             "ipython-sql 확장을 설치하면 %%sql 매직 커맨드로 실행 가능합니다."),
            ("참 데이터 파이프라인 스케줄링은 Airflow로 해야 하나?",
             "Airflow가 표준이지만, 간단한 작업은 Prefect이나 cron도 옵션입니다."),
            ("dbt로 데이터 변환 자동화하는 게 좋을까?",
             "dbt는 SQL 기반 변환에 최적입니다. 버전 관리와 테스트도 지원합니다."),
            ("데이터 품질 모니터링은 어떻게 하면 좋아?",
             "Great Expectations 같은 도구로 데이터 검증 파이프라인을 구축하시면 됩니다."),
        ]
        tq, ta = tool_qs[week]
        mon_turns.extend([
            _turn("user", tq,
                  _t(base, wo, 10, 15), IntentCategory.knowledge_lookup),
            _turn("assistant", ta,
                  _t(base, wo, 10, 16)),
        ])
        # 격주 ephemeral 종료
        if week % 2 == 1:
            mon_turns.extend([
                _turn("user", "넵넵 고마워",
                      _t(base, wo, 10, 20), None),  # ephemeral
                _turn("assistant", "언제든요!",
                      _t(base, wo, 10, 21)),
            ])
        sessions.append(_session(uid, _t(base, wo, 10), mon_turns))

        # --- 화요일: Pandas 데이터 처리 ---
        pandas_topics = [
            ("Pandas로 매출 데이터 전처리하는데 결측치 처리 어떻게 하면 좋을까?",
             "결측치 패턴에 따라 dropna, fillna, interpolate를 사용합니다.",
             "피벗테이블 만드는 법도 알려줘",
             "pd.pivot_table(df, values='매출', index='날짜', columns='카테고리')로 만듭니다."),
            ("DataFrame merge할 때 left join이랑 inner join 차이가 뭐야?",
             "left join은 왼쪽 테이블 전체 유지, inner join은 교집합만 반환합니다.",
             "merge 성능 최적화하려면?",
             "인덱스 기반 join이나 categorical dtype 변환이 효과적입니다."),
            ("시계열 데이터 리샘플링 어떻게 해?",
             "df.resample('W').mean()으로 주간 집계가 가능합니다.",
             "rolling average도 같이 보고 싶어",
             "df.rolling(window=7).mean()을 적용하시면 됩니다."),
            ("대용량 CSV 읽을 때 메모리 터지는데 어떡해?",
             "chunksize 파라미터로 분할 읽기하거나, dtype 최적화하세요.",
             "Parquet 포맷으로 변환하는 게 나을까?",
             "네, Parquet은 컬럼 기반이라 분석 쿼리에 훨씬 효율적입니다."),
        ]
        pq, pa, pq2, pa2 = pandas_topics[week]
        pandas_turns = [
            _turn("user", pq,
                  _t(base, wo + 1, 10, 0), IntentCategory.data_analysis),
            _turn("assistant", pa,
                  _t(base, wo + 1, 10, 1)),
            _turn("user", pq2,
                  _t(base, wo + 1, 10, 5), IntentCategory.data_analysis),
            _turn("assistant", pa2,
                  _t(base, wo + 1, 10, 6)),
        ]
        # 격주 ephemeral 종료
        if week % 2 == 0:
            pandas_turns.extend([
                _turn("user", "오키 고마워",
                      _t(base, wo + 1, 10, 10), None),  # ephemeral
                _turn("assistant", "언제든 물어보세요!",
                      _t(base, wo + 1, 10, 11)),
            ])
        sessions.append(_session(uid, _t(base, wo + 1, 10), pandas_turns))

        # --- 수요일: 대시보드/시각화 (새 카테고리) ---
        dq, da, dq2, da2 = dashboard_convos[week]
        wed_turns = [
            _turn("user", dq,
                  _t(base, wo + 2, 14, 0), None),  # 12 카테고리에 없음
            _turn("assistant", da,
                  _t(base, wo + 2, 14, 1)),
            _turn("user", dq2,
                  _t(base, wo + 2, 14, 5), None),  # 대시보드/시각화
            _turn("assistant", da2,
                  _t(base, wo + 2, 14, 6)),
        ]
        sessions.append(_session(uid, _t(base, wo + 2, 14), wed_turns))

        # --- 목요일: project_status (PM과 겹침) ---
        status_msgs = [
            ("이번 주 데이터 파이프라인 상태 업데이트할게",
             "현재 진행 상황을 정리해주세요.",
             "ETL 스케줄러 설정도 해야 해",
             "Airflow DAG 설정을 도와드리겠습니다."),
            ("ETL 작업 진행상황 공유할게. 80% 완료됐어",
             "좋습니다. 남은 20%는 어떤 작업인가요?",
             "데이터 검증 로직이랑 에러 핸들링이 남았어",
             "검증 로직은 Great Expectations로 자동화하면 효율적입니다."),
            ("대시보드 개발 진행률 보고할게",
             "진행 상황을 정리해드리겠습니다.",
             "김과장님한테 공유할 자료도 만들어줘",
             "PM님께 공유할 진행 상황 요약을 작성하겠습니다."),
            ("이번 분기 데이터 프로젝트 현황 정리해줘",
             "분기별 데이터 프로젝트 현황을 정리하겠습니다.",
             "KPI 달성률도 같이 넣어줘",
             "KPI 달성률을 포함하여 정리하겠습니다."),
        ]
        sq1, sa1, sq2, sa2 = status_msgs[week]
        thu_turns = [
            _turn("user", sq1,
                  _t(base, wo + 3, 11, 0), IntentCategory.project_status),
            _turn("assistant", sa1,
                  _t(base, wo + 3, 11, 1)),
        ]
        if sq2:
            thu_turns.extend([
                _turn("user", sq2,
                      _t(base, wo + 3, 11, 5),
                      IntentCategory.scheduling if week == 0
                      else IntentCategory.team_communication if week == 2
                      else IntentCategory.project_status),
                _turn("assistant", sa2,
                      _t(base, wo + 3, 11, 6)),
            ])
        # ephemeral 추가 (격주)
        if week % 2 == 1:
            thu_turns.extend([
                _turn("user", "넵넵",
                      _t(base, wo + 3, 11, 10), None),  # ephemeral
                _turn("assistant", "추가 사항 있으시면 말씀해주세요.",
                      _t(base, wo + 3, 11, 11)),
            ])
        sessions.append(_session(uid, _t(base, wo + 3, 11), thu_turns))

        # --- 금요일: 리포트 작성 + 추가 분석 ---
        fri_turns = []
        if week % 2 == 0:
            fri_turns = [
                _turn("user", "주간 데이터 리포트 작성해줘",
                      _t(base, wo + 4, 15, 0), IntentCategory.document_drafting),
                _turn("assistant",
                      "주간 리포트 작성하겠습니다. 핵심 지표, 이상치, 인사이트 포함.",
                      _t(base, wo + 4, 15, 1)),
                _turn("user", "그래프도 같이 넣어줘",
                      _t(base, wo + 4, 15, 5), IntentCategory.document_drafting),
                _turn("assistant",
                      "matplotlib/seaborn 시각화를 리포트에 포함하겠습니다.",
                      _t(base, wo + 4, 15, 6)),
            ]
        else:
            fri_turns = [
                _turn("user", "이상치 탐지 결과 좀 봐줘",
                      _t(base, wo + 4, 15, 0), IntentCategory.data_analysis),
                _turn("assistant",
                      "Z-score 기반 이상치 탐지 결과: 3건의 이상치 발견.",
                      _t(base, wo + 4, 15, 1)),
                _turn("user", "오키 보고서에 넣어줘",
                      _t(base, wo + 4, 15, 5), IntentCategory.document_drafting),
                _turn("assistant", "이상치 분석 결과를 보고서에 추가하겠습니다.",
                      _t(base, wo + 4, 15, 6)),
            ]
        sessions.append(_session(uid, _t(base, wo + 4, 15), fri_turns))

    return sessions


# ──────────────────────────────────────────────
# 전체 데이터 생성
# ──────────────────────────────────────────────
def generate_all() -> dict:
    """전체 리얼리스틱 대화 데이터 생성"""
    base_date = datetime(2026, 3, 23, 0, 0, 0)  # 월요일 시작

    pm_sessions = generate_user_pm(base_date)
    dev_sessions = generate_user_dev(base_date)
    new_sessions = generate_user_new(base_date)
    analyst_sessions = generate_user_analyst(base_date)

    all_sessions = pm_sessions + dev_sessions + new_sessions + analyst_sessions

    # --- 통계 ---
    total_turns = sum(len(s.turns) for s in all_sessions)
    user_turns = sum(
        1 for s in all_sessions for t in s.turns if t.role == "user"
    )

    # intent 분포 (user 턴만)
    intent_counts: dict[str, int] = {}
    ephemeral_count = 0
    new_category_count = 0
    for s in all_sessions:
        for t in s.turns:
            if t.role != "user":
                continue
            if t.intent:
                key = t.intent.value
                intent_counts[key] = intent_counts.get(key, 0) + 1
            else:
                # ephemeral vs 새 카테고리 구분: 10자 이하 = ephemeral
                if len(t.content) <= 10:
                    ephemeral_count += 1
                else:
                    new_category_count += 1

    intent_counts["_ephemeral"] = ephemeral_count
    intent_counts["_new_category(cicd/dashboard)"] = new_category_count

    # 유저별 턴 수
    user_turn_counts: dict[str, int] = {}
    for s in all_sessions:
        uid = s.user_id
        cnt = sum(1 for t in s.turns if t.role == "user")
        user_turn_counts[uid] = user_turn_counts.get(uid, 0) + cnt

    data = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "base_date": base_date.isoformat(),
            "duration_days": 28,
            "users": ["user_pm", "user_dev", "user_new", "user_analyst"],
            "total_sessions": len(all_sessions),
            "total_turns": total_turns,
            "total_user_turns": user_turns,
            "user_turn_counts": user_turn_counts,
            "intent_distribution": dict(
                sorted(intent_counts.items(), key=lambda x: -x[1])
            ),
        },
        "sessions": [s.model_dump(mode="json") for s in all_sessions],
    }

    return data


if __name__ == "__main__":
    data = generate_all()

    output_path = Path(__file__).parent / "realistic_conversations.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    meta = data["metadata"]
    print("생성 완료!")
    print(f"  세션: {meta['total_sessions']}개")
    print(f"  전체 턴: {meta['total_turns']}개")
    print(f"  유저 턴: {meta['total_user_turns']}개")
    print(f"  유저별 턴:")
    for uid, cnt in meta["user_turn_counts"].items():
        print(f"    {uid}: {cnt}")
    print(f"  Intent 분포:")
    for intent, count in meta["intent_distribution"].items():
        print(f"    {intent}: {count}")
    print(f"\n저장: {output_path}")

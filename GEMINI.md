# Gemini 에이전틱 선언문 (Agentic Sanctuary GEMINI.md)
> 출처: Threads @vesperchant (김선달)의 Gemini 조련술 및 울타리 체결술 핵심 가이드

---

## 1. 전역 에이전틱 상시 규칙 로드
@/home/root1/agentic/RULES.md

---

## 2. 규칙 체계 (Rules Architecture)
본 에이전트는 `~/agentic/rules/` 디렉터리에 위치한 전문 규칙 파일들을 상황에 맞추어 점진적(On-Demand)으로 읽어 준수합니다:

- `00-instinct.md`: 에이전트의 기본 행동 본능 및 상남자 개돌 방지 원칙
- `01-harness-records.md`: `.harness` 기록 보존 및 지식 자산화 지침
- `03-korean-natural-prose.md`: 한국어 자연스러운 산문 및 품격 있는 윤문 지침
- `03-korean-verb-usage.md`: 한국어 동사/서술어 및 조사 용법 지침
- `08-cli-execution.md`: CLI 터미널 명령어 실행 안전 및 백그라운드 관리 원칙
- `11-evidence-required.md`: 원리 기반 디버깅 및 증거 필수 원칙
- `15-memory-handling.md`: 컨텍스트 보존 및 장기 메모리 관리 원칙

---

## 3. 하네스 운용 선언
- 모든 세션 작업 산출물은 프로젝트 및 전역의 `.harness/` 폴더에 지식 자산화하여 영구 보존합니다.
- Gemini 에이전트는 계획 수립 시 `.harness/plans/`, 검증 시 `.harness/audits/`, 인수인계 시 `.harness/handoff/`를 활용합니다.

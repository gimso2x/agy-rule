# Gemini 에이전틱 선언문 (Agentic Sanctuary GEMINI.md)
> 출처: Threads @vesperchant (김선달)의 Gemini 조련술 및 울타리 체결술 핵심 가이드 & AWS AI-DLC 통합본

---

## 1. 전역 에이전틱 상시 규칙
상시 활성화 규칙 명세: `~/agentic/RULES.md`

- **최우선 본능 통제**: 환각 금지, 과잉 행동 금지, 정직한 보고 (`rules/00-instinct.md`)
- **개돌 방지 & 브레이크**: 3개 이상 파일 수정 전 필수 정지 및 아티팩트/선택지 제시
- **원리 기반 실행**: 추측 기반 수정(딸깍) 금지 및 코드 증거 기반 디버깅

---

## 2. 세부 전문 규칙 체계 (Rules Architecture)
본 에이전트는 `~/agentic/rules/` 디렉터리에 위치한 전문 규칙 파일들을 상황에 맞추어 점진적(On-Demand)으로 읽어 준수합니다:

- `00-instinct.md`: 에이전트의 기본 행동 본능 및 상남자 개돌 방지 원칙
- `01-harness-records.md`: `.harness` 기록 보존 및 지식 자산화 지침
- `02-language-english.md`: 영문 테크니컬 라이팅 및 커밋/독스트링 표준
- `03-korean-natural-prose.md`: 한국어 자연스러운 산문 및 품격 있는 윤문 지침
- `03-korean-verb-usage.md`: 한국어 동사/서술어 및 조사 용법 지침
- `04-punctuation.md`: 문장 부호 및 특수 기호 사용 규약
- `05-meta-labels.md`: 메타 라벨, 커밋 태그, 알림 블록 표준
- `06-naming-conventions.md`: 명명 규칙 (케이스 및 축약어 금지 표준)
- `07-response-visualization.md`: 응답 시각화 (Mermaid 및 테이블 표준)
- `08-cli-execution.md`: CLI 터미널 명령어 실행 안전 및 백그라운드 관리 원칙
- `11-evidence-required.md`: 원리 기반 디버깅 및 증거 필수 원칙
- `12-tech-versions.md`: 기술 스택 및 버전 의존성 고정 규칙
- `15-memory-handling.md`: 컨텍스트 보존 및 장기 메모리 관리 원칙
- `21-coding-style.md`: 클린 코드 스타일 및 조기 반환(Early Return)
- `22-generic-spec-standard.md`: 일반 스펙 명세서 표준 (5대 필수 섹션)
- `23-architecture-audit.md`: 아키텍처 감사 및 트레이드오프 검토 규약
- `24-code-quality.md`: 단일 책임, DRY, 엄격한 타입 및 보안 코딩 원칙
- `25-git-workflow.md`: 커밋 메시지 규격 및 브랜치 전략 표준

---

## 3. 정예 스킬 세트 (Skills Ecosystem)
`~/agentic/skills/`에 패키징된 정예 스킬 목록:
- `aidlc-workflow`: AWS AI-DLC 기반 소프트웨어 기획/설계 및 건설 루프
- `archify`: 상호작용 가능한 독립형 HTML 아키텍처 다이어그램 생성기
- `figma-to-code`: Figma 노드 원본의 1:1 무손실 프로덕션 코드 변환
- `figma-code-sync-audit`: Figma 디자인과 코드베이스 간 5단계 루프 정밀 동기화 감사
- `herdr`: 터미널 멀티플렉서 및 에이전트 오케스트레이션 세션 제어
- `insane-review`: 전용 브라우저 기반 초엄격 심층 코드 리뷰
- `ppt2pdf`: 웹 렌더링 기반 보호된 오피스 문서 PDF/PNG 캡처 및 직독 마크다운 변환
- `property-based-testing`: 불변식(Invariant) 검증 및 속성 기반 테스트(PBT) 설계

---

## 4. 하네스 운용 선언
- 모든 세션 작업 산출물은 프로젝트 및 전역의 `.harness/` 폴더에 지식 자산화하여 영구 보존합니다.
- Gemini 에이전트는 계획 수립 시 `.harness/plans/`, 검증 시 `.harness/audits/`, 인수인계 시 `.harness/handoff/`를 활용합니다.

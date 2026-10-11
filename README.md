# agy-rule

> **Gemini / Antigravity 조련술, 울타리 체결술 및 엔지니어링 표준 통합 룰셋**  
> Threads [@vesperchant (김선달)](https://www.threads.com/@vesperchant)의 Gemini/Antigravity 조련술, 바이브 코딩 핸디캡 룰, 에이전틱 성역(Agentic Sanctuary) 설계 및 AWS AI-DLC 글로벌 엔지니어링 가이드라인을 완전 융합한 Antigravity 단일 원천(SSOT) 룰셋 & 스킬 에코시스템입니다.

---

## 🌟 핵심 철학 (Core Principles)

본 룰셋은 AI 에이전트의 '무지성 개돌'과 '추측 기반 수정(딸깍)'을 원천 차단하고, 장기 지속 가능한 에이전틱 협업 환경을 구축하는 것을 목표로 합니다.

### 1. 개돌 방지 및 브레이크 체결 (Anti-Rush & Checkpoint Protocol)
* **상남자 개돌 모드 금지**: 복잡한 작업이나 다단계 플랜을 사용자 확인 없이 처음부터 끝까지 무작정 혼자 달려나가지 않습니다.
* **필수 정지점 (Mandatory Checkpoints)**:
  * 아키텍처/설계 상의 중요한 분기점이나 트레이드오프가 발생하는 지점
  * 요구사항이 모호하거나 여러 구현 방향이 갈리는 지점
  * 3개 이상의 핵심 파일 또는 200줄 이상의 대규모 코드 변경이 예상되는 지점
  * 데이터 파괴, 패키지 삭제, 되돌리기 어려운 시스템 환경 변경 직전
* **브레이크 동작**: 위 상황에서는 즉시 멈추고 현황, 판단 근거, 옵션을 명확히 정리하여 사용자에게 확인을 받습니다.

### 2. 원리 기반 실행 원칙 (Principle-First / Anti-딸깍)
* **추측 기반 수정 금지**: 코드를 수정하기 전 반드시 관련 파일의 실제 구조와 동작 원리를 직접 읽고 검증합니다.
* **증거 기반 디버깅**: "알아서 다 해주겠지" 식의 생성을 지양하고, 시스템 로그, 에러 메시지, 코드베이스 증거를 바탕으로 원인을 규명한 뒤 최소한의 정확한 변경을 적용합니다.
* **실행 후 검증**: 파일 수정 후에는 반드시 린트, 빌드, 테스트 또는 실행 결과를 확인하여 정상 동작을 검증합니다.

### 3. 정제된 소통과 질문 매너 (Thoughtful Inquiry)
* **생각 없는 질문 지양**: 답이 뻔한 질문, 사소한 단답형 질문으로 사용자의 맥락을 끊지 않습니다.
* **구조화된 선택지 제시**: 사용자에게 결정을 요청할 때는 반드시 **(1) 문제 상황과 맥락, (2) 구체적인 선택지(권장 표기 포함), (3) 각 옵션의 장단점 및 트레이드오프, (4) 기타(직접 서술)**를 갖추어 질문합니다.

### 4. 계획 및 아티팩트 운용 (Planning & Artifact Mode)
* **Planning Mode 적극 활용**: 4단계 이상의 복잡한 기능 구현이나 리팩토링은 실행 전 단계별 계획(`[ ]` 체크리스트)을 수립하고 공유합니다.
* **Artifact 리뷰 준수**: 계획, 설계서, 주요 변경 명세는 구조화된 아티팩트(Artifact)로 작성하여 사용자가 검토할 수 있도록 합니다.
* **컨텍스트 격리**: 대규모 리서치나 병렬 검증 태스크는 전문 서브에이전트에게 위임하여 메인 컨텍스트를 맑게 유지합니다.

### 5. 하네스 자산화 규약 (Harness Knowledge Assetization)
* 일회성 채팅으로 끝내지 않고, 계획·감사·의사결정 이력을 `.harness/` 디렉터리에 영구 자산으로 기록·보존합니다.

### 6. 엄격한 품질 & 보안 베이스라인 (Quality & Baseline Security)
* **민감정보 보호**: 로그 및 메시지에 토큰, 비밀번호, PII 노출 금지
* **입력 검증 & 인젝션 차단**: 파라미터화 쿼리 강제, 타입 안전성 유지
* **불변식 사고(Invariant Thinking)**: Round-Trip(역변환 복원), 크기/원소 보존 불변식, 멱등성 검증

---

## 📁 디렉터리 구조 (Directory Structure)

```text
agy-rule/
├── install.sh                   # 원클릭 환경 통합 및 자동 링크 배포 스크립트
├── GEMINI.md                    # 에이전틱 성역 최상위 진입점 (@include 정의)
├── RULES.md                     # 상시 로드 룰셋 (개돌 방지, 원리 기반, 한국어 윤문, 품질/보안)
├── rules/                       # 전문 세부 규칙 모음 (18종 완비)
│   ├── distilled/               # 핵심 규칙 초압축 증류본 모음
│   ├── 00-instinct.md           # 행동 본능 및 브레이크 체크포인트 규약
│   ├── 01-harness-records.md    # 하네스(.harness) 자산화 기록 규칙
│   ├── 02-language-english.md   # 영문 테크니컬 라이팅 및 커밋/독스트링 표준
│   ├── 03-korean-natural-prose.md # 자연스러운 한국어 산문 및 번역투 배제
│   ├── 03-korean-verb-usage.md  # 한국어 동사 및 조사 활용 규칙
│   ├── 04-punctuation.md        # 문장 부호 및 특수 기호 사용 규약
│   ├── 05-meta-labels.md        # 메타 라벨, 커밋 태그, 알림 블록 표준
│   ├── 06-naming-conventions.md # 명명 규칙 (케이스 및 축약어 금지 표준)
│   ├── 07-response-visualization.md # 응답 시각화 (Mermaid 및 테이블 표준)
│   ├── 08-cli-execution.md      # CLI 안전 실행 및 백그라운드 관리
│   ├── 11-evidence-required.md  # 코드 증거 기반 디버깅 원칙
│   ├── 12-tech-versions.md      # 기술 스택 및 버전 의존성 고정 규칙
│   ├── 15-memory-handling.md    # 메모리 및 컨텍스트 격리 관리
│   ├── 21-coding-style.md       # 클린 코드 스타일 및 조기 반환(Early Return)
│   ├── 22-generic-spec-standard.md # 일반 스펙 명세서 표준 (5대 필수 섹션)
│   ├── 23-architecture-audit.md # 아키텍처 감사 및 트레이드오프 검토 규약
│   ├── 24-code-quality.md       # DRY, 단일 책임, 엄격한 타입 및 보안 표준
│   └── 25-git-workflow.md       # Git 커밋 메시지 규격 및 브랜치 전략
├── skills/                      # 정예 에이전트 스킬 생태계 (8종 완비)
│   ├── aidlc-workflow/          # AWS AI-DLC 수명주기 소프트웨어 기획/건설
│   ├── archify/                 # 반응형 대화형 HTML 아키텍처 다이어그램 생성기
│   ├── figma-to-code/           # Figma 노드 1:1 무손실 프로덕션 코드 변환
│   ├── figma-code-sync-audit/   # Figma 디자인 vs 코드 5단계 정밀 싱크 감사
│   ├── herdr/                   # 터미널 멀티플렉서 및 에이전트 세션 제어
│   ├── insane-review/           # 전용 Chromium 격리 기반 초엄격 심층 코드 리뷰
│   ├── ppt2pdf/                 # 오피스 문서 브라우저 렌더링 PDF 변환 & 직독 마크다운
│   └── property-based-testing/  # 불변식(Invariant) 검증 및 속성 기반 테스트(PBT)
└── .harness/                    # 에이전트 자산화 8대 디렉터리
    ├── audits/                  # 정합성 검사 및 감사 보고서
    ├── handoff/                 # 작업 인수인계 및 체크포인트
    ├── history/                 # 주요 작업 이력 및 컨텍스트 로그
    ├── memory/                  # 장기 지속 메모리 및 도메인 지식
    ├── metrics/                 # 성능 지표 및 측정 기록
    ├── plans/                   # 마일스톤 및 아키텍처 계획서
    ├── pull-request/            # PR 설명서 및 변경 로그
    └── walkthroughs/            # 작업 검증 및 실행 가이드
```

---

## 🚀 설치 및 일원화 동기화 (Quick Start)

### 1. 성역(Sanctuary) 저장소 클론 및 동기화
어떤 환경(로컬 PC, OCI 클라우드 인스턴스, EC2 등)이든 단 한 번의 명령으로 전체 룰과 스킬이 자동 연동됩니다:

```bash
# 1. 성역 저장소 클론
git clone https://github.com/gimso2x/agy-rule.git ~/agentic

# 2. 원클릭 동기화 스크립트 실행
cd ~/agentic && ./install.sh
```

`install.sh` 스크립트가 다음 작업을 자동으로 수행합니다:
* `~/.agents/rules/` 에 18종 전문 규칙 자동 심볼릭 링크
* `~/.agents/skills/` 및 `~/.gemini/config/skills/` 에 8종 스킬 자동 심볼릭 링크
* `~/.gemini/config/GEMINI.md` 및 `~/GEMINI.md` 에 전역 엔트리포인트 자동 구성
* `.harness/` 8대 디렉터리 자산화 보장

---

## 📜 라이선스 (License)

[MIT License](LICENSE)

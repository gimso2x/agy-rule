# agy-rule

> **Gemini / Antigravity 조련술 및 울타리 체결 룰셋**  
> Threads [@vesperchant (김선달)](https://www.threads.com/@vesperchant)의 Gemini/Antigravity 조련술, 바이브 코딩 핸디캡 룰, 에이전틱 성역(Agentic Sanctuary) 설계를 기반으로 표준화한 Antigravity 룰셋 및 하네스 템플릿입니다.

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
* **구조화된 선택지 제시**: 사용자에게 결정을 요청할 때는 반드시 **(1) 문제 상황과 맥락, (2) 구체적인 선택지(권장 표기 포함), (3) 각 옵션의 장단점 및 트레이드오프**를 갖추어 질문합니다.

### 4. 계획 및 아티팩트 운용 (Planning & Artifact Mode)
* **Planning Mode 적극 활용**: 4단계 이상의 복잡한 기능 구현이나 리팩토링은 실행 전 단계별 계획을 수립하고 공유합니다.
* **Artifact 리뷰 준수**: 계획, 설계서, 주요 변경 명세는 구조화된 아티팩트(Artifact)로 작성하여 사용자가 검토할 수 있도록 합니다.
* **컨텍스트 격리**: 대규모 리서치나 병렬 검증 태스크는 전문 서브에이전트에게 위임하여 메인 컨텍스트를 맑게 유지합니다.

### 5. 하네스 자산화 규약 (Harness Knowledge Assetization)
* 일회성 채팅으로 끝내지 않고, 계획·감사·의사결정 이력을 `.harness/` 디렉터리에 영구 자산으로 기록·보존합니다.

### 6. 자연스러운 한국어 산문 및 윤문
* 번역투, 기계 번역 찌꺼기, 조사의 어색한 생략, 불필요한 외래어 남발을 배제하고 단단하고 정갈한 한국어 문장을 구사합니다.

---

## 📁 디렉터리 구조 (Directory Structure)

```text
agy-rule/
├── GEMINI.md                    # 에이전틱 성역 최상위 진입점 (@include 정의)
├── RULES.md                     # 상시 로드 룰셋 (개돌 방지, 원리 기반, 한국어 윤문)
├── rules/                       # 전문 세부 규칙 모음
│   ├── 00-instinct.md           # 행동 본능 및 브레이크 체크포인트 규약
│   ├── 01-harness-records.md    # 하네스(.harness) 자산화 기록 규칙
│   ├── 03-korean-natural-prose.md # 자연스러운 한국어 산문 및 번역투 배제
│   ├── 03-korean-verb-usage.md  # 한국어 동사 및 조사 활용 규칙
│   ├── 08-cli-execution.md      # CLI 안전 실행 및 백그라운드 관리
│   ├── 11-evidence-required.md  # 코드 증거 기반 디버깅 원칙
│   └── 15-memory-handling.md    # 메모리 및 컨텍스트 격리 관리
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

## 🚀 설치 및 사용법 (Installation & Usage)

### 1. 전역 성역(Sanctuary)으로 클론
```bash
git clone https://github.com/gimso2x/agy-rule.git ~/agentic
```

### 2. Antigravity 워크스페이스 또는 전역 설정에 연동

#### 방법 A: 워크스페이스 레벨 연동 (`GEMINI.md`)
작업 중인 프로젝트 루트의 `GEMINI.md`에 아래 한 줄을 추가합니다:
```markdown
@/home/ubuntu/agentic/GEMINI.md
```
*(참고: 사용자 홈 경로에 맞게 절대 경로를 지정합니다.)*

#### 방법 B: 전역 설정 레벨 연동 (`~/.gemini/config/GEMINI.md`)
모든 워크스페이스에 기본 적용하려면 전역 파일에 등록합니다:
```bash
mkdir -p ~/.gemini/config
echo "@/home/ubuntu/agentic/GEMINI.md" >> ~/.gemini/config/GEMINI.md
```

#### 방법 C: Antigravity 디스커버리 규칙 경로 연동 (`~/.agents/rules/`)
Antigravity 2.0 규칙 디스커버리를 사용하려면 심볼릭 링크 또는 복사합니다:
```bash
mkdir -p ~/.agents/rules
cp ~/agentic/rules/*.md ~/.agents/rules/
```

---

## 📊 정합성 및 컨텍스트 예산 검증 결과

* **규칙 총량**: 최상위 재귀 확장 시 **120라인 / 8,305바이트**
* **Antigravity 규칙 예산(24KB)** 대비 **34.6%** 수준으로, 컨텍스트 절삭(Truncation) 위험 없이 안전하게 주입됩니다.
* 모든 단일 규칙 파일은 30라인 이하 / 1.5KB 이하로 최적화되었습니다.

---

## 📜 라이선스 (License)

[MIT License](LICENSE)

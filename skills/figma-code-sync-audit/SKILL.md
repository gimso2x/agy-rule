---
name: figma-code-sync-audit
description: >-
  Use this skill when auditing, comparing, or synchronizing an existing codebase implementation against
  Figma designs (nodes/URLs). It governs 5-stage loop audit (inline character overrides, multi-state diff,
  layout sizing, library default conflicts, interactive component states & auxiliary actions), 9-category node extraction,
  visibility exclusions, and Storybook test-isolation leak prevention.
---

# Figma-Code Sync & Audit Engineering Skill (5-Stage Loop & 9-Category Edition)

This skill governs the systematic comparison, discrepancy detection, and 1:1 synchronization between existing production code and Figma designs via the **5-Stage Loop Engineering Audit**, **9-Category Node Extraction**, and **Active Route Verification**.

---

## 🔒 Non-Negotiable Invariants (동기화 불변식)

1. **Visibility Exclusion Invariant (숨김 노드/레이어 배제 불변식 - CRITICAL)**:
   - Figma 노드 트리 탐색 시 `visible: false`인 노드 및 **상위 부모 체인 중 하나라도 `visible: false`인 하위 트리는 디자인에서 미사용/숨김 처리된 요소**이다.
   - `visible: false`인 텍스트, 뱃지, 레이아웃, 컴포넌트는 누락이나 불일치로 판정하지 않으며, **코드베이스에 절대로 추가해서는 안 된다**.
   - 단, 상위 노드의 특정 불릿이나 아이콘이 숨겨져 있더라도 하위 자식 노드에 별도의 가시적인 요소(`visible: true`)가 존재할 수 있으므로, 하위 자식 개별의 `visible` 속성을 독립적으로 검사해야 한다.

2. **Orphan Code Inspection Invariant (죽은 코드 수정 방지 불변식)**:
   - 라우트에서 import하지 않는 고립된 컴포넌트(Orphan)를 수정하면 화면에 아무런 변경도 반영되지 않는다.
   - 수정 전 반드시 `setup-context.py` 또는 라우트 파일(`src/app/**/page.tsx`)의 실제 import 체인을 거슬러 올라가 **실제 브라우저에 렌더링되는 컴포넌트**를 확인하고 수정한다.

3. **Source of Truth (카피 100% 일치 불변식)**:
   - 모든 텍스트 카피, 라벨, 약관, 안내 문구의 정본은 Figma 최신 노드의 가시적인 `characters` 값이다.
   - 단, 상위 노드뿐 아니라 토글/탭 상태별 하위 노드까지 재귀적으로 전수 대조해야 한다.

4. **Inline Character Overrides Invariant (인라인 스타일 오버라이드 불변식 - Loop 1)**:
   - 한 텍스트 블록 안에서 특정 단어(예: 브랜드명, 강조 문구)만 색상/굵기가 다른 경우, 단순 텍스트 매칭에 그치지 않고 `characterStyleOverrides` 및 `styleOverrideTable`을 전수 조사한다.
   - 오버라이드가 감지되면 반드시 `<span className={...}>`로 분리하여 해당 색상/스타일을 1:1 일치시킨다.

5. **Multi-State Differential Invariant (상태별 시각 불변식 - Loop 2)**:
   - 아코디언, 탭, 드롭다운 등 상태형 컴포넌트는 `Default/Closed`와 `Open/Active` 상태의 `fills`와 `strokes`를 1:1 diff 비교한다.
   - 예: 평소 질문은 섹션 회색 배경(`fills: []` / 투명), 확장 시에만 흰색 카드 배경(`fills: #FFFFFF`)으로 전환되는 디자인을 정확히 추출하여 반영한다.

6. **Layout Sizing & Responsive Invariant (너비/줄바꿈 불변식 - Loop 3)**:
   - 피그마 Auto Layout에서 `layoutGrow: 1` 또는 `layoutAlign: STRETCH`(`sizingH: FILL`)인 자식 요소는 코드에서 반드시 `flex: 1` 또는 `width: 100%`를 적용한다.
   - 모바일(360px)과 데스크톱(640px+)의 텍스트 개행(`\n`) 차이를 분석하여, 데스크톱 화면에서 `span { display: block }`로 인한 부자연스러운 강제 2줄 개행을 방지한다.
   - **버튼 및 인라인 액션 요소의 강제 2줄 개행 방지 (`white-space: nowrap`)**:
     - 버튼/라벨에 고정 `width`를 부여하면 CSS `box-sizing: border-box`로 인해 내부 텍스트 가용 너비(width - padding - border)가 텍스트 자체 너비보다 1~2px 작아져 글자가 쪼개지는 현상(예: "결제전" + "표" 2줄 개행)이 발생한다.
     - 모든 버튼, 인라인 뱃지, 액션 요소는 반드시 **`white-space: nowrap; word-break: keep-all;`**을 기본 선언하고, 피그마 HUG 스펙에 맞게 `min-width` 기반으로 너비를 선언해야 한다.

7. **Library Default Conflict Invariant (라이브러리 기본값 충돌 불변식 - Loop 4)**:
   - Ground UI(`Accordion`, `Tab` 등) 또는 외부 라이브러리가 기본으로 탑재한 배경색(예: 기본 흰색 `var(--color-gray-0)`)이 부모 컨테이너(예: 회색 `#F4F5F6`)와 충돌하는지 사전 검증하고, CSS Module에서 명시적으로 오버라이드한다.

8. **Interactive Component State Variant Invariant (인터랙티브 상태 일치 불변식 - Loop 5)**:
   - 피그마의 `Button`, `Input`, `Select` 등 인터랙티브 인스턴스는 `componentProperties.State` (`Default`, `Hover`, `Disabled`, `Focused`) 프로퍼티를 갖는다.
   - 코드베이스에서 임의의 비즈니스 이유(예: "미연동", "목업 비활성")로 시안의 `State: Default`인 버튼에 `disabled` 속성을 임의 부여하거나, 반대로 시안의 `State: Disabled`인 요소에 `disabled`를 누락해서는 안 된다.
   - 시안이 `Default` 상태인 경우 완전히 활성화된 스타일(텍스트, 보더, hover 효과)을 유지하고, `disabled`에 의해 글자색/테두리가 바래지는 시각적 불일치를 방지한다.

9. **Auxiliary Action & Inline Element Invariant (행/셀 내부 부속 액션 전수 감사 불변식 - Loop 5)**:
   - 테이블 행(`dl > div`, `tr`, `Card`)의 값(`dd`, `td`) 영역 내부에 주 데이터 텍스트 외에 우측/좌측에 부속된 보조 액션 요소(예: `결제전표`, `영수증`, `수정`, `조회`, `복사`, `계좌번호 입력`)가 존재하는지 반드시 전수 감사한다.
   - 주 텍스트("하나", "100,000원")만 확인하고 우측 부속 인라인 액션 버튼을 빠뜨리거나 비활성화하는 실수를 원천 방지한다.

10. **Test Isolation & Side-Effect Cleanup (테스트 격리 불변식)**:
    - `sessionStorage`나 `localStorage`를 조작하는 컴포넌트의 Storybook 스토리나 단위 테스트는 실행 종료 시(`play` 함수 끝 또는 `afterEach`) 반드시 스토리지를 클린업(`removeItem` / `clear`)해야 한다.

11. **In-Place Modification (제자리 수정 원칙)**:
    - 변경 시 `*_new.ts`, `*_copy.tsx` 등의 임시 파일을 생성하지 않고, 대상 파일에 제자리(in-place) 반영한다.

---

## ⚡ Sync & Audit Toolchain & Workflow

### 도구 체인
- `scripts/resolve-storybook-node.py`: 스토리북 URL 또는 Story ID로부터 Figma Node ID, 화면 ID, 컴포넌트/스타일 파일 경로 자동 해석
- `scripts/setup-context.py`: 프로젝트 라이브러리(Ground), 토큰, 활성 라우트(`src/app/**/page.tsx`) 스캔
- `scripts/figma_loop_audit.py`: **5-Stage Loop 자동 분석** (인라인 오버라이드, 멀티 스테이트, 레이아웃 사이징, 라이브러리 충돌, **인터랙티브 상태 & 부속 액션**)
- `scripts/extract-figma-node.py`: 피그마 노드의 9대 카테고리(Text, Fill, Stroke, Radius, Shadow, Layout, Sizing, Props 등) 종합 추출 (Ancestor Hidden 필터링 내장)

---

### Step 1. 프로젝트 및 라우트 컨텍스트 확인 (Orphan 방지)
수정 대상 컴포넌트가 활성 라우트에 속해 있는지 스캔:
```bash
python3 ~/.gemini/config/skills/figma-code-sync-audit/scripts/setup-context.py
```

### Step 2. 5-Stage Loop 자동화 스크립트 실행
Figma URL 또는 로컬 노드 캐시 JSON을 넘겨 5단계 루프 검사를 수행한다:
```bash
# 온라인 검사
python3 ~/.gemini/config/skills/figma-code-sync-audit/scripts/figma_loop_audit.py \
  "https://www.figma.com/design/:file_key/:title?node-id=:node_id"

# 또는 오프라인/캐시된 JSON 검사
python3 ~/.gemini/config/skills/figma-code-sync-audit/scripts/figma_loop_audit.py --json /path/to/node.json
```

### Step 3. 루프별 결과 리포트 분석
- **[Loop 1]** 🚨 Inline Style Override: `characterStyleOverrides` 구간별 단어 및 컬러 확인 → `<span>` 분리.
- **[Loop 2]** 🚨 Multi-State Discrepancy: `Open` vs `Closed`, `Active` vs `Inactive` 배경/보더 차이 확인.
- **[Loop 3]** 📌 Layout Sizing: `fill` 자식 요소의 `flex: 1` 누락 여부 및 모바일/데스크톱 개행 차이 확인.
- **[Loop 4]** ℹ️ Background Contrast: 비-흰색 부모 컨테이너에서의 라이브러리 기본 흰색 충돌 여부 확인.
- **[Loop 5]** 🚨 Interactive Component State & Auxiliary Action:
  - 데이터 컨테이너(행/셀) 내부의 부속 인라인 액션 버튼(결제전표, 수정 등) 누락 여부 확인.
  - 인스턴스 `State` (`Default` vs `Disabled`) 일치 여부 확인 (코드에서 임의로 `disabled` 처리되어 시각적으로 바래지지 않았는지 검증).
- **[Visibility Check]** ⚠️ 보고된 차이점 중 피그마 원본에서 `visible: false`로 처리된 요소가 있다면 **반영하지 않고 건너뜀**.

### Step 4. 제자리 수정 (In-Place Fix)
- 라우트 import 체인 상의 실제 컴포넌트 파일(`*.tsx`), 스타일(`*.module.scss`), 상수(`constants/*.ts`)를 직접 수정.

### Step 5. 게이트웨이 전수 검증 (Verification Gate)
반드시 아래 4대 검증을 순차적으로 실행하여 모두 통과함을 확인:
```bash
pnpm check      # Biome 린트/포맷
pnpm typecheck  # TypeScript Strict 타입 검사
pnpm test:run   # Unit + Playwright Storybook a11y/interaction
pnpm build      # Next.js 프로덕션 standalone 빌드
```

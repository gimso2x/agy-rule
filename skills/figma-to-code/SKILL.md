---
name: figma-to-code
description: >-
  Use this skill when converting Figma design nodes (via Figma MCP, Dev Mode, or JSON node dumps)
  into production-ready web components, ensuring 1:1 visual fidelity, design token alignment,
  and instance override validation.
skill_version: 2.0.0
---

# Figma-to-Code Fidelity & Engineering Skill (6-Phase Edition)

Figma 원본 디자인을 무손실로 추출하고, 현재 프로젝트의 토큰·디자인 시스템(Ground DS)·아키텍처 규칙을 증거(evidence)로 삼아 1:1 픽셀 완성도의 프론트엔드 코드로 변환 및 검증합니다.

---

## 🔒 Non-Negotiable Invariants (절대 준수 불변식)

1. **Visibility Exclusion Invariant (가장 치명적인 착시 및 유령 요소 방지 - CRITICAL)**:
   - 피그마 노드 탐색 시 `visible: false`인 노드 및 **상위 조상 체인 중 하나라도 `visible: false`인 하위 트리 전체**는 디자인에서 미사용/숨김 처리된 요소이다.
   - 인스턴스 오버라이드(`node.overrides`)에서 `visible: false`로 처리된 요소(닫기 버튼, 서브타이틀, 배지 등)도 동일하게 비가시 요소다.
   - 이러한 요소는 mock 데이터, 텍스트, JSX 노드로 **절대로 렌더링하거나 코드베이스에 추가하지 않는다**.

2. **Top-Level Viewport & Section vs Card Surface (배경색 계층 분리 불변식 - B1/B6)**:
   - TEXT 노드만 보고 UI를 구현하지 않는다 (`Anti-Pattern B1`).
   - 바깥 섹션 프레임의 배경색(`$color-gray-50`, `$color-green-50` 등)과 안쪽 카드의 흰색 표면(`$color-gray-0` + `$shadow-sm`)을 하나의 레이어로 뭉개지(flatten) 않고 명확히 분리한다.

3. **Orphan Code Inspection Invariant (죽은 코드 수정 방지 - B10)**:
   - 아무도 import하지 않는 orphan 컴포넌트를 수정하지 않는다.
   - 반드시 대상 라우트(`src/app/**/page.tsx`)로부터 실사용 import 체인을 거슬러 올라가 실제 렌더링되는 컴포넌트를 확인한 후 수정한다.

4. **Design System & Token First (Ground DS 준수 - B4/B5)**:
   - 임의의 Hex 코드(`#123456`)나 픽셀(px) 하드코딩을 일체 금지한다.
   - `@proptier/ground`의 기성 컴포넌트(`TextButton`, `Badge`, `Chips`, `Flex`, `Text` 등)를 우선 사용하며, `.d.ts`를 확인하여 유효한 prop만 전달한다.
   - spacing 토큰은 **4px 기본 배수**(`$spacing-4`, `$spacing-8`, `$spacing-12`, `$spacing-16`, `$spacing-20`...)만 사용하며, 존재하지 않는 `$spacing-2`, `$spacing-6`을 지어내지 않는다.

5. **Screen Modality & Shell Hierarchy (팝업 형태 왜곡 방지)**:
   - 기존 파일명이 `*modal*`이어도 피그마에 `App Header`(뒤로가기 + 타이틀 + 닫기) 또는 뷰포트 전체 구조가 있다면 플로팅 카드가 아닌 **풀사이즈(`FullscreenOverlay` / `Page`)** 구조로 구현한다.

6. **Auto Layout Sizing Fidelity (반응형 깨짐 방지 - B9c)**:
   - 피그마의 `layoutSizingHorizontal/Vertical` (`FILL`, `HUG`, `FIXED`)을 준수한다.
   - `FILL` → `flex: 1` / `width: 100%`, `HUG` → auto / fit-content, `FIXED` → 정밀 치수.

---

## ⚡ 6-Phase Engineering Workflow

```
[Phase 1: SETUP]      프로젝트 환경 스캔 (Ground 버전, 토큰, feature, 라우트)
       ↓
[Phase 2: EXTRACT]    피그마 9대 카테고리 추출 (스크립트 및 에셋 다운로드)
       ↓
[Phase 3: PROPOSE]    구현 방침 및 매핑 계획 수립 (Ground 컴포넌트 & 토큰)
       ↓
[Phase 4: GENERATE]   Div Soup 압축 및 속성 교차표 대조 코드 생성 (In-Place)
       ↓
[Phase 5: AUDIT]      체크리스트 기반 1:1 전수 대조 (17개 검증 항목 & visual-diff)
       ↓
[Phase 6: HANDOFF]    린트/타입/테스트 게이트 통과 및 완료 보고
```

---

### Phase 1: SETUP — 프로젝트 맥락 확보
프로젝트 루트에서 스캐너를 실행하여 토큰 지원 여부, Ground 컴포넌트, 활성 라우트를 자동 탐색합니다:
```bash
python3 ~/.gemini/config/skills/figma-to-code/scripts/setup-context.py --project-root .
```
- `design.mode`: `token-aware` 또는 `raw` 모드 결정
- `design.tokens`: DESIGN.md로부터 추출된 컬러, 타이포, 간격, 반경, 그림자 토큰 역매핑 테이블 확보
- `routes`: 대상 컴포넌트가 `src/app/**/page.tsx` 실사용 import 체인 상에 위치하는지 검증 (Orphan 방지)
- Ground DS의 실제 `.d.ts` export 선언 확인

---

### Phase 2: EXTRACT — 피그마 전체 Evidence 수송
Figma REST API 또는 MCP 도구를 통해 원본 데이터를 무손실로 확보합니다.

#### 1. 노드 트리 데이터 추출 (무손실 JSON 및 요약 텍스트)
```bash
# JSON 무손실 추출 (document.json)
python3 ~/.gemini/config/skills/figma-to-code/scripts/extract-figma-node.py \
  --format json "<FIGMA_URL>" > /tmp/document.json

# 9대 카테고리 요약 및 가시성 텍스트 추출
python3 ~/.gemini/config/skills/figma-to-code/scripts/extract-figma-node.py \
  --format text "<FIGMA_URL>"
```
- **9대 카테고리**: 1.Text, 2.Background, 3.Layout, 4.Radius/Shadow, 5.Stroke, 6.Component, 7.Image/Icon, 8.Sizing, 9.Variant-Props
- **Ancestors Hidden 필터링**: 숨김 처리된 레이어와 그 자식들은 렌더링 대상에서 원천 제외

#### 2. 에셋 및 SVG 아이콘 자동 추출
```bash
python3 ~/.gemini/config/skills/figma-to-code/scripts/extract-figma-assets.py \
  "<FIGMA_URL>" --output-dir ./src/assets/icons
```
- 복합 심볼이나 다중 레이어 일러스트는 수동 SVG 대신 Figma Image API로 온전한 에셋 파일로 내려받아 사용

---

### Phase 3: PROPOSE — 구현 방침 및 매핑 계획 수립
추출된 evidence를 바탕으로 구현 계획을 정리합니다:
- Ground 컴포넌트 매핑 (예: `INSTANCE | Text Button` → `<TextButton size="sm">`)
- 색상/간격/반경 토큰 매핑
- 피그마 수치와 DS 기본 토큰 간의 근사(Approximation) 사유 명시
- 모호한 구조나 컴포넌트 선택지가 있는 경우 사용자에게 확인

---

### Phase 4: GENERATE — 클린 시맨틱 코드 생성
디자이너의 불필요한 중첩 래퍼(Div Soup)를 압축하고, 승인된 매핑에 맞춰 코드를 제자리(in-place) 생성합니다.

#### 1. 시맨틱 스켈레톤 도출 (선택적 가속 도구)
```bash
python3 ~/.gemini/config/skills/figma-to-code/scripts/simplify-figma-tree.py \
  /tmp/document.json
```
- 불필요한 빈 Spacer Frame 제거 및 부모 간격(`gap`)으로 전환
- React JSX + 깔끔한 `.module.scss` 스켈레톤 자동 도출

#### 2. 속성 교차표 대조 (`resources/generate-gate-template.md`)
- Fill, Stroke, Spacing, Radius, Shadow를 1:1 대조 확인
- `visible: false` 노드가 포함되지 않았는지 재확인

---

### Phase 5: AUDIT — 1:1 전수 자가 대조
`resources/checklist.md` 및 `resources/anti-patterns.md`를 바탕으로 자가 검증을 수행합니다:
- [ ] 텍스트 카피가 띄어쓰기, 줄바꿈까지 100% 일치하는가?
- [ ] 안티패턴(B1~B10)에 해당하는 위반 사항이 없는가?
- [ ] 모바일 뷰포트(360px)에서 수평 오버플로 없이 렌더링되는가?
- [ ] 수정한 파일이 실제 라우트 import 체인에 속하는가?

#### 픽셀 단위 시각 diff (필요 시)
`visual-diff/` 도구를 활용하여 Figma 원본 렌더링과 로컬 dev 서버 화면 간의 픽셀 단위 일치도를 검증할 수 있습니다.

---

### Phase 6: HANDOFF — 게이트웨이 검증 & 보고
프로젝트 표준 검증 명령어를 실행하여 모두 통과한 뒤 사용자에게 보고합니다:
```bash
pnpm check      # Biome 린트/포맷
pnpm typecheck  # TypeScript 타입 검사
pnpm test:run   # 테스트 통과
pnpm build      # 프로덕션 빌드 성공
```
보고 시 의도적 근사 결정 사항과 변경 내역을 요약 전달합니다.

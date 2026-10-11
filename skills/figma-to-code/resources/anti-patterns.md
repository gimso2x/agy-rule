# Anti-Patterns: Figma → UI 구현 금지 패턴

> AUDIT 단계에서 각 항목의 금지 이유와 대안을 확인한다. 호스트 디자인 시스템이나 저장소 이름을 이 문서에 고정하지 않는다.

## A. AI-slop 패턴 (범용 디자인 품질)

### A1. 타이포그래피

- ❌ DON'T: 시스템 폰트로 충분한데 근거 없이 웹폰트를 추가한다.
- ❌ DON'T: 명확한 브랜드 이유 없이 세 개 이상의 폰트 패밀리를 로드한다.
- ❌ DON'T: 의도적 캡션을 제외하고 모바일 본문을 지나치게 작게 설정한다.
- ✅ DO: 호스트의 승인된 폰트와 의미 있는 텍스트 스타일을 사용한다.
- ✅ DO: 모든 텍스트의 크기·두께·행간·자간을 Figma raw evidence로 감사한다.

### A2. 색상과 장식

- ❌ DON'T: 보라-파랑/보라-분홍 그라디언트, 무지개 테두리, 장식용 메쉬/블롭을 근거 없이 사용한다.
- ❌ DON'T: 글래스모피즘과 블러를 화면 전체의 기본 스타일로 적용한다.
- ❌ DON'T: 대비를 확인하지 않은 회색 텍스트나 색상만으로 의미를 전달하는 상태를 만든다.
- ✅ DO: 기능적 목적이 확인된 페인트만 구현하고 접근성 대비를 검사한다.
- ✅ DO: 색상은 호스트의 승인된 semantic token/API로 resolution한다.

### A3. 레이아웃과 공간

- ❌ DON'T: 중첩 카드를 무근거로 추가하거나 모든 섹션을 동일한 카드 그리드로 만든다.
- ❌ DON'T: 고정 데스크톱 너비, 임의 `min-height`, 근거 없는 간격 그리드를 사용한다.
- ✅ DO: Figma의 중첩 레이어·absolute bounding box·auto-layout sizing을 보존한다.
- ✅ DO: 모바일부터 반응형으로 구현하고 최소 지원 폭에서 동작을 확인한다.
- ✅ DO: 반복되는 형제 간에는 margin보다 레이아웃의 gap 규칙을 우선한다.

### A4. 모션

- ❌ DON'T: 모든 요소에 바운스/linear easing, 800ms를 넘는 전환, 레이아웃 속성 애니메이션을 적용한다.
- ❌ DON'T: 정지할 수 없는 자동 재생이나 과도한 동시 애니메이션을 만든다.
- ✅ DO: transform/opacity 중심의 짧은 모션과 `prefers-reduced-motion`을 지원한다.

### A5. 컴포넌트와 상호작용

- ❌ DON'T: hover만으로 동작하거나 키보드·터치·포커스 대안이 없는 인터랙션을 만든다.
- ❌ DON'T: 아이콘-제목-설명 카드만을 모든 콘텐츠의 유일한 패턴으로 사용한다.
- ✅ DO: 호스트 컴포넌트의 실제 상태/접근성 API를 확인하고 보이는 포커스 상태를 제공한다.

## B. Fidelity·Context·Policy 패턴 (DS 독립)

### B1. TEXT-only 추출

- ❌ DON'T: TEXT 노드만 읽고 배경, 이미지, INSTANCE, VECTOR, effects를 추측한다.
- ✅ DO: 전체 레이어 트리와 각 노드의 raw fills/strokes/effects를 추출한다.

### B2. 레이어/페인트 손실

- ❌ DON'T: wrapper와 surface를 합치거나 paint의 보이지 않는 항목·unknown fields·알파·블렌드·gradient/image 데이터를 버린다.
- ✅ DO: 원본 document는 verbatim JSON으로 저장하고 derived index는 대체물로 취급하지 않는다.

### B3. 추출과 구현 정책 혼합

- ❌ DON'T: extractor가 token 후보, DS 선택, CSS literal 허용 여부를 추론하거나 JSON에 permission을 기록하게 한다.
- ✅ DO: `extraction evidence → resolution capability → host implementation policy`를 분리한다.

### B4. 근거 없는 컴포넌트 매핑

- ❌ DON'T: INSTANCE 이름만으로 컴포넌트·variant·state를 추측하거나 실제 API 확인 없이 props를 발명한다.
- ✅ DO: 호스트 DS/API의 실제 타입과 semantic/state fit을 확인하고, 맞지 않으면 기존 앱 컴포넌트나 승인된 semantic 구현을 선택한다.

### B5. 치수·반응형 추측

- ❌ DON'T: padding/gap만으로 width·height를 정하거나 `FILL/HUG/FIXED`, constraints를 무시한다.
- ✅ DO: absoluteBoundingBox와 sizing/constraints를 함께 확인하고 고정 요소만 exact size로 둔다.

### B6. 효과·가시성 오인

- ❌ DON'T: shadow와 layer/background blur를 같은 CSS 효과로 처리하거나 숨김 부모의 자식을 렌더링 기준에 포함한다.
- ✅ DO: effect type·visible·offset·spread·color를 구분하고 effective visibility를 트리 전체에 전파한다.

### B7. GENERATE gate 우회

- ❌ DON'T: 추출 직후 proposal·resolution·host policy 확인 없이 구현을 시작하거나 raw px/hex를 자동 허용으로 해석한다.
- ✅ DO: 애매한 매핑은 선택지와 제약을 먼저 기록하고 승인 후 생성한다. 호스트가 literal을 금지하면 DS/API 또는 승인된 로컬 구현을 사용한다.

### B8. Orphan 수정과 검증 생략

- ❌ DON'T: 활성 import/route chain 밖의 코드를 수정하거나 렌더링·computed style·pixel diff 없이 완료를 선언한다.
- ✅ DO: 실제 사용 경로를 확인하고 host lint/test/build, raw audit, dimension mismatch와 content mismatch를 각각 기록한다.

## C. HTML 구조 및 시맨틱 품질 (Div Soup 방지 & 레이어 압축)

### C1. Designer Div-Soup (무의미한 래퍼 프레임 남발)
- ❌ DON'T: Figma의 정렬용·오토레이아웃용 중첩 프레임(`Frame 12`, `AutoLayout 5`, 빈 그룹)을 1:1로 전부 `<div>`로 옮겨 5~10중 중첩 껍데기를 만든다.
- ✅ DO: 배경색·테두리·패딩이 없고 레이아웃 제약만 있는 단일 자식 껍데기 프레임은 자식 컴포넌트의 클래스(`flex`, `w-full` 등)로 병합(Flatten)하여 최소 깊이의 DOM 트리를 구성한다.

### C2. Spacer Frame의 DOM 오염
- ❌ DON'T: 디자이너가 간격을 띄우기 위해 배치한 빈 박스/스페이서 프레임을 `<div className="h-[24px]">` 형태의 빈 DOM 요소로 남긴다.
- ✅ DO: 부모 Flex/Grid의 `gap` 또는 형제 요소의 `margin`으로 변환하고 빈 껍데기 태그는 완전히 소거한다.

### C3. 시맨틱 태그 무시 (무지성 div 도배)
- ❌ DON'T: 클릭 가능한 버튼, 링크, 헤더, 내비게이션 바, 뱃지를 전부 `div onClick`이나 `div`로 도배한다.
- ✅ DO: 클릭 요소는 `<button>` 또는 `<a>`, 상단바는 `<header>`, 목록은 `<ul>`/`<li>`, 텍스트 위계에 따라 `<h1~h3>`, `<p>`, `<label>`을 올바르게 매핑한다.

### C4. 색상·토큰 임의 추측 (Color Hallucination)
- ❌ DON'T: Figma의 raw RGBA 값을 보면서 임의의 Tailwind 색상(`bg-slate-700`, `text-gray-500` 등)을 감으로 찍어 맞추거나 알파 투명도를 누락한다.
- ✅ DO: 프로젝트의 실제 테마 토큰(`tailwind.config`, CSS 변수)과 정확히 대조하여 매핑하고, 일치하는 토큰이 없으면 임의 추측 대신 정확한 Hex/RGBA(`text-[#...]`)를 보존한다.
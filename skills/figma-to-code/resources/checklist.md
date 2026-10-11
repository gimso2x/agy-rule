# AUDIT 체크리스트 — Figma → UI

> GENERATE 후 HANDOFF 전에 실행한다. 각 항목은 통과 또는 의도적 근사(사유와 raw 근거 명시)여야 한다.

## 1. Extraction evidence

- [ ] 전체 document/node tree를 추출했는가(TEXT-only 아님)?
- [ ] `document`가 JSON-safe verbatim이고 derived index가 대체물이 아님을 확인했는가?
- [ ] 각 node의 `id/type/name/path/visibility`와 hidden ancestor semantics를 보존했는가?
- [ ] `fills/strokes/effects/backgroundColor`의 type/visible/raw color floats/opacity/blend/gradient/image/unknown fields를 보존했는가?
- [ ] bbox/layout/padding/gap/sizing/constraints/radius/componentId/properties/variables 및 TEXT characters/style raw를 보존했는가?
- [ ] INSTANCE, VECTOR, image, component variant를 별도 검토했는가?

## 2. Layer fidelity

- [ ] wrapper, card/surface, badge, border, overlay를 flat list로 합치지 않았는가?
- [ ] 섹션 배경과 child surface를 노드별 fills/background로 분리했는가?
- [ ] shadow와 layer/background blur, visible paint와 hidden node를 구분했는가?
- [ ] padding/gap만으로 치수를 추측하지 않고 `absoluteBoundingBox.width × height`와 sizing/constraints를 비교했는가?

## 3. Three-axis gate

각 속성에 다음 열을 채운다.

| Figma raw evidence | Exact token/API resolution | Host-policy-compliant implementation | Rendered raw audit |
|---|---|---|---|
| 원본 field/path와 값 | `exact`/`partial`/`unavailable`을 key-preserving하게 기록 | host rule·DS API·기존 앱·app-local·semantic 순서와 선택 근거 | computed style/pixel diff로 실제 값 확인 |

- [ ] exact/partial/unavailable 어느 상태에서도 token key를 삭제하거나 새 token을 추측하지 않았는가?
- [ ] raw evidence만으로 raw px/hex literal 허용을 추론하지 않았는가?
- [ ] host design-system/API 타입 선언과 import 규칙을 확인했는가?
- [ ] Figma와 host dimension이 다르면 `dimension-mismatch`를 별도 실패로 기록했는가?
- [ ] 정규화가 필요하면 명시적 flag와 non-empty reason, original/normalized dimensions를 기록했는가?
- [ ] 해결 불가/근사 항목을 PROPOSE gate에서 드러내고 승인했는가?

## 4. Rendered audit와 접근성

- [ ] computed raw font/color/spacing/radius/shadow/opacity가 Figma evidence와 일치하는가?
- [ ] 모든 텍스트의 characters/style과 semantic heading/label이 맞는가?
- [ ] 이미지 alt, icon-only label, 키보드/터치/visible focus, reduced motion을 검증했는가?
- [ ] 대비 4.5:1 일반 텍스트, 3:1 큰 텍스트/UI 경계 기준을 확인했는가?
- [ ] active runtime route와 import chain에서 실제 사용 코드를 수정했는가(orphan 아님)?

## 5. Visual diff

- [ ] 글로벌 도구 경로 `~/my-wiki/gjc-config/skills/figma/visual-diff`에서 실행했는가? 로컬 skill 경로를 새로 만들지 않았는가?
- [ ] registry 또는 안전한 ad-hoc selector를 사용했는가? project/name slug와 output containment를 검증했는가?
- [ ] 기본 physical dimensions exact 비교에서 equal dimensions/ratio는 pass, content mismatch는 fail인가?
- [ ] threshold를 근거 없이 올리지 않았는가? mismatch 원인을 missing layer, color/spacing, font, timing 등으로 분리했는가?
- [ ] `report.json`과 diff image를 보존했는가?

## 6. Host verification commands

- [ ] 저장소가 지정한 lint 명령을 exit 0으로 실행했는가?
- [ ] 저장소가 지정한 unit/integration test 명령을 exit 0으로 실행했는가?
- [ ] 저장소가 지정한 type-check/build 명령을 exit 0으로 실행했는가?
- [ ] global extractor/visual unit test와 Python compile도 실행했는가?

## 7. Handoff

- [ ] node-id/화면과 구현 파일 경로, active import chain을 기록했는가?
- [ ] 세 축 표와 rendered audit, dimension/crop/scale, 의도적 근사를 전달했는가?
- [ ] generated cache/output/log가 global skill ignore 규칙에 걸리는지 확인했는가?
- [ ] 커밋/푸시 없이 작업 트리와 영향 범위를 보고했는가?

## AUDIT 결과 템플릿

```text
## AUDIT 결과 — [node-id / 화면명] ([날짜])

- Extraction: [통과/근사/실패]
- Resolution: [통과/근사/실패]
- Implementation policy: [통과/근사/실패]
- Rendered audit: [통과/근사/실패]
- Visual diff: [report 경로와 mismatch/dimension 결과]
- Host commands: [명령과 exit code]
- Global path/ignore: [검증 결과]
- 근사·실패 사유: [raw evidence, 선택지, 다음 조치]
```

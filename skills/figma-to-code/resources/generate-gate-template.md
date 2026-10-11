# GENERATE Gate — 4-axis property matrix

코드 생성 전에 각 중요한 FRAME/INSTANCE/VECTOR property를 다음 네 축으로 대조한다. raw 값은 구현 허가가 아니다.

```markdown
| Figma raw evidence | Exact token/API resolution | Host-policy-compliant implementation | Rendered raw audit |
|---|---|---|---|
| path: `...`<br>property: `fills`<br>value: `{...}` | `exact` / `partial` / `unavailable`<br>capability key + source | chosen API/component/style<br>host rule reference<br>approximation + approval | computed/pixel result<br>pass or mismatch reason |
```

## 기입 규칙

1. **Figma raw evidence**: JSON `document`/`index.nodes`의 실제 path와 property를 적는다. `fills`, `strokes`, `effects`, `backgroundColor`, bbox, sizing, padding, gap, radius, characters, style, properties, variables를 포함한다.
2. **Resolution**: category별 exact capability를 key와 근거로 적는다. 없으면 `partial` 또는 `unavailable`을 적고 key를 삭제하지 않는다.
3. **Implementation policy**: host AGENTS/SCSS/import/Server Component/접근성 규칙과 실제 DS/app API에 맞는 선택을 적는다.
4. **Rendered audit**: computed raw style와 pixel report가 Figma raw와 일치하는지 적는다. content mismatch와 dimension mismatch를 분리한다.

## GENERATE 진입 조건

- raw evidence, resolution, policy, rendered audit 열을 모두 채운다.
- raw px/hex가 추출됐다는 사실만으로 token/API 또는 CSS literal permission을 추론하지 않는다.
- host가 literal을 금지하면 compliant DS/API 또는 승인된 app-local semantic implementation을 사용한다.
- exact mapping이 없으면 빈칸을 추측으로 채우지 않고 PROPOSE에서 제약, 근사, 선택지를 공개해 승인받는다.
- hidden subtree는 구현/렌더 audit 대상에서 제외하지만 raw extraction에는 남긴다.
- Figma와 actual physical dimensions가 다르면 기본 비교는 실패한다(`reason=dimension-mismatch`). 명시적 normalization flag와 non-empty reason 없이는 stretch하지 않는다.

## 예시

```markdown
| Figma raw evidence | Exact token/API resolution | Host-policy-compliant implementation | Rendered raw audit |
|---|---|---|---|
| `/Root/Card` · `paddingLeft` · `16` | `exact` · `spacing/card-inline` · host token docs | `Card` API `paddingInline` · host rule R12 | computed `16px` · pass |
| `/Root/Icon` · `fills[0]` · `SOLID`, raw color floats | `unavailable` · no icon-color capability | existing icon component; no guessed literal · approved P-03 | computed color differs · intentional approximation |
| `/Root/Canvas` · bbox `WxH` | n/a | capture viewport from bbox | actual `WxH` differs · `dimension-mismatch` · fail |
```

## 실패 시 조치

| 증상 | 원인 | 조치 |
|---|---|---|
| fill/stroke 색이 다름 | VECTOR/paint raw 누락 또는 API 추측 | 해당 node paint/effect raw를 재추출하고 resolution을 갱신 |
| gap/padding/radius가 다름 | token key 추측 또는 bbox 무시 | exact capability와 layout raw를 대조하고 근사면 gate 승인 |
| effect가 동일한 shadow로 보임 | shadow/blur type 혼동 | type/offset/spread/color를 분리해 구현 |
| dimensions가 다름 | actual을 Figma 크기로 강제 stretch | 기본 실패를 기록하고 명시 normalization reason이 있을 때만 재실행 |
| 구현이 실제 화면에 없음 | orphan 수정 | runtime route와 active import chain을 따라 사용 파일 수정 |

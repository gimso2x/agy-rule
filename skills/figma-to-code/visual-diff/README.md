# 시각 diff 도구 (figma 스킬 자급자족 모듈)

Figma image API로 렌더링한 PNG와 dev 서버 화면 캡처를 **픽셀 단위**로 비교한다.
개별 computed style 검증(SKILL.md §13)이 잡지 못하는 **전체 화면 레벨**의 시각 차이를 잡는다.

> **격리 원칙**: 이 도구는 figma 스킬에 종속된 자급자족 모듈이다.
> 프로젝트 루트의 `package.json` / `.env.example` / `scripts/` 는 건드리지 않는다.
> 의존성은 이 디렉토리의 `package.json` 에만 선언되며, 자체 `node_modules` 을 갖는다.

## 사전 준비 (최초 1회)

```bash
cd ~/my-wiki/gjc-config/skills/figma/visual-diff
pnpm install --ignore-workspace   # sharp, pixelmatch, @playwright/test
                                  # --ignore-workspace 필수: 프로젝트 루트 workspace에 흡수되지 않고
                                  # 이 디렉토리에 격리된 node_modules 을 만든다
pnpm install-browser              # Playwright chromium 바이너리
```

## 실행

```bash
# 전제: 프로젝트 루트에서 dev 서버가 떠 있어야 한다 (pnpm dev)
# 전제: FIGMA_TOKEN 이 현재 셸에 export 되어 있어야 한다
#   export FIGMA_TOKEN=personal-access-token-...

cd ~/my-wiki/gjc-config/skills/figma/visual-diff
pnpm diff                 # config.mjs 의 모든 엔트리
pnpm diff ai-app-web/map-main   # selector `<project>/<name>` 으로 필터
```

## 산출물

```
outputs/visual-diff/
  {project}/{name}/
    figma.png       # Figma image API 렌더링
    actual.png      # dev 서버 캡처
    diff.png        # 차이 시각화 (차이 픽셀이 빨강)
    report.json     # { mismatchPixels, totalPixels, mismatchRatio, threshold, passed }
  summary.json      # 전체 실행 요약
```

## 새 화면 추가하기

`config.mjs` 의 `entries` 배열에 엔트리를 추가한다:

```js
{
  project: "ai-app-web",
  name: "broker-detail",
  ownerRepo: "proptier/ai-app-web",
  figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
  figmaNodeId: "1234-5678",          // URL 형식 그대로
  url: "http://localhost:6012/broker/123",
  viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
  threshold: 0.01,                    // 1% 초과 시 fail
  waitSelector: ".broker-screen",     // 비동기 로드 대기 (옵션)
}
```
- `project`/`name`은 lowercase safe slug(`^[a-z0-9][a-z0-9-]{0,62}$`), `ownerRepo`는 `owner/name` 형식 필수. selector는 `<project>/<name>`, output은 `outputs/visual-diff/<project>/<name>/`.

- `viewport`는 Figma 모바일 프레임 치수와 맞춘다 (DESIGN.md iOS mobile 기준).
- `deviceScaleFactor` 와 Figma `scale` 이 일치해야 물리 해상도가 같다.
- `threshold`는 폰트 렌더링·맵 타일 타이밍 차이를 흡수한다. 0(완전 일치)은 비현실적.

## AUDIT 연동

`../resources/checklist.md` §5(Visual diff) 가 이 도구를 AUDIT 절차로 호출한다.
구현 완료 후 반드시 `pnpm diff` 를 돌려 `passed: true` 를 확인할 것.

## mismatch 해석 가이드

| 상황                             | 판정                                 |
| -------------------------------- | ------------------------------------ |
| 폰트 힌팅/안티앨리어싱 미세 차이 | 의도적 근사 (사유 명시)              |
| 맵 타일 로딩 타이밍              | 의도적 근사 (재실행으로 확인)        |
| 색/간격/치수 토큰 매핑 실수      | **진짜 오류** → GENERATE 단계로 복귀 |
| 누락된 배경·섀도                 | **진짜 오류** → GENERATE 단계로 복귀 |
| 잘못된 컴포넌트 variant          | **진짜 오류** → GENERATE 단계로 복귀 |
| 디자인에만 있는 장식 요소        | 의도적 근사 (사유 명시)              |

#!/usr/bin/env node
/**
 * 시각 diff 파이프라인 entrypoint (스킬 자급자족 도구).
 *
 * 사용법 (스킬 디렉토리 안에서):
 *   pnpm diff                 # config.mjs 의 모든 엔트리 실행
 *   pnpm diff map-main        # name 으로 필터
 *   node run.mjs              # pnpm 없이 직접 실행
 *
 * 사전 조건:
 *   1. `pnpm install` (이 스킬 디렉토리에서 — 프로젝트 루트가 아님)
 *   2. `pnpm install-browser` (최초 1회 — Playwright chromium)
 *   3. dev 서버가 떠 있을 것 (프로젝트 루트에서 `pnpm dev`, 포트는 config.mjs 참조)
 *   4. FIGMA_TOKEN 환경변수 (현재 셸로만 제공; 파일·로그에 기록 금지)
 *
 * 산출물: outputs/visual-diff/{name}/{figma,actual,diff}.png + report.json
 *         outputs/visual-diff/summary.json
 *
 * 설계 원칙: 이 도구는 figma 스킬에 종속된 자급자족 모듈다.
 * 프로젝트의 package.json / .env.example / scripts/ 는 건드리지 않는다.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { configVersion, entries } from "./config.mjs";
import { fetchFigmaPng } from "./fetch-figma.mjs";
import { captureDevPng } from "./capture-dev.mjs";
import { compareImages } from "./compare.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
// 산출물은 스킬 내부 outputs/<project>/<name>/ 에. 프로젝트 outputs/ 와 섞이지 않는다.
const OUT_ROOT = path.resolve(__dirname, "outputs", "visual-diff");

const SAFE_SLUG_RE = /^[a-z0-9][a-z0-9-]{0,62}$/;

// --- CLI 파싱: `<project>/<name>` 또는 `<name>`(현재 프로젝트) 필터 ---
const filterArg = process.argv[2];
const targets = filterArg
  ? entries.filter((e) => `${e.project}/${e.name}` === filterArg || e.name === filterArg)
  : entries;
if (targets.length === 0) {
  console.error(
    `⚠️  일치하는 엔트리가 없다: ${filterArg}\nconfig.mjs 의 selector 목록: ${entries
      .map((e) => `${e.project}/${e.name}`)
      .join(", ")}`,
  );
  process.exit(2);
}
// safe slug + output containment: project/name이 slug가 아니면 load-time fail (path traversal 차단).
for (const e of entries) {
  if (!SAFE_SLUG_RE.test(e.project) || !SAFE_SLUG_RE.test(e.name)) {
    console.error(`❌ 잘못된 selector slug: ${e.project}/${e.name} (safe slug ^[a-z0-9][a-z0-9-]{0,62}$ 필요)`);
    process.exit(2);
  }
}

// --- dev 서버 헬스체크 ---
async function checkDevServer(url) {
  try {
    const res = await fetch(url, { method: "GET" });
    // 5xx 는 캡처해봤자 에러 페이지 → 의미 없음. 4xx 까지는 서버가 정상 응답한 것으로 본다.
    return { up: res.status < 500, status: res.status };
  } catch {
    return { up: false, status: null }; // 연결 자체 실패 = 서버가 안 떠있음
  }
}

const firstUrl = targets[0].url;
const { up, status } = await checkDevServer(firstUrl);
if (!up) {
  if (status === null) {
    console.error(
      `⚠️  dev 서버(${firstUrl})에 연결할 수 없다.\n먼저 프로젝트 루트에서 \`pnpm dev\` 를 실행한 뒤 다시 시도하라.`,
    );
  } else {
    console.error(
      `⚠️  dev 서버(${firstUrl})가 HTTP ${status} 응답을 반환한다.\n` +
        `캡처해도 에러 페이지만 찍히므로 의미 없다. 먼저 해당 경로가 정상 렌더링되도록 고칠 것\n` +
        `(흔한 원인: NEXT_PUBLIC_NAVER_MAP_CLIENT_ID 등 env 누락).`,
    );
  }
  process.exit(1);
}

// --- 메인 루프 ---
const summary = { configVersion, generatedAt: new Date().toISOString(), entries: [] };
let anyFailed = false;

for (const entry of targets) {
  const dir = path.join(OUT_ROOT, entry.project, entry.name);
  const figmaPath = path.join(dir, "figma.png");
  const actualPath = path.join(dir, "actual.png");
  const diffPath = path.join(dir, "diff.png");
  const reportPath = path.join(dir, "report.json");

  console.log(`\n▶ ${entry.name}  (node ${entry.figmaNodeId} ↔ ${entry.url})`);

  try {
    const scale = entry.viewport.deviceScaleFactor ?? 1;
    console.log(`  • Figma PNG fetch (scale=${scale}) ...`);
    await fetchFigmaPng({
      fileKey: entry.figmaFileKey,
      nodeId: entry.figmaNodeId,
      scale,
      outPath: figmaPath,
    });

    console.log(`  • dev 서버 캡처 ...`);
    await captureDevPng({
      url: entry.url,
      viewport: entry.viewport,
      waitSelector: entry.waitSelector,
      fullPage: entry.fullPage ?? false,
      clipSelector: entry.clipSelector,
      actions: entry.actions ?? [],
      outPath: actualPath,
    });

    console.log(`  • 픽셀 diff ...`);
    const report = await compareImages({
      figmaPath,
      actualPath,
      diffPath,
      reportPath,
      threshold: entry.threshold,
      cropTop: entry.cropTop ?? 0,
      cropBottom: entry.cropBottom ?? 0,
      scaleFactor: entry.viewport.deviceScaleFactor ?? 1,
    });
    // per-entry report.json에 project/ownerRepo/configVersion provenance 추가
    report.project = entry.project;
    report.ownerRepo = entry.ownerRepo;
    report.configVersion = configVersion;
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));

    const pct = (report.mismatchRatio * 100).toFixed(2);
    const verdict = report.passed ? "✅ PASS" : "❌ FAIL";
    console.log(
      `  ${verdict}  mismatch ${report.mismatchPixels}/${report.totalPixels} (${pct}%, 임계 ${(entry.threshold * 100).toFixed(2)}%)`,
    );
    console.log(`  산출물: ${dir}`);

    if (!report.passed) anyFailed = true;
    summary.entries.push({
      name: entry.name,
      project: entry.project,
      ownerRepo: entry.ownerRepo,
      configVersion,
      ...report,
      diffPath: path.relative(process.cwd(), diffPath),
    });
  } catch (err) {
    anyFailed = true;
    console.error(`  ❌ 오류: ${err.message}`);
    summary.entries.push({
      name: entry.name,
      project: entry.project,
      ownerRepo: entry.ownerRepo,
      configVersion,
      error: err.message,
      passed: false,
    });
  }
}

summary.allPassed = !anyFailed;
await fs.mkdir(OUT_ROOT, { recursive: true });
await fs.writeFile(path.join(OUT_ROOT, "summary.json"), JSON.stringify(summary, null, 2));

console.log(
  `\n${anyFailed ? "❌ 일부 엔트리 실패" : "✅ 전체 통과"} — ${path.relative(process.cwd(), OUT_ROOT)}/summary.json`,
);
process.exit(anyFailed ? 1 : 0);

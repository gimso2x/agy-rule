/**
 * Playwright chromium 으로 dev 서버 화면을 캡처해 PNG로 저장.
 *
 * - 뷰포트를 Figma 모바일 프레임 치수 + deviceScaleFactor로 설정해
 *   Figma 이미지(scale=N)와 동일 물리 해상도를 맞춘다.
 * - Client-side hydration (SSR bailout) 후 콘텐츠가 보일 때까지 대기.
 * - networkidle + waitSelector + 추가 안정화 delay로 타이밍 문제 완화.
 */
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

/**
 * @param {object} args
 * @param {string} args.url       dev 서버 URL
 * @param {{width:number, height:number, deviceScaleFactor:number}} args.viewport
 * @param {string} [args.waitSelector]  캡처 전까지 추가로 기다릴 셀렉터
 * @param {string} args.outPath   저장할 PNG 경로
 * @param {string} [args.clipSelector]  풀페이지 대신 이 셀렉터 영역만 캡처 (옵션)
 * @param {boolean} [args.fullPage=false]  스크롤 가능한 긴 페이지(예: broker)는 true로 전체 캡처
 * @param {Array<{type:string, role?:string, name?:string, text?:string, selector?:string, ms?:number, timeout?:number}>} [args.actions]
 */
async function runCaptureActions(page, actions = []) {
  for (const action of actions) {
    switch (action.type) {
      case "click":
        if (action.role && action.name) {
          await page.getByRole(action.role, { name: action.name }).click();
        } else if (action.selector) {
          await page.locator(action.selector).click();
        } else if (action.text) {
          await page.getByText(action.text, { exact: action.exact ?? false }).click();
        }
        break;
      case "scroll":
        if (action.selector) {
          await page.locator(action.selector).scrollIntoViewIfNeeded();
        } else if (action.y != null) {
          await page.evaluate((y) => window.scrollTo(0, y), action.y);
        }
        break;
      case "waitFor":
        await page.waitForSelector(action.selector, { timeout: action.timeout ?? 10000 });
        break;
      case "wait":
        await page.waitForTimeout(action.ms ?? 500);
        break;
      default:
        break;
    }
  }
}

export async function captureDevPng({
  url,
  viewport,
  waitSelector,
  outPath,
  clipSelector,
  fullPage = false,
  actions = [],
}) {
  await fs.mkdir(path.dirname(outPath), { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: {
      width: viewport.width,
      height: viewport.height,
    },
    deviceScaleFactor: viewport.deviceScaleFactor ?? 1,
  });
  const page = await context.newPage();

  try {
    // networkidle까지 대기 (SSR bailout + client hydration 포함)
    await page.goto(url, { waitUntil: "networkidle", timeout: 15000 });

    // Client-side hydration 완료 대기:
    // 1) SSR bailout이 발생해도 #app-shell 내부에 실제 콘텐츠가 생길 때까지 기다림
    // 2) waitSelector가 있으면 우선 사용, 없으면 공통 콘텐츠 셀렉터로 fallback
    const contentSelector = waitSelector ?? "#app-shell, main, .app-screen, article";
    try {
      await page.waitForSelector(contentSelector, { timeout: 10000 });
    } catch {
      // 셀렉터 미발견 시에도 캡처 진행 (빈 페이지면 diff가 크게 드러남)
    }

    // 추가 안정화 대기: 폰트 로딩, transition, 애니메이션 완료
    await page.waitForTimeout(1500);

    if (actions.length > 0) {
      await runCaptureActions(page, actions);
      await page.waitForTimeout(500);
    }

    if (clipSelector) {
      const el = await page.$(clipSelector);
      if (el) {
        await el.screenshot({ path: outPath });
      } else {
        await page.screenshot({ path: outPath, fullPage });
      }
    } else {
      await page.screenshot({ path: outPath, fullPage });
    }
    return outPath;
  } finally {
    await context.close();
    await browser.close();
  }
}

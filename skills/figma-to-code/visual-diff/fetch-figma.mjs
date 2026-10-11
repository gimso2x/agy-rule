/**
 * Figma REST image API로 노드를 PNG로 렌더링해 다운로드한다.
 *
 * 흐름:
 *   1. GET /v1/images/{fileKey}?ids={nodeId}&format=png&scale=2
 *      → 응답 body에 signed S3 URL이 들어있음 (짧은 수명).
 *   2. signed URL에서 PNG 바이트를 받아 outPath에 저장.
 *
 * 인증: `X-Figma-Token: $FIGMA_TOKEN` 헤더. FIGMA_TOKEN이 없으면 에러로 종료.
 * signed URL 자체는 토큰 없이도 다운로드 가능 (URL에 자격 증명이 포함됨).
 */
import fs from "node:fs/promises";
import path from "node:path";
import { normalizeNodeId } from "./config.mjs";

/**
 * @param {object} args
 * @param {string} args.fileKey  Figma file key
 * @param {string} args.nodeId   URL 형식 (`3513-155842`) 또는 API 형식
 * @param {number} args.scale    렌더링 배율 (dev deviceScaleFactor와 일치시킬 것)
 * @param {string} args.outPath  저장할 PNG 경로
 */
export async function fetchFigmaPng({ fileKey, nodeId, scale, outPath }) {
  const token = process.env.FIGMA_TOKEN;
  if (!token) {
    throw new Error(
      "FIGMA_TOKEN 환경변수가 설정되지 않았다. 권한 있는 토큰을 현재 셸 환경으로만 제공하라. 토큰을 파일·로그·대화에 기록하지 않는다.",
    );
  }

  const apiNodeId = normalizeNodeId(nodeId);
  const apiUrl = new URL(`https://api.figma.com/v1/images/${fileKey}`);
  apiUrl.searchParams.set("ids", apiNodeId);
  apiUrl.searchParams.set("format", "png");
  apiUrl.searchParams.set("scale", String(scale));

  // 1. image API 호출 → signed URL 획득
  const apiRes = await fetch(apiUrl, {
    headers: { "X-Figma-Token": token },
  });
  if (!apiRes.ok) {
    const body = await apiRes.text();
    throw new Error(`Figma image API 실패 (${apiRes.status}): ${body.slice(0, 300)}`);
  }
  const apiJson = await apiRes.json();
  const signedUrl = apiJson?.images?.[apiNodeId];
  if (!signedUrl) {
    throw new Error(
      `Figma 응답에 노드 ${apiNodeId} 의 이미지 URL이 없다. err=${JSON.stringify(
        apiJson.err ?? null,
      )}`,
    );
  }

  // 2. signed URL에서 PNG 다운로드
  const imgRes = await fetch(signedUrl);
  if (!imgRes.ok || !imgRes.body) {
    throw new Error(`Figma PNG 다운로드 실패 (${imgRes.status})`);
  }
  const buf = Buffer.from(await imgRes.arrayBuffer());

  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, buf);
  return outPath;
}

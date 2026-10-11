/**
 * 두 PNG(figma, actual)를 픽셀 단위로 비교해 diff.png + report.json 산출.
 *
 * cropTop / cropBottom 지원:
 * - Figma 프레임에 시스템 UI(Status Bar, Nav Bar)가 포함된 경우
 *   상단/하단을 크롭해 실제 콘텐츠 영역만 비교한다.
 * - cropTop: 상단에서 제외할 Figma logical px (예: Status Bar = 34)
 * - cropBottom: 하단에서 제외할 Figma logical px (예: Nav Bar = 44)
 * - scaleFactor로 물리 픽셀을 계산해 크롭한다.
 *
 * 정규화: Figma 이미지의 WxH를 기준으로 actual 이미지를 리사이즈한 뒤,
 * cropTop/cropBottom이 있으면 동일 영역을 추출해 비교한다.
 */
import fs from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";
import pixelmatch from "pixelmatch";

/**
 * @param {object} args
 * @param {string} args.figmaPath
 * @param {string} args.actualPath
 * @param {string} args.diffPath
 * @param {string} args.reportPath
 * @param {number} args.threshold
 * @param {number} [args.cropTop]     Figma logical px 단위. 예: Status Bar 34px
 * @param {number} [args.cropBottom]  Figma logical px 단위. 예: Nav Bar 44px
 * @param {number} [args.scaleFactor]  deviceScaleFactor. 기본 2 (mobile retina)
 */
export async function compareImages({
  figmaPath,
  actualPath,
  diffPath,
  reportPath,
  threshold,
  cropTop = 0,
  cropBottom = 0,
  scaleFactor = 2,
  normalizeDimensions = false,
  normalizationReason = "",
}) {
  // 1. Figma 이미지를 기준 치수로
  const figmaMeta = await sharp(figmaPath).metadata();
  const baseWidth = figmaMeta.width;
  const baseHeight = figmaMeta.height;
  if (!baseWidth || !baseHeight) {
    throw new Error(`Figma PNG 메타데이터에서 치수를 읽지 못했다: ${figmaPath}`);
  }

  // 2. cropTop / cropBottom 을 물리 픽셀로 변환
  const cropTopPx = Math.round(cropTop * scaleFactor);
  const cropBottomPx = Math.round(cropBottom * scaleFactor);
  const croppedHeight = baseHeight - cropTopPx - cropBottomPx;

  // 3. actual 치수 읽기 + dimension mismatch 검사 (강제 stretch 금지)
  const actualMeta = await sharp(actualPath).metadata();
  const actualWidth = actualMeta.width;
  const actualHeight = actualMeta.height;
  if (!actualWidth || !actualHeight) {
    throw new Error(`Actual PNG 메타데이터에서 치수를 읽지 못했다: ${actualPath}`);
  }
  const dimensionMismatch = baseWidth !== actualWidth || baseHeight !== actualHeight;
  const wantsNormalize =
    normalizeDimensions === true &&
    typeof normalizationReason === "string" &&
    normalizationReason.trim().length > 0;
  if (dimensionMismatch && !wantsNormalize) {
    const dimReport = {
      reason: "dimension-mismatch",
      figmaWidth: baseWidth,
      figmaHeight: baseHeight,
      actualWidth,
      actualHeight,
      normalizeDimensions: false,
      normalizationReason: null,
      totalPixels: 0,
      mismatchPixels: 0,
      mismatchRatio: 1,
      threshold,
      passed: false,
      generatedAt: new Date().toISOString(),
    };
    await fs.mkdir(path.dirname(reportPath), { recursive: true });
    await fs.writeFile(reportPath, JSON.stringify(dimReport, null, 2));
    return dimReport;
  }

  // 4. 정규화: 치수가 다르면(wantsNormalize) 공통 크기로 stretch, 같으면 resize 없이 decode
  const pipeline = dimensionMismatch
    ? [
        sharp(figmaPath).resize(baseWidth, baseHeight, { fit: "fill" }).ensureAlpha().raw().toBuffer(),
        sharp(actualPath).resize(baseWidth, baseHeight, { fit: "fill" }).ensureAlpha().raw().toBuffer(),
      ]
    : [
        sharp(figmaPath).ensureAlpha().raw().toBuffer(),
        sharp(actualPath).ensureAlpha().raw().toBuffer(),
      ];

  const [figmaFull, actualFull] = await Promise.all(pipeline);

  // 4. crop 적용: raw buffer 에서 필요한 영역만 추출
  const diffWidth = baseWidth;
  const diffHeight = croppedHeight;
  const rowBytes = baseWidth * 4; // RGBA = 4 bytes per pixel
  const figmaCropped = Buffer.alloc(diffWidth * diffHeight * 4);
  const actualCropped = Buffer.alloc(diffWidth * diffHeight * 4);

  for (let y = 0; y < diffHeight; y++) {
    const srcStart = (y + cropTopPx) * rowBytes;
    const dstStart = y * rowBytes;
    figmaFull.copy(figmaCropped, dstStart, srcStart, srcStart + rowBytes);
    actualFull.copy(actualCropped, dstStart, srcStart, srcStart + rowBytes);
  }

  // 5. pixelmatch diff
  const diffBuf = Buffer.alloc(diffWidth * diffHeight * 4);
  const mismatchPixels = pixelmatch(figmaCropped, actualCropped, diffBuf, diffWidth, diffHeight, {
    threshold: 0.1,
    alpha: 0.2,
  });
  const totalPixels = diffWidth * diffHeight;
  const mismatchRatio = mismatchPixels / totalPixels;
  const passed = mismatchRatio <= threshold;

  // 6. diff.png + report.json
  await fs.mkdir(path.dirname(diffPath), { recursive: true });
  await sharp(diffBuf, {
    raw: { width: diffWidth, height: diffHeight, channels: 4 },
  })
    .png()
    .toFile(diffPath);

  const report = {
    width: diffWidth,
    height: diffHeight,
    cropTop: Math.round(cropTopPx),
    cropBottom: Math.round(cropBottomPx),
    totalPixels,
    mismatchPixels,
    mismatchRatio: Number(mismatchRatio.toFixed(6)),
    threshold,
    passed,
    generatedAt: new Date().toISOString(),
  };
  await fs.writeFile(reportPath, JSON.stringify(report, null, 2));

  return report;
}

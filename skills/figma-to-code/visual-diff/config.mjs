/**
 * 시각 diff 비교 대상 설정.
 *
 * - cropTop: Figma 프레임 상단 시스템 UI(Status Bar 등)를 제외하고 비교.
 *   Figma logical px 단위 (scaleFactor에 따라 자동 변환).
 * - cropBottom: 하단 시스템 UI(Nav Bar 등)를 제외하고 비교.
 */

// configVersion 1: project/name/ownerRepo namespace registry (B-후자).
export const configVersion = 1;
const DEFAULT_PROJECT = "ai-app-web";
const DEFAULT_OWNER_REPO = "proptier/ai-app-web";

const rawEntries = [
  {
    name: "map-main",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "3513-155842",
    url: "http://localhost:6012/map",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    waitSelector: ".app-viewport",
  },
  {
    name: "broker-detail",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2804-47837",
    url: "http://localhost:6012/broker/65859",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    fullPage: true,
    waitSelector: ".app-screen",
  },
  {
    name: "redevelopment-reconstruction",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "3653-22017",
    url: "http://localhost:6012/info/redevelopment/redev-001",
    viewport: { width: 360, height: 963, deviceScaleFactor: 2 },
    threshold: 0.01,
    cropTop: 34,
    cropBottom: 44,
    waitSelector: ".app-screen",
  },
  {
    name: "redevelopment-property-tab",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "3653-51911",
    url: "http://localhost:6012/info/redevelopment/redev-001",
    viewport: { width: 360, height: 1017, deviceScaleFactor: 2 },
    threshold: 0.01,
    cropTop: 34,
    cropBottom: 44,
    waitSelector: ".app-screen",
    actions: [
      { type: "click", role: "tab", name: "매물" },
      { type: "wait", ms: 500 },
    ],
  },
  {
    name: "redevelopment-redevelop",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2439-27542",
    url: "http://localhost:6012/info/redevelopment/redev-002",
    viewport: { width: 360, height: 903, deviceScaleFactor: 2 },
    threshold: 0.01,
    cropTop: 34,
    cropBottom: 44,
    waitSelector: ".app-screen",
  },
  {
    name: "redevelopment-progress",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "3660-57262",
    url: "http://localhost:6012/info/redevelopment/redev-001",
    viewport: { width: 360, height: 799, deviceScaleFactor: 2 },
    threshold: 0.01,
    cropTop: 34,
    cropBottom: 44,
    waitSelector: ".app-screen",
    clipSelector: "[data-visual-diff='progress-timeline']",
    actions: [
      { type: "scroll", selector: "text=진행상황" },
      { type: "wait", ms: 300 },
    ],
  },
  {
    name: "redevelopment-stage-guide",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2684-76228",
    url: "http://localhost:6012/info/redevelopment/redev-001",
    viewport: { width: 360, height: 1152, deviceScaleFactor: 2 },
    threshold: 0.01,
    cropTop: 34,
    cropBottom: 44,
    waitSelector: ".app-screen",
    actions: [
      { type: "scroll", selector: "text=진행상황" },
      { type: "wait", ms: 300 },
      { type: "click", role: "button", name: "추진경과 안내" },
      { type: "waitFor", selector: "h2 >> text=추진경과 안내" },
      { type: "wait", ms: 800 },
    ],
  },
  {
    name: "complex-detail-market",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "3031-75379",
    url: "http://localhost:6012/complex/1",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    fullPage: true,
    waitSelector: ".app-screen",
  },
  {
    name: "complex-detail-property",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2457-16995",
    url: "http://localhost:6012/complex/1",
    viewport: { width: 360, height: 956, deviceScaleFactor: 2 },
    threshold: 0.01,
    cropTop: 34,
    cropBottom: 44,
    waitSelector: ".app-screen",
    actions: [
      { type: "click", role: "tab", name: "매물" },
      { type: "wait", ms: 500 },
    ],
  },
  {
    name: "complex-detail-info",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "3086-98049",
    url: "http://localhost:6012/complex/1",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    cropTop: 34,
    cropBottom: 44,
    waitSelector: ".app-screen",
    actions: [
      { type: "click", role: "tab", name: "단지정보" },
      { type: "wait", ms: 500 },
    ],
  },
  {
    name: "complex-detail-broker",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2421-6699",
    url: "http://localhost:6012/complex/1",
    viewport: { width: 360, height: 1218, deviceScaleFactor: 2 },
    threshold: 0.01,
    cropTop: 34,
    cropBottom: 44,
    waitSelector: ".app-screen",
    actions: [
      { type: "click", role: "tab", name: "중개업소" },
      { type: "wait", ms: 500 },
    ],
  },
  {
    name: "property-filter",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2679-36981",
    url: "http://localhost:6012/map",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    waitSelector: ".app-viewport",
    actions: [
      { type: "click", role: "button", name: "필터 열기" },
      { type: "wait", ms: 500 },
    ],
  },
  {
    name: "property-filter-price",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2679-38367",
    url: "http://localhost:6012/map",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    waitSelector: ".app-viewport",
    actions: [
      { type: "click", role: "button", name: "필터 열기" },
      { type: "wait", ms: 400 },
      { type: "click", role: "tab", name: "가격" },
      { type: "wait", ms: 500 },
    ],
  },
  {
    name: "property-filter-area",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2685-86382",
    url: "http://localhost:6012/map",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    waitSelector: ".app-viewport",
    actions: [
      { type: "click", role: "button", name: "필터 열기" },
      { type: "wait", ms: 400 },
      { type: "click", role: "tab", name: "면적" },
      { type: "wait", ms: 500 },
    ],
  },
  {
    name: "property-filter-detail",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2685-89852",
    url: "http://localhost:6012/map",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    waitSelector: ".app-viewport",
    actions: [
      { type: "click", role: "button", name: "필터 열기" },
      { type: "wait", ms: 400 },
      { type: "click", role: "tab", name: "상세" },
      { type: "wait", ms: 500 },
    ],
  },
  {
    name: "property-filter-facility",
    figmaFileKey: "mlrIlS8MnuIJTDTGwmeLsq",
    figmaNodeId: "2685-89152",
    url: "http://localhost:6012/map",
    viewport: { width: 360, height: 780, deviceScaleFactor: 2 },
    threshold: 0.01,
    waitSelector: ".app-viewport",
    actions: [
      { type: "click", role: "button", name: "필터 열기" },
      { type: "wait", ms: 400 },
      { type: "click", role: "tab", name: "기타/시설" },
      { type: "wait", ms: 500 },
    ],
  },
];

// namespace 주입: 각 entry에 project/ownerRepo 보정 (명시 없으면 기본값).
// ponytail: selector = <project>/<name>; output = outputs/visual-diff/<project>/<name>/
export const entries = rawEntries.map((e) => ({
  project: e.project ?? DEFAULT_PROJECT,
  ownerRepo: e.ownerRepo ?? DEFAULT_OWNER_REPO,
  ...e,
}));

export function normalizeNodeId(nodeId) {
  if (nodeId.includes(":")) return nodeId;
  return nodeId.replace(/-/g, ":");
}

#!/usr/bin/env python3
"""ppt2pdf — SharePoint/OneDrive PowerPoint 웹 문서를 ego-browser로 PDF 추출.

ego-browser(ego lite)를 기본 브라우저로 사용하여:
  - 사용자의 로그인된 M365 세션을 그대로 유지
  - 백그라운드 크롬 CDP 포트 의존성 제거
  - PowerPoint/Word 웹 편집기에서 슬라이드/페이지 표면 캡처 → img2pdf 조립.

사용법:
  ppt2pdf.py "<sharepoint-url>" [--out 결과.pdf] [--keep-tab] [--reuse] [--fresh]

전제: ego-browser CLI + python3 + img2pdf
"""
import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image
import numpy as np


def get_work_dirs():
    mnt_c = Path('/mnt/c')
    if mnt_c.is_dir():
        wsl_dir = Path('/mnt/c/tmp/ppt2pdf')
        win_dir = 'C:\\tmp\\ppt2pdf'
    else:
        wsl_dir = Path('/tmp/ppt2pdf')
        win_dir = str(wsl_dir)
    return wsl_dir, win_dir


WORK, WIN_WORK = get_work_dirs()
LOCK_FILE = Path.home() / '.gjc' / 'ppt2pdf.lock'
PORT = int(os.environ.get('PPT2PDF_PORT', '9222'))
PROFILE = Path.home() / '.local' / 'state' / 'mygjc' / 'ppt2pdf-profile'


def log(*a):
    print(*a, flush=True)


def find_ego_browser() -> str | None:
    p = shutil.which('ego-browser')
    if p:
        return p
    local_p = Path.home() / '.local' / 'bin' / 'ego-browser'
    if local_p.is_file() and os.access(local_p, os.X_OK):
        return str(local_p)
    c_users = Path('/mnt/c/Users')
    if c_users.is_dir():
        for exe in sorted(c_users.glob('*/.local/share/ego/active_version_dir/ego-browser.exe')):
            if exe.is_file() and os.access(exe, os.X_OK):
                return str(exe)
    return None


def ego_alive() -> bool:
    ego_bin = find_ego_browser()
    if not ego_bin:
        return False
    try:
        r = subprocess.run([ego_bin, 'nodejs'], input='console.log("ok");',
                           capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def chrome_alive() -> bool:
    return ego_alive()


def pick_chromium(paths):
    for c in reversed(list(paths)):
        if c.is_file() and os.access(c, os.X_OK):
            return c
    return None


def find_chromium():
    ego = find_ego_browser()
    if ego:
        return Path(ego)
    return pick_chromium(sorted(Path.home().glob('.cache/ms-playwright/chromium-*/chrome-linux*/chrome')))


def _pid_bound_to_profile(ps_lines, port, profile_dir):
    expected = '--user-data-dir=%s' % profile_dir
    for line in ps_lines:
        if ((f'--remote-debugging-port={port}' in line or f'--remote-debugging-port {port}' in line)
                and expected in line):
            try:
                return int(line.strip().split(maxsplit=1)[0])
            except (ValueError, IndexError):
                continue
    return None


def profile_bound():
    return 0


def persistent_context(browser):
    contexts = getattr(browser, 'contexts', None)
    if not contexts:
        raise RuntimeError('CDP 브라우저에 기존 persistent context가 없음')
    return contexts[0]


def new_profile_page(browser):
    return persistent_context(browser).new_page()


def slide_total(fr):
    try:
        return fr.evaluate(
            "() => { for (const el of document.querySelectorAll('div,section,span')) {"
            " const t = (el.innerText||'').trim();"
            " const m = t.match(/^슬라이드\\s*\\d+\\s*\\/\\s*(\\d+)$/);"
            " if (m) return +m[1]; } return null; }"
        )
    except Exception:
        return None


def _capture_ppt_slides(pg, fr, work_dir, fresh=False):
    total = slide_total(fr)
    if total is None or not 1 <= total <= 300:
        raise RuntimeError('슬라이드 총 장수 확인 실패 또는 300장 초과')
    seq = []
    surface = fr.locator('[id^="SlideRootViewElement"]:visible')
    selected = fr.locator('[role="option"][aria-selected="true"][aria-posinset]')
    for number in range(1, total + 1):
        target_file = Path(work_dir) / ('slide-%03d.png' % number)
        if not fresh and target_file.exists() and target_file.stat().st_size > 1000:
            seq.append(number)
            log('슬라이드 %d/%d 기존 캡처 재사용' % (number, total))
            continue

        loc = fr.locator('[role="option"][aria-posinset="%d"]' % number)
        try:
            loc.scroll_into_view_if_needed(timeout=3000)
        except Exception:
            pass
        loc.click()
        if selected.get_attribute('aria-posinset') != str(number):
            raise RuntimeError('슬라이드 선택 불일치: expected %d' % number)
        surface.screenshot(path=str(target_file))
        seq.append(number)
        log('슬라이드 %d/%d 캡처 확인' % (number, total))
    return seq


def acquire_run_lock():
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lk = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit('다른 ppt2pdf 실행 중 — 종료 후 재시도 (lock: %s)' % LOCK_FILE)
    return lk


def auto_crop_slide(img_path: Path):
    """주변 회색 배경을 크롭하여 실제 슬라이드(흰색/콘텐츠 영역)만 보존."""
    try:
        im = Image.open(img_path).convert('RGB')
        arr = np.array(im)
        h, w, _ = arr.shape

        # 중앙 행/열 기준으로 회색 캔버스 배경(240~248) 판별
        row = arr[h // 2]
        is_bg_row = (row[:, 0] >= 240) & (row[:, 0] <= 248) & \
                    (row[:, 1] >= 240) & (row[:, 1] <= 248) & \
                    (row[:, 2] >= 240) & (row[:, 2] <= 248)

        # 왼쪽/오른쪽 경계
        min_x = 0
        for x in range(0, w):
            if not is_bg_row[x]:
                min_x = x
                break

        max_x = w
        for x in range(w - 1, -1, -1):
            if not is_bg_row[x]:
                max_x = x
                break

        # 수직 경계
        mid_x = (min_x + max_x) // 2
        col = arr[:, mid_x]
        is_bg_col = (col[:, 0] >= 240) & (col[:, 0] <= 248) & \
                    (col[:, 1] >= 240) & (col[:, 1] <= 248) & \
                    (col[:, 2] >= 240) & (col[:, 2] <= 248)

        min_y = 0
        for y in range(0, h):
            if not is_bg_col[y]:
                min_y = y
                break

        max_y = h
        for y in range(h - 1, -1, -1):
            if not is_bg_col[y]:
                max_y = y
                break

        # 슬라이드 유효 크기 확인 (최소 400x300)
        if (max_x - min_x) > 400 and (max_y - min_y) > 300:
            cropped = im.crop((min_x, min_y, max_x, max_y))
            cropped.save(img_path)
    except Exception as e:
        log(f"자동 크롭 경고 ({img_path.name}): {e}")


def build_ego_script(config: dict) -> str:
    cfg_json = json.dumps(config, ensure_ascii=False)
    return f"""
const CONFIG = {cfg_json};

function log(...args) {{
  process.stderr.write(args.join(" ") + "\\n");
}}

async function capture() {{
  const task = await taskSpace("ppt2pdf");
  let page = null;
  let docTitle = "";

  if (CONFIG.reuse || !CONFIG.url) {{
    const tabs = await task.tabs();
    const targetTab = tabs.find(t =>
      t.url && (t.url.includes("sharepoint.com") || t.url.includes("onedrive") || t.url.includes("officeapps.live.com"))
    ) || tabs.find(t => t.active);

    if (!targetTab) {{
      log("재사용할 SharePoint/OneDrive 탭이 없음 — URL을 인자로 전달하세요.");
      process.exit(1);
    }}
    page = targetTab.label ? task.page(targetTab.label) : await task.adopt(targetTab.page);
    log("기존 탭 재사용:", targetTab.url);
  }} else {{
    page = task.page("p1");
    log("탭 열기:", CONFIG.url);
    await page.goto(CONFIG.url, {{ waitUntil: "domcontentloaded", timeout: 60000 }});
  }}

  // 로그인 및 앱 로드 대기 (최대 5분)
  let ready = false;
  let isWord = false;
  let totalSlides = null;

  for (let i = 0; i < 150; i++) {{
    const currentUrl = await page.url();
    docTitle = await page.title();

    if (currentUrl.includes("login.microsoftonline.com") || docTitle.includes("로그인")) {{
      log("로그인 필요 — ego 브라우저 창에서 M365 로그인 (최대 5분 대기, 완료 시 자동 진행)");
      await page.waitForTimeout(2000);
      continue;
    }}

    const snap = await page.snapshot({{ scope: "full_page" }});
    const match = snap.match(/슬라이드\\s*\\d+\\s*\\/\\s*(\\d+)/);
    if (match) {{
      totalSlides = parseInt(match[1], 10);
      ready = true;
      isWord = false;
      break;
    }}

    if (snap.includes('.Page') || snap.includes('Word')) {{
      ready = true;
      isWord = true;
      break;
    }}

    await page.waitForTimeout(2000);
  }}

  if (!ready) {{
    log("문서 로드 실패 / 지연 — 탭을 확인한 뒤 --reuse 로 재시도하세요.");
    process.exit(1);
  }}

  log(`문서 준비 완료 (${{isWord ? "Word" : "PowerPoint"}}): ${{docTitle}} (총 ${{totalSlides || "?"}}장)`);

  const fs = await import("node:fs/promises");
  await fs.mkdir(CONFIG.workDir, {{ recursive: true }});

  const capturedSlides = [];
  const slideClip = {{ x: 270, y: 120, width: 1420, height: 795 }};

  if (!isWord && totalSlides && totalSlides >= 1) {{
    // 슬라이드 목록 포커스 및 맨 위 1번으로 이동
    log("슬라이드 목록 포커스 및 1번 슬라이드로 이동...");
    try {{
      await page.click('loc=role:listbox[name="슬라이드 목록"]');
    }} catch (_) {{}}

    for (let p = 0; p < 25; p++) {{
      await page.keyboard.press("PageUp");
    }}
    await page.waitForTimeout(1000);

    for (let num = 1; num <= totalSlides; num++) {{
      const numStr = String(num).padStart(3, '0');
      const outPath = `${{CONFIG.workDir}}\\\\slide-${{numStr}}.png`;

      // 기존 파일 재사용 체크
      if (!CONFIG.fresh) {{
        try {{
          const st = await fs.stat(outPath);
          if (st.size > 1000) {{
            log(`슬라이드 ${{num}}/${{totalSlides}} 기존 캡처 재사용`);
            capturedSlides.push(outPath);
            await page.keyboard.press("ArrowDown");
            await page.waitForTimeout(400);
            continue;
          }}
        }} catch (_) {{}}
      }}

      // 캡처
      await page.screenshot({{ path: outPath, clip: slideClip }});
      capturedSlides.push(outPath);
      log(`슬라이드 ${{num}}/${{totalSlides}} 캡처 완료`);

      // 다음 슬라이드로 이동
      if (num < totalSlides) {{
        await page.keyboard.press("ArrowDown");
        await page.waitForTimeout(500);
      }}
    }}
  }}

  if (!CONFIG.keepTab) {{
    try {{
      await page.close();
      log("작업 완료 후 탭 정리 완료");
    }} catch (_) {{}}
  }}

  const result = {{
    success: true,
    title: docTitle || "document",
    docType: isWord ? "word" : "ppt",
    total: capturedSlides.length,
    slides: capturedSlides
  }};
  process.stdout.write("PPT2PDF_RESULT_JSON=" + JSON.stringify(result) + "\\n");
}}

capture().catch((err) => {{
  log("EGO_CAPTURE_FATAL:", err.stack || err.message);
  process.exit(1);
}});
"""


def run_ego_capture(ego_bin: str, config: dict) -> dict:
    script = build_ego_script(config)
    proc = subprocess.Popen(
        [ego_bin, 'nodejs'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    stdout_data, stderr_data = proc.communicate(input=script)

    combined = (stdout_data or '') + '\n' + (stderr_data or '')
    result_line = None
    for line in combined.splitlines():
        if 'PPT2PDF_RESULT_JSON=' in line:
            result_line = line.split('PPT2PDF_RESULT_JSON=', 1)[1].strip()
        elif line.strip():
            log(line)

    if proc.returncode != 0:
        raise RuntimeError(f'ego-browser 캡처 실패 (code {proc.returncode})')
    if not result_line:
        raise RuntimeError('ego-browser 결과 JSON 수신 실패')

    return json.loads(result_line)


def run_ppt2md(md_script: Path, out_pdf: Path) -> None:
    if md_script.exists():
        log('Markdown 변환 시작 (ppt2md)...')
        subprocess.run([sys.executable, str(md_script), str(out_pdf)], check=True)


def main():
    run_lock = acquire_run_lock()
    ap = argparse.ArgumentParser(description='SharePoint PowerPoint → PDF (ego-browser)')
    ap.add_argument('url', nargs='?', help='SharePoint 링크 (생략 시 기존 SharePoint 탭 재사용)')
    ap.add_argument('--out', help='출력 PDF 경로 (기본: ~/decks/<문서명>/<문서명>.pdf)')
    ap.add_argument('--keep-tab', action='store_true', help='작업 후 탭 유지')
    ap.add_argument('--reuse', action='store_true', help='기존 SharePoint 탭 재사용')
    ap.add_argument('--fresh', action='store_true', help='기존 캡처본 재사용 없이 전체 재캡처')
    ap.add_argument('--no-markdown', action='store_true', help='Markdown 생성 생략')
    args = ap.parse_args()

    ego_bin = find_ego_browser()
    if not ego_bin:
        sys.exit('ego-browser CLI 없음 — ego lite 브라우저 설치 및 실행 상태를 확인하세요.')

    WORK.mkdir(parents=True, exist_ok=True)
    if args.fresh or not (args.reuse or not args.url):
        for old in WORK.glob('slide-*.png'):
            try:
                old.unlink()
            except OSError:
                pass

    config = {
        'url': args.url or '',
        'workDir': WIN_WORK,
        'reuse': bool(args.reuse or not args.url),
        'fresh': bool(args.fresh),
        'keepTab': bool(args.keep_tab),
    }

    log('ego-browser 캡처 엔진 구동...')
    result = run_ego_capture(ego_bin, config)

    files = sorted(WORK.glob('slide-*.png'))
    if not files:
        sys.exit('캡처된 슬라이드 이미지 없음')

    # 자동 크롭 적용 (슬라이드 캔버스 정밀화)
    log('슬라이드 이미지 여백 자동 정밀화(crop) 중...')
    for f in files:
        auto_crop_slide(f)

    raw_title = result.get('title') or 'document'
    name = raw_title.replace(' - PowerPoint', '').replace(' - Word', '').replace('.pptx', '').replace('.docx', '').strip()
    name = name.rsplit('.', 1)[0].strip() or 'document'
    safe_name = "".join(c for c in name if c not in '<>:"/\\|?*').strip() or 'document'

    out = Path(args.out) if args.out else Path.home() / 'decks' / safe_name / (safe_name + '.pdf')
    deck_dir = out.parent
    deck_dir.mkdir(parents=True, exist_ok=True)

    for old in deck_dir.glob('slide-*.png'):
        try:
            old.unlink()
        except OSError:
            pass

    log(f'PDF 조립 중 ({len(files)}장)...')
    subprocess.run([sys.executable, '-m', 'img2pdf', *map(str, files), '-o', str(out)], check=True)

    for f in files:
        shutil.copy2(f, deck_dir / f.name)

    log('완료: %d장 → %s (%.1f MB)' % (len(files), out, out.stat().st_size / 1e6))
    log('슬라이드 이미지: %s/slide-*.png (%d장)' % (deck_dir, len(files)))

    try:
        if not args.no_markdown:
            md_script = Path(__file__).resolve().parent / 'ppt2md.py'
            run_ppt2md(md_script, out)
    finally:
        pass


if __name__ == '__main__':
    main()

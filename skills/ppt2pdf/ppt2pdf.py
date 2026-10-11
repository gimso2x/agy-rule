#!/usr/bin/env python3
"""ppt2pdf — SharePoint/OneDrive PowerPoint 웹 문서를 PDF로 추출.

링크 하나로: 전용 WSL Chromium(Playwright 번들, 기본 포트 9223 — PPT2PDF_PORT로
변경, 전용 프로필 ~/.local/state/mygjc/ppt2pdf-profile)에서 새 탭으로 열고,
편집기에서 번호별 슬라이드 표면 캡처 → img2pdf 조립.

M365 로그인은 브라우저 창에서 수동 로그인 — 스크립트가 감지 시 최대 5분 대기하다
완료되면 자동 진행한다. 세션 유지는 "전용 프로필 + 브라우저를 닫지 않는 것"이
유일한 전략이다 (쿠키 스냅샷 백업/복원은 v2.0.0에서 제거).

사용법:
  ppt2pdf.py "<sharepoint-url>" [--out 결과.pdf] [--keep-tab]

전제: python3 + playwright + img2pdf 설치 (pip3 install --user playwright img2pdf)
      Playwright Chromium 설치 (python3 -m playwright install chromium) + WSLg
"""
import argparse
import fcntl
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PORT = int(os.environ.get('PPT2PDF_PORT', '9223'))
CDP = 'http://127.0.0.1:%d' % PORT
PROFILE = Path.home() / '.local' / 'state' / 'mygjc' / 'ppt2pdf-profile'
WORK = Path('/tmp/ppt2pdf')
LOCK_FILE = Path.home() / '.gjc' / 'ppt2pdf.lock'
OLD_COOKIE_FILE = Path.home() / '.gjc' / 'ppt2pdf-cookies.json'  # v1 유물 — 정리용


def log(*a):
    print(*a, flush=True)


def chrome_alive():
    import urllib.request
    try:
        with urllib.request.urlopen(CDP + '/json/version', timeout=2):
            return True
    except Exception:
        return False


def pick_chromium(paths):
    """후보 중 실행 가능한 최신 Chromium 바이너리 하나를 고른다 (없으면 None)."""
    for c in reversed(list(paths)):
        if c.is_file() and os.access(c, os.X_OK):
            return c
    return None


def find_chromium():
    """Playwright 번들 Chromium 탐색 — ~/.cache/ms-playwright/chromium-*/chrome-linux*/."""
    return pick_chromium(sorted(Path.home().glob(
        '.cache/ms-playwright/chromium-*/chrome-linux*/chrome')))


def _pid_bound_to_profile(ps_lines, port, profile_dir):
    """ps -eo pid=,args= 출력에서 우리 포트+프로필을 함께 소유한 브라우저 PID.

    insane-review profile_bound 이식: 포트가 살아 있어도 전용 프로필에 바인딩된
    프로세스가 아니면(외부 브라우저) None → 재사용 거부."""
    expected = '--user-data-dir=%s' % profile_dir
    for line in ps_lines:
        if ((f'--remote-debugging-port={port}' in line
             or f'--remote-debugging-port {port}' in line)
                and expected in line):
            try:
                return int(line.strip().split(maxsplit=1)[0])
            except (ValueError, IndexError):
                continue
    return None


def profile_bound():
    """CDP 포트가 우리 전용 프로필에 바인딩되었는지 /proc-기반(ps) 검증. fail-closed."""
    try:
        r = subprocess.run(['ps', '-eo', 'pid=,args='],
                           capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError) as e:
        sys.exit('CDP 프로필 바인딩 검증 불가: %s' % str(e)[:80])
    pid = _pid_bound_to_profile(r.stdout.splitlines(), PORT, PROFILE)
    if pid is None:
        sys.exit('포트 %d가 ppt2pdf 전용 프로필에 바인딩되지 않음 (외부 브라우저 소유 가능)\n'
                 '그 브라우저를 끄거나 PPT2PDF_PORT로 포트 분리 후 재실행' % PORT)
    return pid


def acquire_run_lock():
    """동시 실행 상호배제(flock) — /tmp/ppt2pdf 슬라이드 레이스 방지.

    insane-review CdpLease 패턴의 축소판. fd는 프로세스 종료 시 해제."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lk = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit('다른 ppt2pdf 실행 중 — 종료 후 재시도 (lock: %s)' % LOCK_FILE)
    return lk


def ensure_browser():
    """전용 WSL Chromium 확보: 살아 있으면(프로필 바인딩 검증 후) 재사용, 아니면 기동."""
    if chrome_alive():
        profile_bound()
        log('기존 Chromium(%d) 재사용 — 세션 유지를 위해 창을 닫지 말 것' % PORT)
        return
    exe = find_chromium()
    if exe is None:
        sys.exit('Playwright Chromium 없음 — python3 -m playwright install chromium 후 재시도')
    if 'DISPLAY' not in os.environ and 'WAYLAND_DISPLAY' not in os.environ:
        if Path('/tmp/.X11-unix/X0').exists():
            os.environ['DISPLAY'] = ':0'
        elif Path('/tmp/.X11-unix/X100').exists():
            os.environ['DISPLAY'] = ':100'
        else:
            os.environ['DISPLAY'] = ':0'
    PROFILE.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(PROFILE, 0o700)
    subprocess.Popen([str(exe), '--remote-debugging-address=127.0.0.1',
                      '--remote-debugging-port=%d' % PORT,
                      '--user-data-dir=%s' % PROFILE,
                      '--no-first-run', '--no-default-browser-check'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(40):
        time.sleep(1)
        if chrome_alive():
            profile_bound()
            log('Chromium 시작됨 (프로필: %s, 포트 %d)' % (PROFILE, PORT))
            return
    sys.exit('Chromium 시작 실패 — WSLg 디스플레이 또는 같은 프로필을 쓰는 기존 브라우저 종료 확인')


def persistent_context(browser):
    """Return the attached browser's existing profile-backed default context."""
    contexts = browser.contexts
    if not contexts:
        raise RuntimeError('CDP 브라우저에 기존 persistent context가 없음')
    return contexts[0]


def new_profile_page(browser):
    """Open a page inside the persistent profile context so M365 cookies survive tab cleanup."""
    return persistent_context(browser).new_page()


def find_app_frame(pg):
    """PowerPoint 또는 Word Online 앱 프레임과 문서 유형('ppt' | 'word')을 반환."""
    for f in pg.frames:
        if 'officeapps.live.com' in f.url and 'ppt.aspx' in f.url:
            return f, 'ppt'
    for f in pg.frames:
        if 'officeapps.live.com' in f.url and ('wordeditorframe.aspx' in f.url or 'wordviewerframe.aspx' in f.url):
            return f, 'word'
        if f.name and 'Word' in f.name:
            return f, 'word'
    for f in pg.frames:
        try:
            if f.evaluate('() => document.querySelectorAll(".Page").length') > 0:
                return f, 'word'
            if f.evaluate('() => document.querySelectorAll("canvas").length') > 0:
                return f, 'ppt'
        except Exception:
            continue
    return None, None


def current_slide(fr):
    """현재 슬라이드 번호 (한국어 '슬라이드 N:'/영어 'Slide N:' 모두). 프레임 분리 등은 None."""
    try:
        return fr.evaluate(
            "() => { for (const el of document.querySelectorAll('div,section,canvas')) {"
            " const t = (el.innerText||'').trim();"
            " const m = t.match(/^슬라이드\\s*(\\d+)\\s*[:/]|^Slide\\s*(\\d+)\\s*[:/]/);"
            " if (m) return +(m[1] || m[2]); } return null; }"
        )
    except Exception:
        return None



def slide_total(fr):
    """편집 모드 상태바 '슬라이드 1/39'에서 총 장수. 없으면 None."""
    try:
        return fr.evaluate(
            "() => { for (const el of document.querySelectorAll('div,section,span')) {"
            " const t = (el.innerText||'').trim();"
            " const m = t.match(/^슬라이드\\s*\\d+\\s*\\/\\s*(\\d+)$/);"
            " if (m) return +m[1]; } return null; }"
        )
    except Exception:
        return None


def wait_doc_ready(pg, fr, doc_type, rounds=30):
    """문서 상호작용 준비 대기. PPT는 슬라이드 번호, Word는 .Page 요소 관측."""
    for _ in range(rounds):
        fr2, dt2 = find_app_frame(pg)
        if fr2 is not None:
            fr, doc_type = fr2, dt2
        if fr is not None:
            if doc_type == 'word':
                try:
                    if fr.evaluate('() => document.querySelectorAll(".Page").length') > 0:
                        return fr, doc_type
                except Exception:
                    pass
            elif current_slide(fr) is not None:
                return fr, doc_type
        pg.wait_for_timeout(2000)
    return fr, doc_type


def capture_word_pages(b, pg, fr, work_dir):
    """Word Online 가상화 페이지(.Page)를 리본 가림 없이 순차 캡처."""
    try:
        cdp = persistent_context(b).new_cdp_session(pg)
        win = cdp.send('Browser.getWindowForTarget')
        cdp.send('Browser.setWindowBounds', {
            'windowId': win['windowId'],
            'bounds': {'width': 1920, 'height': 1600, 'windowState': 'normal'}
        })
        pg.wait_for_timeout(1000)
    except Exception as e:
        log('창 크기 조정 실패 (무시):', str(e)[:60])

    seq = []
    idx = 0
    while idx < 300:
        pg.mouse.move(10, 1550)
        has_page = fr.evaluate('''idx => {
            const pages = document.querySelectorAll('.Page');
            const panel = document.querySelector('#WACViewPanel');
            if (!pages[idx] || !panel) return false;
            const p = pages[idx];
            p.scrollIntoView({ behavior: 'instant', block: 'start' });
            const currentTop = p.getBoundingClientRect().top;
            panel.scrollTop += (currentTop - 160);
            return true;
        }''', idx)

        if not has_page:
            break

        pg.wait_for_timeout(1200)
        pg.mouse.move(10, 1550)

        final_rect = fr.evaluate('''idx => {
            const pages = document.querySelectorAll('.Page');
            if (!pages[idx]) return null;
            const r = pages[idx].getBoundingClientRect();
            return { x: r.x, y: r.y, width: r.width, height: r.height };
        }''', idx)

        if not final_rect or final_rect['width'] < 100 or final_rect['height'] < 100:
            break

        clip = {
            'x': round(final_rect['x']),
            'y': round(final_rect['y']),
            'width': round(final_rect['width']),
            'height': round(final_rect['height'])
        }
        out_file = work_dir / ('slide-%03d.png' % (idx + 1))
        pg.screenshot(path=str(out_file), clip=clip)
        seq.append(idx + 1)
        log('워드 페이지 캡처 %d장' % (idx + 1))

        is_last = fr.evaluate('''idx => {
            const pages = document.querySelectorAll('.Page');
            const p = pages[idx];
            if (p && p.classList.contains('LastPage')) return true;
            return false;
        }''', idx)
        if is_last:
            log('마지막 페이지 도달 (%d장)' % (idx + 1))
            break

        idx += 1

    return seq


def run_ppt2md(md_script: Path, out_pdf: Path) -> None:
    """Markdown 생성 (ppt2md 연동). 실패 시 예외를 전파해 전체 명령을 실패시킨다."""
    if md_script.exists():
        log('Markdown 변환 시작 (ppt2md)...')
        subprocess.run([sys.executable, str(md_script), str(out_pdf)], check=True)


def _capture_ppt_slides(pg, fr, work_dir):
    """Capture every editor slide, including slides omitted by a slideshow."""
    total = slide_total(fr)
    if total is None or not 1 <= total <= 300:
        raise RuntimeError('슬라이드 총 장수 확인 실패 또는 300장 초과')
    pg.set_viewport_size({'width': 1920, 'height': 1200})
    selected = fr.locator('[role="option"][aria-selected="true"][aria-posinset]')
    surface = fr.locator('[id^="SlideRootViewElement"]:visible')
    seq = []
    for number in range(1, total + 1):
        fr.locator('[role="option"][aria-posinset="%d"]' % number).click()
        fr.wait_for_function('''number => {
            const selected = document.querySelector('[role="option"][aria-selected="true"]');
            const roots = [...document.querySelectorAll('[id^="SlideRootViewElement"]')]
                .filter(el => el.checkVisibility() && el.getBoundingClientRect().width > 600);
            return selected?.getAttribute('aria-posinset') === String(number) && roots.length === 1;
        }''', arg=number, timeout=15000)
        pg.wait_for_timeout(1300)
        if selected.get_attribute('aria-posinset') != str(number):
            raise RuntimeError('슬라이드 선택 불일치: expected %d' % number)
        active_id = fr.evaluate('''() => {
            const roots = [...document.querySelectorAll('[id^="SlideRootViewElement"]')]
                .filter(el => el.checkVisibility() && el.getBoundingClientRect().width > 600);
            return roots.length === 1 ? roots[0].id : null;
        }''')
        target_surface = fr.locator(f'#{active_id}') if active_id else surface
        try:
            target_surface.screenshot(path=str(work_dir / ('slide-%03d.png' % number)), timeout=10000)
        except Exception:
            pg.wait_for_timeout(1000)
            target_surface.screenshot(path=str(work_dir / ('slide-%03d.png' % number)), timeout=15000)
        seq.append(number)
        log('슬라이드 %d/%d 캡처 확인' % (number, total))
    if slide_total(fr) != total:
        raise RuntimeError('캡처 중 원본 장수가 변경됨 — 발행 중단')
    return seq


def main():
    run_lock = acquire_run_lock()  # /tmp 슬라이드 정리·캡처 레이스 방지 (종료 시 해제)
    ap = argparse.ArgumentParser(description='SharePoint PowerPoint → PDF')
    ap.add_argument('url', nargs='?',
                    help='SharePoint 링크 (생략 시 기존 SharePoint 탭 재사용)')
    ap.add_argument('--out', help='출력 PDF 경로 (기본: ~/decks/<문서명>/<문서명>.pdf)')
    ap.add_argument('--keep-tab', action='store_true', help='작업 후 탭 유지')
    ap.add_argument('--reuse', action='store_true',
                    help='기존 SharePoint 탭 재사용 (링크 생략과 동일 — 로그인·재시도 후 재실행용)')
    ap.add_argument('--no-markdown', action='store_true',
                    help='Markdown 생성(ppt2md) 생략 (PDF + 슬라이드 PNG만 생성)')
    args = ap.parse_args()

    if OLD_COOKIE_FILE.exists():
        OLD_COOKIE_FILE.unlink()  # v1 라이브 세션 스냅샷 — 미사용 자격증명 즉시 정리
        log('구버전 쿠키 백업 삭제 (~/.gjc/ppt2pdf-cookies.json)')

    ensure_browser()
    WORK.mkdir(exist_ok=True)
    for old in WORK.glob('slide-*.png'):
        old.unlink()

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(CDP)
        persistent_context(b)  # fail closed before any navigation if profile context is missing
        if not args.url or args.reuse:  # 링크 생략 또는 --reuse = 기존 SharePoint 탭 재사용
            pages = [pg for c in b.contexts for pg in c.pages if 'sharepoint' in pg.url]
            if not pages:
                log('재사용할 SharePoint 탭이 없음 — --reuse 없이 링크만 인자로 주면 새 탭을 엽니다')
                sys.exit(1)
            pg = pages[-1]
            log('기존 탭 재사용')
        else:
            pg = new_profile_page(b)
            log('탭 열기:', args.url[:90])
            try:
                pg.goto(args.url, wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                log('탭 열기 실패:', str(e)[:100])
                pg.close()
                sys.exit(1)

        # 앱 로딩 대기 (90초). 로그인 페이지면 수동 로그인 대기 — 최대 5분, 완료 시 자동 진행.
        fr = None
        doc_type = None
        doc_title = None
        for _ in range(45):
            pg.wait_for_timeout(2000)
            fr, doc_type = find_app_frame(pg)
            doc_title = pg.title()
            if fr:
                break
        if not fr and ('login.microsoftonline' in pg.url.lower()
                       or '로그인' in (doc_title or '')):
            log('로그인 필요 — 브라우저 창에서 M365 로그인 (최대 5분 대기, 완료 시 자동 진행)')
            for _ in range(150):
                pg.wait_for_timeout(2000)
                fr, doc_type = find_app_frame(pg)
                doc_title = pg.title()
                if fr:
                    break
        if not fr:
            if 'login.microsoftonline' in pg.url.lower() or '로그인' in (doc_title or ''):
                log('로그인 대기 시간 초과 — 로그인 완료 후 --reuse 로 재실행 (탭은 열어둠)')
            else:
                log('앱 로드 실패/지연 — 그 탭을 확인하고(필요시 새로고침) --reuse 로 재시도 (탭은 열어둠)')
            sys.exit(1)
        log('앱 로드됨 (%s): %s' % (doc_type, (doc_title or '')[:60]))

        # 문서 준비 게이트(최대 60초)
        fr, doc_type = wait_doc_ready(pg, fr, doc_type)
        if fr is None or (doc_type == 'ppt' and current_slide(fr) is None):
            log('문서 응답 없음 — 탭 새로고침 후 재대기')
            try:
                pg.reload(wait_until='domcontentloaded', timeout=60000)
            except Exception as e:
                log('새로고침 실패(무시):', str(e)[:60])
            for _ in range(45):
                pg.wait_for_timeout(2000)
                fr, doc_type = find_app_frame(pg)
                doc_title = pg.title()
                if fr:
                    break
            if fr:
                fr, doc_type = wait_doc_ready(pg, fr, doc_type)
        if fr is None or (doc_type == 'ppt' and current_slide(fr) is None):
            log('문서 로드 실패 — 탭을 확인한 뒤 재실행 (탭은 열어둠)')
            sys.exit(1)

        seq = []
        if doc_type == 'word':
            log('Word 문서 감지 — 페이지 단위 캡처 모드 시작')
            seq = capture_word_pages(b, pg, fr, WORK)
        else:
            seq = _capture_ppt_slides(pg, fr, WORK)

        if not seq:
            log('캡처 실패 — 0장')
            if not args.keep_tab:
                pg.close()
            sys.exit(1)

        # PDF 조립 + 슬라이드 이미지 저장 (~/decks/<문서명>/)
        name = (doc_title or 'document').rsplit('.', 1)[0].strip() or 'document'
        out = Path(args.out) if args.out else Path.home() / 'decks' / name / (name + '.pdf')
        deck_dir = out.parent
        deck_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(WORK.glob('slide-*.png'))
        for old in deck_dir.glob('slide-*.png'):  # ponytail: 이전 추출 잔여 슬라이드 정리 (덮어쓰기 누락 방지)
            old.unlink()
        subprocess.run([sys.executable, '-m', 'img2pdf', *map(str, files), '-o', str(out)],
                       check=True)
        for f in files:  # AI 분석용 슬라이드 PNG
            shutil.copy2(f, deck_dir / f.name)
        log('완료: %d장 → %s (%.1f MB)' % (len(seq), out, out.stat().st_size / 1e6))
        log('슬라이드 이미지: %s/slide-*.png (%d장)' % (deck_dir, len(files)))

        # Markdown 생성 (ppt2md 연동) — check=True 로 실패 전파 (F9/D3)
        # 실패하더라도 keep_tab=False 면 Chromium 탭만 닫고 profile context는 유지한다.
        try:
            if not args.no_markdown:
                md_script = Path(__file__).resolve().parent / 'ppt2md.py'
                run_ppt2md(md_script, out)
        finally:
            if not args.keep_tab:
                pg.close()
                log('탭 정리 완료 (Chromium/profile context는 유지 — 세션 유지를 위해 창을 닫지 말 것)')
if __name__ == '__main__':
    main()

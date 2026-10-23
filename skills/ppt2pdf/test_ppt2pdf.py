#!/usr/bin/env python3
"""ppt2pdf 스크립트 유닛 검증 하네스 (V2 + 레드팀 적대 케이스).

Chrome/M365 없이 실행 가능 — 저장소에서 그대로:
  python3 skills/ppt2pdf/test_ppt2pdf.py

커버: Chromium 바이너리 탐색(실행불가/부재 스킵), CDP 포트↔전용 프로필
바인딩 파서(외부 브라우저/포트 불일치 거부), persistent profile context 탭 생성,
flock 실행 락.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / 'ppt2pdf.py'
spec = importlib.util.spec_from_file_location('ppt2pdf', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

tmpdir = Path(tempfile.mkdtemp(prefix='ppt2pdf-test-'))
mod.LOCK_FILE = tmpdir / 'run.lock'

ok = True


def check(name, cond, detail=''):
    global ok
    print(('PASS' if cond else 'FAIL'), name, detail)
    if not cond:
        ok = False


# ── V2-1: Chromium 바이너리 탐색 ────────────────────────────────
exe = tmpdir / 'chromium-1208' / 'chrome'
exe.parent.mkdir()
exe.write_text('#!/bin/sh\n')
exe.chmod(0o755)
dead = tmpdir / 'chromium-9999' / 'chrome'  # 최신이지만 실행 비트 없음
dead.parent.mkdir()
dead.write_text('x')
check('V2 executable picked (not newer dead one)', mod.pick_chromium([exe, dead]) == exe)
check('V2 non-executable only -> None', mod.pick_chromium([dead]) is None)
check('V2 empty -> None', mod.pick_chromium([]) is None)
check('V2 order preserved (last wins)', mod.pick_chromium([dead, exe]) == exe)

# ── V2-2: 포트↔전용 프로필 바인딩 파서 (insane-review profile_bound 이식) ──
PROFILE = '/home/u/.local/state/mygjc/ppt2pdf-profile'
PS = [
    ' 123 /home/u/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome'
    ' --remote-debugging-port=9223 --user-data-dir=' + PROFILE + ' --no-first-run',
    ' 456 /usr/bin/chrome --remote-debugging-port=9222'
    ' --user-data-dir=/home/u/.local/state/mygjc/insane-review-profile',
    ' 789 /usr/bin/chrome --remote-debugging-port 9223 --user-data-dir=' + PROFILE,
    ' 999 /usr/bin/chrome --remote-debugging-port=9223 --user-data-dir=/other',
]
check('V2 bound pid (equals form)', mod._pid_bound_to_profile(PS, 9223, PROFILE) == 123)
check('V2 bound pid (space form)', mod._pid_bound_to_profile(PS[2:], 9223, PROFILE) == 789)
check('V2 foreign profile only -> None',
      mod._pid_bound_to_profile([PS[1]], 9223, PROFILE) is None)
check('V2 port mismatch -> None',
      mod._pid_bound_to_profile([PS[0]], 9222, PROFILE) is None)
check('V2 empty ps -> None', mod._pid_bound_to_profile([], 9223, PROFILE) is None)
check('V2 garbage pid field skipped -> None',
      mod._pid_bound_to_profile(['xxx --remote-debugging-port=9223 --user-data-dir=' + PROFILE],
                                9223, PROFILE) is None)

# ── V2-3: 새 문서는 persistent profile context 안에서 열어 세션을 유지 ──
from unittest.mock import MagicMock, patch
browser = MagicMock()
ctx = MagicMock()
page_from_profile = MagicMock()
ctx.new_page.return_value = page_from_profile
browser.contexts = [ctx]
opened = mod.new_profile_page(browser)
check('V2 profile page uses existing persistent context', opened is page_from_profile)
check('V2 persistent context new_page called once', ctx.new_page.call_count == 1)
check('V2 Browser.new_page convenience API never used', browser.new_page.call_count == 0)
empty_browser = MagicMock(); empty_browser.contexts = []
missing_context_rejected = False
try:
    mod.persistent_context(empty_browser)
except RuntimeError:
    missing_context_rejected = True
check('V2 missing persistent context fails closed', missing_context_rejected)

# ── V5: 실행 락 (flock) ──────────────────────────────────────────
lk1 = mod.acquire_run_lock()
check('V5 lock acquired', lk1 is not None)
import fcntl as _f
lk2 = open(mod.LOCK_FILE, 'w')
blocked = False
try:
    _f.flock(lk2, _f.LOCK_EX | _f.LOCK_NB)
except OSError:
    blocked = True
check('V5 second acquire blocks', blocked)
lk1.close()
lk3 = open(mod.LOCK_FILE, 'w')
_f.flock(lk3, _f.LOCK_EX | _f.LOCK_NB)
check('V5 lock released after close', True)
lk3.close()

# ── F9: ppt2md 오류 전파 (check=True) ─────────────────────────────
import subprocess
dummy_pdf = tmpdir / 'sample.pdf'
dummy_pdf.write_text('dummy pdf bytes')
good_script = tmpdir / 'good_ppt2md.py'
good_script.write_text('#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n')
good_script.chmod(0o755)
bad_script = tmpdir / 'bad_ppt2md.py'
bad_script.write_text('#!/usr/bin/env python3\nimport sys\nsys.exit(2)\n')
bad_script.chmod(0o755)

# 1) 정상 스크립트 실행 -> 성공
threw_good = False
try:
    mod.run_ppt2md(good_script, dummy_pdf)
except Exception as e:
    threw_good = True
check('F9 ppt2md success passes', not threw_good)

# 2) 오류 스크립트 실행 -> CalledProcessError 전파 (PDF 선행 생성이어도 실패)
threw_bad = False
try:
    mod.run_ppt2md(bad_script, dummy_pdf)
except subprocess.CalledProcessError as e:
    threw_bad = (e.returncode == 2)
check('F9 ppt2md failure propagates CalledProcessError', threw_bad)

# 3) 부재 스크립트 -> no-op 성공
threw_missing = False
try:
    mod.run_ppt2md(tmpdir / 'missing_script.py', dummy_pdf)
except Exception:
    threw_missing = True
check('F9 missing ppt2md script is no-op', not threw_missing)

# Editor capture must include hidden slides and reject stale selection.
page = MagicMock()
frame = MagicMock()
frame.locator.return_value.get_attribute.side_effect = ['1', '2', '3']
with patch.object(mod, 'slide_total', return_value=3):
    captured = mod._capture_ppt_slides(page, frame, tmpdir)
check('PPT captures every editor slide including hidden slides', captured == [1, 2, 3])
check('PPT uses slide-only screenshots', frame.locator.return_value.screenshot.call_count == 3)
frame.reset_mock()
frame.locator.return_value.get_attribute.side_effect = ['1', '1']
with patch.object(mod, 'slide_total', return_value=3):
    try:
        mod._capture_ppt_slides(page, frame, tmpdir)
        check('PPT rejects stale selected slide', False)
    except RuntimeError:
        check('PPT stops before capturing stale selected slide',
              frame.locator.return_value.screenshot.call_count == 1)

# Resume vs Fresh mode test
resume_dir = tmpdir / 'resume_test'
resume_dir.mkdir(parents=True, exist_ok=True)
(resume_dir / 'slide-001.png').write_bytes(b'x' * 1500)
frame.reset_mock()
frame.locator.return_value.get_attribute.side_effect = ['2', '3']
with patch.object(mod, 'slide_total', return_value=3):
    captured_res = mod._capture_ppt_slides(page, frame, resume_dir, fresh=False)
check('PPT resume skips existing slide-001', captured_res == [1, 2, 3])
check('PPT resume only takes 2 screenshots', frame.locator.return_value.screenshot.call_count == 2)

frame.reset_mock()
frame.locator.return_value.get_attribute.side_effect = ['1', '2', '3']
with patch.object(mod, 'slide_total', return_value=3):
    captured_fresh = mod._capture_ppt_slides(page, frame, resume_dir, fresh=True)
check('PPT fresh recaptures all 3 slides', captured_fresh == [1, 2, 3])
check('PPT fresh takes 3 screenshots', frame.locator.return_value.screenshot.call_count == 3)
# ── V2-5: skill_cli fast-path wrapper tests ────────────────────────
CLI_SCRIPT = Path(__file__).resolve().parent / 'skill_cli.py'
cli_spec = importlib.util.spec_from_file_location('skill_cli', CLI_SCRIPT)
cli_mod = importlib.util.module_from_spec(cli_spec)
cli_spec.loader.exec_module(cli_mod)

# 1) split_command
check('CLI split empty -> run', cli_mod.split_command([]) == ('run', []))
check('CLI split url -> run with url', cli_mod.split_command(['https://tenant.sharepoint.com/x']) == ('run', ['https://tenant.sharepoint.com/x']))
check('CLI split explicit run -> run', cli_mod.split_command(['run', 'https://tenant.sharepoint.com/x']) == ('run', ['https://tenant.sharepoint.com/x']))
check('CLI split check -> check', cli_mod.split_command(['check']) == ('check', []))
check('CLI split status -> status', cli_mod.split_command(['status']) == ('status', []))
check('CLI split cleanup -> cleanup', cli_mod.split_command(['cleanup']) == ('cleanup', []))

# 3) cmd_cleanup
test_work = tmpdir / 'cli-work'
test_work.mkdir(parents=True, exist_ok=True)
(test_work / 'slide-001.png').write_text('dummy')
(test_work / 'slide-002.png').write_text('dummy')
(test_work / 'keep.txt').write_text('keep')
with patch.object(cli_mod.engine, 'WORK', test_work), \
     patch.object(cli_mod.engine, 'acquire_run_lock', return_value=open(tmpdir / 'cli.lock', 'w')):
    cli_mod.cmd_cleanup()
    check('CLI cleanup removes slide pngs', not (test_work / 'slide-001.png').exists() and not (test_work / 'slide-002.png').exists())
    check('CLI cleanup preserves non-slide files', (test_work / 'keep.txt').exists())

# 4) browser_state structure
state = cli_mod.browser_state()
check('CLI browser_state has required keys', {'port', 'profile', 'chromium_available', 'cdp'}.issubset(set(state.keys())))

print('=== RESULT:', 'ALL PASS' if ok else 'FAILURES PRESENT')
sys.exit(0 if ok else 1)

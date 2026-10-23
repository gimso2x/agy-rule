---
name: insane-review
description: Run a strict ChatGPT Web code review over an explicitly bounded code set using the dedicated browser profile the agent starts itself and the immutable vendored generation. Use when the user asks for an insane review, strict code review, or explicitly invokes insane-review. Natural input defaults to the run fast path; check, status, and cleanup are explicit operational commands.
skill_version: 2.0.0
skill_status: active
skill_visibility: user
---

# Insane Review

이 스킬은 외부 전송 경계가 있는 코드 리뷰다. upstream 설치기·mutable `bin` 엔진·캐시를 실행하지 않는다. `bin`은 검증된 로컬 `vendor/current` generation만 descriptor로 실행하는 trusted launcher다. 자동 로그인, 주 브라우저/프로필 사용, API 또는 텍스트 붙여넣기 폴백은 금지한다.

Use the fast path for normal personal-coding requests. Read [FAST_PATH.md](FAST_PATH.md) first and follow its public `run/check/status/cleanup` contract. Treat `insane-review "<request>"` as `insane-review run "<request>"`. Orchestrate `prepare` and `send` internally with a single approval gate before external transfer.

## 1. 사전 준비 (에이전트가 브라우저를 직접 기동)

사용자에게 브라우저 수동 기동을 요청하지 않는다. 에이전트가 전용 Chromium을
직접 띄우고 접속 상태까지 확인한다. WSL2에서는 보안 검증(리눅스 `/proc` 및
0700 전용 프로필 바인딩)을 위해 WSL2 리눅스 Chromium을 사용한다.

```bash
# 기동 + 준비 상태 확인을 한 명령으로 (mygjc-cdp start는 이미 ready면 재기동하지 않는다)
(~/my-wiki/gjc-config/bin/mygjc-cdp start insane-review && \
 ~/my-wiki/gjc-config/bin/mygjc-cdp wait insane-review --timeout 900) & \
python3 ~/my-wiki/gjc-config/skills/insane-review/bin/pack_and_ask.py check-env \
  --cdp-endpoint http://127.0.0.1:9222 \
  --profile-dir "$HOME/.local/state/mygjc/insane-review-profile"
```

- launcher는 symlink 경로를 거부한다(`unsafe directory`). omp처럼 스킬 디렉터리가
  symlink로 연결된 환경에서도 항상 `~/my-wiki/gjc-config/skills/insane-review/bin/pack_and_ask.py`
  절대경로로 실행한다.
- `mygjc-cdp start insane-review`는 chatgpt 역할이므로 기동 시
  `https://chatgpt.com/` 탭을 함께 연다(fresh 프로필의 `no_chatgpt_page` 방지).
- `check-env`의 login/model 관측 분기표:

| 관측 | 의미 | 에이전트 행동 |
|---|---|---|
| `ready: true` | 로그인 + `GPT-5.6 Sol` exact 준비 완료 | 파일 선별 → prepare 진행 |
| `login:"missing", reason:"no_chatgpt_page"` | ChatGPT 탭 없음 | 다시 체인 1 실행(start가 탭을 열고 check-env 재관측) |
| `login:"missing", reason:"authentication_required"` | 로그아웃 상태 | 로그인 창을 열어둔 채 ask로 "로그인 완료" 확인 → 체인 1 재실행(전송 없음) |
| `login:"ready", model:"mismatch"` 또는 `model:"unobservable"` | 모델 미선택/관측 불가 | ask로 모델 선택(GPT-5.6 Sol, 추론 높음) 안내 → 체인 1만 재실행; `ready:true`일 때만 진행 |
| `login:"unobservable"` / `probe_error` | 관측 실패 | fail-closed; 재관측 1회 후 중단·보고 |

로그인은 수동이다. 자격증명 입력·쿠키 접근은 금지다. `start && wait`를 명시적
960초 이상 러너 타임아웃의 백그라운드 잡으로 실행해 브라우저를 소유한 채 유지하고,
그 잡이 살아 있는 동안 `check-env`를 동시 실행해 login/model을 관측한다. `wait`는
브라우저와 ChatGPT 탭 생존만 확인하며 인증·모델 준비를 주장하지 않는다. `check-env`
가 `ready:true`를 반환한 뒤에만 prepare와 단일 승인 경계를 진행한다.

**포트 공존 계약**: 9222는 이 스킬 전용이다(ppt2pdf는 9223, gptplan은 9224).
외부 브라우저 도구는 `WBROWSER_CDP_PORT`(예: 9225)처럼 9222-9224 밖 포트를
써야 한다. 반대로 이 스킬의 브라우저가 먼저 떠 있으면 외부 도구 launcher는
`ALREADY_UP` 판정으로 부착을 시도하므로, 양방향 모두 포트 분리가 계약이다.

## 2. 필수 전송 및 검증 순서

1. 검토자(에이전트)가 사용자 요청과 git/코딩 맥락에서 **완전한 intended
   manifest**를 만든다(관련 파일 누락 없이, 불필요 파일 제외). 각 항목은
   canonical relative `path`와 SHA-256만 가지며, 빠진 파일·추가 파일·digest
   drift는 실패다.
   - 단일 파일/전체 팩 상한: **100,000 토큰 / 4MB (4,194,304 bytes)**
2. `pack_and_ask.py prepare`에 intended manifest와 secretlint 설정을 준다
   (`--repo`, `--intended`, `--secretlint-config` 필수). token count는 caller가
   제공하지 않으며 finalized exact pack bytes를 approved tokenizer로 측정할 수
   없으면 실패한다. secretlint는 필수이며 실제 결과의 exclusions는 required
   manifest와 결속되어야 한다. 결과 intended/actual manifest와 pack은 private
   artifact root에 create-new 0600으로 보존된다.
3. 실제 전송 전에 검토자가 출력된 **manifest SHA-256과 pack SHA-256 모두**를
   명시 승인한다(아래 단일 승인 경계). 토큰을 측정할 수 없거나 100000 초과,
   pack이 4194304 bytes 초과, pack parse 실패면 안전한 범위 축소 없이 즉시
   중단한다.
4. `send`은 승인된 동일 pack만 no-follow로 재검증하고 단 한 번 첨부한다.
   재-pack, 압축, paste, 누락 파일 전송은 금지다.

### 단일 승인 경계 (ask)

전송 직전 한 번의 ask에 다음을 모두 표시하고 승인받는다:

- 파일 수 & 범위 (선별된 경로 목록)
- 측정된 토큰 수 & 바이트
- secretlint 판정
- Manifest SHA-256 & Pack SHA-256
- 대상 모델 (`GPT-5.6 Sol`, ChatGPT Web via dedicated CDP 9222)

### send 계약 (에이전트 실행, 사용자 타이핑 없음)

브라우저는 스크립트 프로세스가 살아 있는 동안만 유지되므로(커맨드 종료 후 수 초 내
정리됨), 전송 시점에 브라우저가 살아 있도록 **start와 send를 한 명령으로**
실행한다. `mygjc-cdp start`는 이미 ready면 재기동하지 않는다:

```bash
~/my-wiki/gjc-config/bin/mygjc-cdp start insane-review && \
python3 ~/my-wiki/gjc-config/skills/insane-review/bin/pack_and_ask.py send \
  --pack <pack> --manifest <manifest> \
  --approved-pack-sha <sha> --approved-manifest-sha <sha> \
  --cdp-endpoint http://127.0.0.1:9222 \
  --profile-dir "$HOME/.local/state/mygjc/insane-review-profile" \
  --prompt "<리뷰 요청 프롬프트 텍스트(리터럴)>" \
  --run-id <run-id> --timeout 1200
```

준비·승인 단계가 길어져 브라우저가 내려갔다면 send 직전의 start가 재기동하며,
로그인 세션은 0700 프로필에 보존되어 있으므로 재로그인 없이 ready에 도달한다.
이 체인도 에이전트 러너의 기본 foreground 타임아웃(≈300초)보다 길 수 있으므로
백그라운드 잡으로 띄우고 잡 완료를 기다린다.

- `--timeout`은 1200초(SEND_TIMEOUT_SECONDS)를 사용한다. 런처 기본값 120초는
  Pro 추론 응답에 부족하다.
- `--prompt`는 파일 경로가 아니라 **리터럴 프롬프트 텍스트**다.
- 타임아웃·실패 시 `*.failure.json` receipt가 남는다. **동일 pack에 대한 send
  재실행(재전송)은 금지다.** 실패를 보고하고 사용자 지시를 기다린다.

## 3. CDP와 완료 조건

- 전용 localhost CDP(9222)와 private 0700 profile 결속은 필수다. lock
  contention, localhost/profile 검증 실패, 첨부 실패, timeout, 빈/echo/refusal
  응답은 모두 실패이며 성공 receipt를 남기지 않는다.
- 성공은 stable model control의 exact selection, attachment-completion
  control, 새 assistant turn의 완료, 비echo substantive response, 유일한 0600
  response artifact를 모두 만족할 때만 기록한다.
- `.insane-review`는 0700이어야 한다. pack, intended/actual manifest,
  prepare/approval/success/failure receipt, response는 모두 no-follow/create-new
  0600이다. 기존 파일 또는 symlink는 덮어쓰지 않는다.

## 4. 환경 확인

`check-env`은 읽기 전용으로 Python, `secretlint`, Node와 Playwright를 각각,
dedicated localhost CDP, private profile, 수동 로그인, exact required-model
readiness를 보고해야 한다. 토큰 측정 전제조건으로 전역 `js-tiktoken@1.0.21`이
고정되어야 하며, 필요한 경우 수동으로 `npm install -g js-tiktoken@1.0.21`을
실행한다. tokenizer가 없거나 버전이 다르면 fail-closed하고, `check-env`는
tokenizer 가용성과 관측 버전을 함께 보고해야 한다. 관측할 수 없는 readiness는
ready가 아닌 fail 상태다. 설치·로그인·브라우저 실행·설정 변경·전송을 수행하지
않는다.

## 5. 리뷰 결과 처리

1. 응답은 0600 response artifact로 저장된다(엔진이 기록).
2. GPT 의견을 요약하고, 에이전트 자신의 동의/이견을 함께 보고한다(그들이
   옳든 아니든 독자적 판단을 명시).
3. ask로 "수정을 코드에 반영할까?"를 묻고, 승인 시 에이전트가 직접 코드에
   반영한다. 반영 없이 종료할 수도 있다.

## 6. 셀렉터 외부화 및 한계 (Known-Gap)

- 주요 UI 셀렉터는 `selectors.json`으로 외부화되어 서명된 세대와 함께 제공된다.
- **알려진 한계(Known-Gap)**: `duplicate_modal` 컨테이너 셀렉터는 외부화되었으나,
  모달 내부의 확인 버튼 탐색 로직(role-name 정규식 `/확인|confirm|continue|replace|upload/i`
  및 `.locator("button").last()` 폴백)은 현행 active generation의
  `pack_and_ask.py` 내부에 하드코딩되어 있다 (세대 해시는 `vendor/current`가
  유일한 진실원천 — 본 문서에 해시 핀 금지).
- **영향 및 대응**: ChatGPT 웹의 중복 파일 모달 확인 버튼 구조가 변경될 경우
  `send`는 버튼 감지 타임아웃으로 fail-closed된다. 이 한계는 기존 세대 파일을
  직접 수정하지 않고, 새 셀렉터 키(`duplicate_confirm_button`)를 포함하는 새로운
  signed generation을 발행(`mygjc-update.py` 파이프라인)하는 방식으로만 해소한다.
  기존 세대 파일의 제자리 편집은 엄격히 금지된다.

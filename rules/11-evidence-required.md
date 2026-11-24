---
trigger: model_decision
description: "Apply when debugging, fixing errors, or changing code or configuration that must be verified by evidence."
---

# 11-evidence-required: 원리 기반 실행 및 증거 필수 원칙 (Principle-First)

## 1. 추측 기반 수정 금지 (Anti-Assumption)
- 코드나 설정을 변경하기 전, 대상 파일의 실제 구조와 동작 방식을 반드시 직접 확인(view/grep)하십시오.
- "이럴 것이다"라는 추측만으로 코드를 생성하거나 패치하지 마십시오.

## 2. 증거 기반 디버깅 (Evidence-Based Debugging)
- 에러 해결 시 로그, 스택 트레이스, 관련 설정 파일의 명시적 증거를 먼저 수집하십시오.
- 원인이 규명된 후에만 최소한의 정확한 변경을 적용하십시오.

## 3. 사후 검증 필수
- 모든 코드 수정 후에는 린트(Lint), 빌드(Build), 테스트(Test) 또는 실제 커맨드 실행을 통해 변경 사항이 정상 동작하는지 증거로 입증하십시오.

## 4. 검증 범위 (Verification Scope)
- 변경과 직접 관련된 가장 좁은 검증(해당 테스트, 린트, 실행)부터 돌리십시오.
- 바뀐 인터페이스, 영향 범위, 위험도, 저장소 CI 요구에 따라 검증 범위를 넓히십시오. 공개 API, 공유 모듈, 설정 변경이면 더 넓게 돌리고 결과를 보고하십시오.
- 검증 수단이 없고 새 테스트가 그 변경에 맞을 때만 최소 테스트를 추가하십시오. 맞지 않으면 실행 증거나 수동 확인 절차를 남기십시오.
- 사용자가 보고한 오류와 관찰은 조사할 증거로 받으십시오. 같은 검사를 불필요하게 반복하지 말되, 원인을 좁히거나 수정 후 검증하려면 직접 재현하십시오.
- 출처: Antigravity CLI best practices의 검증 루프(https://antigravity.google/docs/cli/best-practices/)와 공개 omp 프롬프트 중 런타임 비종속 원칙.

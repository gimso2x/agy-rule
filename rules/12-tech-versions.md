# 12-tech-versions (기술 스택 및 버전 관리)

> **원칙**: 에이전트는 사용자의 환경을 임의로 변경하지 않습니다. 현재 설치된 런타임과 프로젝트의 고정 버전을 절대적 기준으로 삼습니다.

---

## 1. 환경 버전 우선 확인 (Evidence-First Versions)
- **런타임 및 의존성 조사**: 패키지 설치나 코드 생성 전, 시스템에 이미 설치된 핵심 도구 버전을 확인합니다.
  - 예: `node -v`, `python3 --version`, `go version`, `docker --version`
- **락파일(Lockfile) 및 매니페스트 준수**:
  - `package.json`, `package-lock.json`, `pnpm-lock.yaml`
  - `requirements.txt`, `Pipfile.lock`, `poetry.lock`
  - `go.mod`, `Cargo.lock`
  - 기존 명시된 버전 범위를 임의로 최신 버전으로 올리거나 낮추지 않습니다.

---

## 2. 패키지 추가 및 버전 잠금 규칙
- **LTS 및 안정 버전 우선**: 신규 라이브러리가 필요할 경우 최신 베타/RC 버전이 아닌, 안정화된 LTS(Long Term Support) 버전을 제안합니다.
- **임의 패키지 설치 금지**: 프로젝트에 동일한 역할을 하는 라이브러리(예: `axios`가 있는데 `fetch` 래퍼나 `got` 추가)가 이미 존재한다면 기존 패키지를 그대로 활용합니다.
- **호환성 파괴 변경(Breaking Changes) 사전 점검**: 메이저 버전 차이로 인한 API 폐기(Deprecation) 여부를 작업 전 반드시 확인합니다.

---

## 3. 되돌리기 어려운 버전 조작 금지
- 시스템 전역 패키지 매니저나 파이썬 전역 환경(`sudo pip install`)에 직접 패키지를 강제 설치하지 않습니다.
- 가상환경(`venv`, `conda`)이나 로컬 의존성 디렉터리(`node_modules/`, `vendor/`) 격리를 원칙으로 합니다.

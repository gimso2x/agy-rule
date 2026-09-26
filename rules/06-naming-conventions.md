# 06-naming-conventions (명명 규칙 표준)

> **원칙**: 이름은 코드의 의도를 가장 직접적으로 드러내는 인터페이스입니다. 추측하기 쉬운 명확한 어휘를 사용하고 모호한 축약어를 배제합니다.

---

## 1. 파일 및 디렉터리 명명 규칙
- **디렉터리 및 일반 파일**: 소문자 케밥케이스(`kebab-case`)를 기본으로 사용합니다.
  - 예: `user-profile/`, `auth-service.ts`, `data-loader.py`
- **컴포넌트 및 클래스 파일**: 해당 프레임워크 관례(React 컴포넌트 등)에 따라 파스칼케이스(`PascalCase`)를 허용합니다.
  - 예: `UserProfile.tsx`, `NavigationHeader.vue`
- **설정 및 특수 파일**: 도구 표준 관례(`GEMINI.md`, `Dockerfile`, `.env.example`)를 준수합니다.

---

## 2. 코드 심볼 명명 규칙
- **변수 및 함수**: 카멜케이스(`camelCase`) 또는 파이썬의 경우 스네이크케이스(`snake_case`)를 언어 표준에 맞게 일관되게 사용합니다.
  - 불린(Boolean) 변수: `is`, `has`, `can`, `should` 접두사를 붙여 명확한 상태를 표현합니다. (예: `isLoading`, `hasPermission`)
  - 함수명: 동사로 시작하여 동작을 서술합니다. (예: `fetchUserData()`, `calculateDiscount()`)
- **클래스, 타입, 인터페이스**: 파스칼케이스(`PascalCase`)를 사용합니다.
  - 예: `UserRepository`, `PaymentSession`, `ApiResponse`
- **상수(Constant) 및 환경변수**: 대문자 스네이크케이스(`UPPER_SNAKE_CASE`)를 사용합니다.
  - 예: `MAX_RETRY_COUNT`, `API_BASE_URL`

---

## 3. 금지 및 주의 사항
- **모호한 한 글자 변수 금지**: 반복문 인덱스(`i`, `j`)를 제외하고 `a`, `tmp`, `data`, `obj` 같은 의미 없는 이름은 사용하지 않습니다.
- **불필요한 축약 금지**: 널리 통용되는 도메인 약어(`id`, `url`, `api`, `db`) 외의 독자적 축약어(`calc`, `btn`, `usr`, `req_auth`)를 남발하지 않습니다.
- **부정형 변수명 지양**: 이중 부정을 유발하는 이름(예: `isNotReady`, `disableFlag = false`) 대신 긍정형(`isReady`, `isEnabled`)을 사용합니다.

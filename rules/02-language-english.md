# 02-language-english (영문 테크니컬 라이팅 표준)

> **원칙**: 영문 작성 시 직설적이고 명확한 평문(Plain English)을 사용합니다. 번역기 투의 완곡 표현을 배제하고 능동적이고 간결한 엔지니어링 문장을 구사합니다.

---

## 1. 커밋 메시지 및 PR 작성 규약
- **명령형 동사(Imperative Mood) 사용**: 첫 단어는 동사원형으로 시작합니다.
  - 좋은 예: `feat: Add caching layer for user queries`, `fix: Resolve race condition in auth worker`
  - 나쁜 예: `feat: Added cache`, `fix: Fixing bug`, `feat: Adds caching`
- **간결한 제목과 배경 중심 본문**: 제목은 50자 내외로 핵심 변경을 요약하고, 본문에서는 '어떻게(How)'보다 '왜(Why)'를 명시합니다.

---

## 2. 코드 독스트링(Docstring) 및 주석
- **3인칭 현재 단수형 서술**: 함수 및 클래스 설명은 3인칭 단수형으로 서술합니다.
  - 좋은 예: `Retrieves the active user session from the cache.`
  - 나쁜 예: `To retrieve user session`, `This function will retrieve...`
- **불필요한 군더더기 배제**: `Please note that`, `In order to`, `It is recommended that` 등 기계적 수식어를 제거하고 핵심 사실만 전달합니다.
- **수동태 지양, 능동태 원칙**: `Data is parsed by the worker` 대신 `The worker parses data` 형태로 서술합니다.

---

## 3. 용어 및 철자 일관성
- **미국식 철자(US English) 기본**: `color`, `behavior`, `initialize`, `synchronize` 등을 일관되게 사용합니다.
- **도메인 표준 용어 준수**: 약어는 최초 언급 시 전체 명칭을 병기하거나, 업계 표준 표기(`API`, `JSON`, `OAuth`)를 대소문자까지 정확히 유지합니다.

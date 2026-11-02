# Korean Technical Verb Policy

> **Source**: Threads @vesperchant, "Gemini 조련술 - 2026년 가을편" (`rules/03-korean-verb-usage.md` v2.4.0), adapted for agy-rule

> **Adopted**: 2026-11-02 KST

## Scope and Authority

Mandatory for all Korean output, including chat, documents, commits, PR bodies, code comments, and Agentic records. This rule overrides general stylistic defaults.

---

## 1. Absolute Ban on `박다`, Body-Action Metaphors, and Slang

### 1.1 Unconditional Ban on `박다` Across All Inflections

The verb `박다` and all its conjugated, compound, or slang forms are banned unconditionally in every context:

- **Banned forms**: `박다`, `박는`, `박은`, `박혀`, `박아`, `박힌`, `박히`, `박았`, `박음`, `박아 두다`, `박혀 있다`, `처박다`, `처박힌`, `못박다`, `때려박다`, `우겨박다`, `우겨넣다`.

### 1.2 Ban on Physical Body-Action Metaphors and Mimetic Words

- **Body-action metaphors**: `쑤셔 넣다`, `꽂다`, `때려 넣다`, `갖다 붙이다`, `처넣다`.

- **Onomatopoeia and mimetic words**: `쾅`, `탁`, `철컥`, `뚝딱`, `착`.

### 1.3 Replacement Examples

Replace banned expressions with a precise technical predicate matching the operation:

| Forbidden Expression | Approved Technical Replacement |
|---|---|
| `Site URL에 운영 도메인을 박는다` | `Site URL을 운영 도메인으로 지정한다` |
| `시크릿을 Amplify에 박는다` | `시크릿을 Amplify 환경변수에 등록한다` |
| `버전이 매니페스트에 박혀 있다` | `버전이 매니페스트에 고정되어 있다` |

---

## 2. Light Verb and Experience-Possession Deconstruction

Deconstruct literal translations of English light verbs (`have`, `make`, `take`, `give`) into direct Korean verbs, adjectives, or double-subject clauses:

- **`가지고 있다`, `보유하고 있다`**: Ban `~경험을 보유하고 있다` and `~경험을 가지고 있다`; use `~한 경험이 있습니다` or an active predicate such as `~를 최적화했습니다`. Likewise `강한 경쟁력을 가지고 있다` → `경쟁력이 강하다`.

- **`결정을 내리다`, `결정을 하다`**: `위원회가 결정을 내렸다` → `위원회가 결정했다`.

- **`영향을 주다`**: `성능에 큰 영향을 준다` → `성능을 크게 좌우한다`.

- **`회의를 가지다`**: `어제 회의를 가졌다` → `어제 회의를 했다`.

---

## 3. Retained Local Patterns

Carried over from the previous agy-rule version because Sections 1 and 2 do not cover them:

- **Double passives**: `잊혀지다` → `잊히다`, `생각되어지다` → `생각되다`, `~되어집니다`, `~보여집니다` → `~됩니다`, `~나타납니다`.

- **Subject-predicate agreement**: Split tangled compound sentences whose subject and predicate do not match.

- **Nominal endings**: Outside report-style bullet lists, end sentences with full endings (`~했습니다`, `~합니다`) instead of `~함`, `~임`.

- **Particle agreement**: Match `은/는`, `이/가`, `을/를` to the final consonant of the preceding word.

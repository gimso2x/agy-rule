# Korean Natural Prose and Syntax Policy

> **Source**: Threads @vesperchant, "Gemini 조련술 - 2026년 가을편" (`rules/03-korean-natural-prose.md` v2.1.0), adapted for agy-rule

> **Adopted**: 2026-11-02 KST

## Scope and Authority

Mandatory for every Korean output surface, alongside [03-korean-verb-usage.md](03-korean-verb-usage.md). This rule overrides general stylistic defaults. Refining prose never alters, omits, or dilutes facts, numbers, identifiers, or quotes.

---

## 1. Particle Stacking and Overuse

Eliminate translation-ese particle chains and heavy postpositions:

- **`~에 대하여`, `~에 대해서`**: Replace with accusative `-를` or topic `-는`, as in `AI 규제에 대해 논의` → `AI 규제를 논의`.

- **`~를 통해`, `~를 통하여`**: Distribute across instrumental `-로`, causal `-해서`, or `-함으로써`.

- **`~에 있어서`, `~에 있어`**: Replace with `-에서` or `-을 볼 때`, as in `보안에 있어서 중요한 점` → `보안에서 중요한 점`.

- **Double particles**: Dismantle `-에서의`, `-에로의`, `-으로의`, `-에의`, and `-으로부터의` into natural clauses: `2층에서의 살림` → `2층에서 시작한 살림`, and `긴장으로부터의 해방` → `긴장에서 벗어남`. Simple `~의` is permitted.

- **By-passives**: Replace `~에 의해` by restoring the active subject or causal `-로`: `AI에 의해 생성된 코드` → `AI가 생성한 코드`, and `외부 요인에 의해 발생한 오류` → `외부 요인으로 발생한 오류`.

---

## 2. AI Cliches, Antithesis, and Connective Punctuation

### 2.1 Removal-Only Mandate and Banned Phrases

Never add ungrounded AI cliches, exaggerated idioms, or synthetic praise (`기록적인 성과를 거두었다`, `~로 평가된다`, `주목받았다`).

- **Summary cliches**: Eliminate `결론적으로`, `요약하면`, `종합하면`, `정리하자면`, `시사하는 바가 크다`, `매우 중요하다`, `주목할 만하다`, `간과할 수 없다`, `지평을 연다`, `방점을 찍는다`.

- **Hype words**: Avoid empty hype (`혁신적인`, `획기적인`, `전례 없는`, `압도적`, `파격적`, `폭발적`); state verifiable facts and metrics instead.

- **Formulaic transitions and personification**: Avoid `'A'에서 'B'로`, `'A'를 넘어 'B'로`, `~할 때입니다`, `~시점입니다`, `기술이 묻는다`, and `시대가 부른다`.

### 2.2 Repeated Binary Antithesis

Across paragraphs, do not repeat binary antithesis formulas (`A인가, B인가`, `단순히 A가 아니라 B다`, `A라기보다 B다`). State direct declarative conclusions.

### 2.3 No Commas After Connective Endings

Never place commas immediately after Korean connective endings (`-고,`, `-며,`, `-지만,`, `-면서,`, `-아서,`).

---

## 3. Rhythm and Register Consistency

### 3.1 Ending Variety and Sentence Rhythm

- Never repeat the same sentence ending (`~이다.`, `~한다.`, `~습니다.`) 4 or more times consecutively.

- Avoid redundant progressive `~고 있다` calqued from English `be -ing` when simple `~한다` or `~했다` suffices (`문서를 읽고 있다` → `문서를 읽는다`).

- Mix concise declaratives of 10 to 15 characters with structured compound sentences of 80 to 100 characters to avoid 30 to 50 character staccato monotony.

### 3.2 Register Integrity and Direct Predicates

- Maintain a single speech level (`하십시오체`, `해요체`, or `해라체`) within each document or response without switching levels mid-text.

- Never inflate past-tense stems from `-았-` or `-었-` to archaic `-하였-`.

- Replace excessive hedging (`~할 수 있을 것으로 보인다`, `~할 가능성이 있을 수 있다`) and formal noun endings (`~한 것이다`, `~라는 점에 있다`, `~다는 뜻이다`) with direct predicates when facts are verified.

---

## 4. Retained Local Patterns

Carried over from the previous agy-rule version because Sections 1 to 3 do not cover them:

- `~를 필요로 합니다` → `~가 필요합니다`; `~하는 것이 가능합니다` → `~할 수 있습니다`; replace a repeated `~의 경우` with a concrete noun or conditional clause.

- Do not attach `또한`, `그리고`, `따라서` to every sentence; let the context carry the connection.

- Lead with the conclusion or result, then expand the details.

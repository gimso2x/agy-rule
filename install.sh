#!/usr/bin/env bash
# ==============================================================================
# agy-rule: Antigravity / Gemini Agentic Sanctuary Installer & Synchronizer
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_HOME="${HOME}"

echo "=========================================================="
echo "🚀 Antigravity 에이전틱 성역(Sanctuary) 동기화 시작"
echo "   - 원천 경로: ${SCRIPT_DIR}"
echo "   - 대상 홈  : ${TARGET_HOME}"
echo "=========================================================="

# 1. 디렉터리 준비
mkdir -p "${TARGET_HOME}/.agents/rules"
mkdir -p "${TARGET_HOME}/.agents/skills"
mkdir -p "${TARGET_HOME}/.gemini/config/skills"

# 2. 규칙(Rules) 동기화 (심볼릭 링크)
echo "📦 [1/4] 규칙(Rules) 18종 동기화..."
for rule_file in "${SCRIPT_DIR}/rules/"*.md; do
  if [[ -f "${rule_file}" ]]; then
    base_name="$(basename "${rule_file}")"
    ln -sf "${rule_file}" "${TARGET_HOME}/.agents/rules/${base_name}"
  fi
done
echo "   ✅ 18개 규칙 파일이 ${TARGET_HOME}/.agents/rules/ 에 링크되었습니다."

# 3. 스킬(Skills) 8종 동기화
echo "📦 [2/4] 정예 스킬(Skills) 8종 동기화..."
for skill_dir in "${SCRIPT_DIR}/skills/"*; do
  if [[ -d "${skill_dir}" ]]; then
    skill_name="$(basename "${skill_dir}")"
    # ~/.agents/skills 및 ~/.gemini/config/skills 양쪽에 링크 (두 디스커버리 경로 모두 지원)
    ln -sfn "${skill_dir}" "${TARGET_HOME}/.agents/skills/${skill_name}"
    ln -sfn "${skill_dir}" "${TARGET_HOME}/.gemini/config/skills/${skill_name}"
    echo "   - [스킬] ${skill_name} 연동 완료"
  fi
done

# 4. GEMINI.md 설정
echo "📦 [3/4] 전역 GEMINI.md 진입점 구성..."
GLOBAL_CONFIG_GEMINI="${TARGET_HOME}/.gemini/config/GEMINI.md"
HOME_GEMINI="${TARGET_HOME}/GEMINI.md"

# 전역 설정 파일 갱신
cat <<EOF > "${GLOBAL_CONFIG_GEMINI}"
# Antigravity Global Agent Rules
@${SCRIPT_DIR}/GEMINI.md
EOF
echo "   ✅ ${GLOBAL_CONFIG_GEMINI} 생성 완료."

# 사용자 홈 루트 GEMINI.md 갱신
cat <<EOF > "${HOME_GEMINI}"
# 글로벌 에이전트 규칙
@${SCRIPT_DIR}/GEMINI.md
EOF
echo "   ✅ ${HOME_GEMINI} 생성 완료."

# 5. .harness 디렉터리 구조 확인
echo "📦 [4/4] 에이전틱 하네스 8대 디렉터리 보장..."
mkdir -p "${SCRIPT_DIR}/.harness/"{audits,handoff,history,memory,metrics,plans,pull-request,walkthroughs}
echo "   ✅ .harness 체계 보장 완료."

echo "=========================================================="
echo "🎉 동기화 완료! 이제 이 환경에서 Antigravity 최신 룰과 스킬을 즉시 사용할 수 있습니다."
echo "=========================================================="

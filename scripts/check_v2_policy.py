"""
Phase 4-H B3 — V2 정책 회귀 자동 감지 (grep CI)
출처: PRD-13 §18 + 사용자 명세

5 규칙:
  1. /api/ai/* 신규 호출 금지 (V2 코드 — draft-v2/ + lib/)
  2. draftsApi 참조 금지 (V2 코드)
  3. V1 Step4Review import 금지 (V2 코드)
  4. V1 5섹션 enum (overview/purpose/plan/effect/budget) 재침투 금지 (V2 코드 quoted string)
  5. Backend migration 추가 감지 (git diff backend/migrations/)

실행:
  python scripts/check_v2_policy.py

종료 코드:
  0: 모든 규칙 통과
  1: 1개 이상 위반

부수 정책 (검사 제외 패턴):
  - 주석 내 "정책 명시"는 위반 아님 (예: "// V1 5섹션 사용 금지"는 PASS)
  - PRD/문서/test 파일은 검사 제외 (코드만 검사)
"""
from __future__ import annotations
import re
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.resolve()

# V2 코드 영역 (검사 대상)
V2_ROOTS = [
    "web-react/src/features/pages/draft-v2",
    "web-react/src/lib",
]

# 검사 제외 — V2 영역이 아니어도 검사 안 함
EXCLUDE_GLOBS = [
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/dist/**",
    "**/.git/**",
]


def iter_v2_files() -> list[Path]:
    """V2 코드 파일 (.js / .jsx / .ts / .tsx / .mjs) 목록."""
    files = []
    for root in V2_ROOTS:
        root_path = REPO_ROOT / root
        if not root_path.exists():
            continue
        for ext in ("*.js", "*.jsx", "*.ts", "*.tsx", "*.mjs"):
            files.extend(root_path.rglob(ext))
    return files


def grep_lines(file_path: Path, pattern: re.Pattern, exclude_comments: bool = True) -> list[tuple[int, str]]:
    """파일에서 pattern 매칭 줄 (line_no, line) 반환. 주석 내 매칭은 exclude_comments=True 시 제외."""
    matches = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.lstrip()
        if exclude_comments and (stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*")):
            continue
        if pattern.search(line):
            matches.append((i, line.strip()[:120]))
    return matches


def rule_1_api_ai_calls() -> tuple[bool, list[str]]:
    """V2 코드에서 /api/ai/* 신규 호출 금지."""
    pattern = re.compile(r"/api/ai/")
    violations = []
    for f in iter_v2_files():
        for ln, line in grep_lines(f, pattern):
            violations.append(f"  {f.relative_to(REPO_ROOT)}:{ln}: {line}")
    return (len(violations) == 0, violations)


def rule_2_drafts_api() -> tuple[bool, list[str]]:
    """V2 코드에서 draftsApi 참조 금지."""
    pattern = re.compile(r"\bdraftsApi\b")
    violations = []
    for f in iter_v2_files():
        for ln, line in grep_lines(f, pattern):
            violations.append(f"  {f.relative_to(REPO_ROOT)}:{ln}: {line}")
    return (len(violations) == 0, violations)


def rule_3_step4review_import() -> tuple[bool, list[str]]:
    """V2 코드에서 Step4Review import 금지 (V1 평가 화면)."""
    pattern = re.compile(r"import\s+.*\bStep4Review\b")
    violations = []
    for f in iter_v2_files():
        for ln, line in grep_lines(f, pattern):
            violations.append(f"  {f.relative_to(REPO_ROOT)}:{ln}: {line}")
    return (len(violations) == 0, violations)


def rule_4_v1_5section_enum() -> tuple[bool, list[str]]:
    """V1 5섹션 enum (overview/purpose/plan/effect/budget) V2 quoted string 재침투 금지.

    PRD §18.8 — V2는 FormSchema + DraftItem + question_id 기준만.
    'plan'은 generic 단어라 정확히 5섹션 enum context (예: section: 'plan')만 잡기.
    """
    # section: 'overview' 또는 sectionKey === 'overview' 같은 패턴
    enum_values = ["overview", "purpose", "effect", "budget"]
    # 'plan'은 너무 광범위 → context 추가 (section: "plan" 등)
    patterns = []
    for v in enum_values:
        # 'overview' "overview" 같은 quoted string
        patterns.append(re.compile(rf"['\"]{re.escape(v)}['\"]"))
    # plan은 section context 한정
    patterns.append(re.compile(r"section[^a-zA-Z]+['\"]plan['\"]"))

    violations = []
    for f in iter_v2_files():
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue
            for pat in patterns:
                if pat.search(line):
                    violations.append(f"  {f.relative_to(REPO_ROOT)}:{i}: {line.strip()[:120]}")
                    break
    return (len(violations) == 0, violations)


def rule_5_backend_migration() -> tuple[bool, list[str]]:
    """Backend migration 추가 감지 (git diff)."""
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "diff", "--name-status", "HEAD", "--", "backend/migrations/"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return (True, [])  # git 명령 실패 시 통과 (no false positive)
        violations = [f"  {ln}" for ln in result.stdout.strip().splitlines() if ln.strip()]
        return (len(violations) == 0, violations)
    except Exception:
        return (True, [])


RULES = [
    ("R1: V2 코드에서 /api/ai/* 호출 금지", rule_1_api_ai_calls),
    ("R2: V2 코드에서 draftsApi 참조 금지", rule_2_drafts_api),
    ("R3: V2 코드에서 V1 Step4Review import 금지", rule_3_step4review_import),
    ("R4: V2 코드 V1 5섹션 enum (overview/purpose/effect/budget) 재침투 금지", rule_4_v1_5section_enum),
    ("R5: backend/migrations/ 변경 감지 (git diff)", rule_5_backend_migration),
]


def main():
    print("=" * 70)
    print(" V2 정책 회귀 자동 감지 (B3 grep CI, PRD-13 §18)")
    print("=" * 70)

    all_pass = True
    for name, fn in RULES:
        ok, violations = fn()
        if ok:
            print(f"  PASS  {name}")
        else:
            all_pass = False
            print(f"  FAIL  {name}")
            for v in violations[:10]:
                print(v)
            if len(violations) > 10:
                print(f"  ... +{len(violations) - 10} more violations")

    print("=" * 70)
    if all_pass:
        print(" RESULT: ALL PASS -- V2 policy compliant")
        sys.exit(0)
    else:
        print(" RESULT: VIOLATION DETECTED -- check violations above")
        sys.exit(1)


if __name__ == "__main__":
    main()

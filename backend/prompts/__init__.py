"""
프롬프트 파일 로딩 유틸.
load_prompt(name) -> (text: str, version: str)
"""
import os
import re

_PROMPT_DIR = os.path.dirname(__file__)


def load_prompt(name: str) -> tuple[str, str]:
    """
    prompts/{name}.md 를 읽어 (텍스트 전체, 버전 문자열) 반환.
    버전은 첫 줄 '# Version: vX.Y' 에서 파싱.
    파일 없으면 FileNotFoundError, 버전 파싱 실패 시 version='unknown'.
    """
    path = os.path.join(_PROMPT_DIR, f"{name}.md")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Prompt file not found: {path}")

    with open(path, encoding="utf-8") as f:
        text = f.read()

    version = "unknown"
    first_line = text.splitlines()[0] if text else ""
    m = re.match(r"#\s*Version:\s*(v[\d.]+)", first_line)
    if m:
        version = m.group(1)

    return text, version


PROMPT_NAMES = [
    "notice_analyst",
    "form_parser",
    "evidence_extractor",
    "company_analyzer",
    "evidence_mapper",
    "missing_material",
    "draft_writer",
    "draft_rewriter",
]


# task_type → prompt file 매핑 (audit_logger / provider 본체에서 사용)
# 현재는 task_type과 prompt filename이 1:1 동일 — 향후 다른 prompt 버전 사용 시 분리 가능
TASK_TYPE_TO_PROMPT = {
    "notice_analyst": "notice_analyst",
    "form_parser": "form_parser",
    "evidence_extractor": "evidence_extractor",
    "company_analyzer": "company_analyzer",
    "evidence_mapper": "evidence_mapper",
    "missing_material": "missing_material",
    "draft_writer": "draft_writer",
    "draft_rewriter": "draft_rewriter",
}


def get_prompt_version(task_type: str) -> str:
    """task_type → prompt 파일 → version 추출.

    매핑 없으면 'missing_prompt', 파일 없으면 'missing_prompt', 파싱 실패 시 'unknown'.
    None 반환 X — 항상 문자열 보장.
    """
    prompt_name = TASK_TYPE_TO_PROMPT.get(task_type)
    if not prompt_name:
        return "missing_prompt"
    try:
        _, version = load_prompt(prompt_name)
        return version
    except FileNotFoundError:
        return "missing_prompt"

"""
Mock AI Provider — 실제 LLM 없이 테스트용 응답 반환
v0.2: PRD §14.1 8 모듈 + V1 호환 5 메서드
"""
from datetime import datetime

from services.ai_provider import AIProvider
from services.audit_logger import audit_log


class MockProvider(AIProvider):
    provider_name = "mock"
    model_name = "mock"

    # ──────────────────────────────────────────────
    # v0.2 8 AI 모듈 (PRD §14.1)
    # ──────────────────────────────────────────────

    @audit_log(task_type="notice_analyst")
    async def notice_analyst(self, notice_text: str, *, request_id: str = "", session_id: str = "") -> dict:
        return {
            "notice_id": "mock_notice_001",
            "target": "중소·중견 제조기업 (업력 3년 이상)",
            "benefit": "총 사업비의 70% 이내, 최대 2억 원",
            "total_budget": "195.5억원 내외 (137개 과제 내외)",
            "deadline": "2026-06-15T18:00",
            "application_period_start": "2026-04-06",
            "submission_system": "IRIS (www.iris.go.kr)",
            "evaluation_criteria": [
                {"name": "기술성", "weight": 40, "scope": "section"},
                {"name": "사업성", "weight": 30, "scope": "section"},
                {"name": "수행역량", "weight": 30, "scope": "document"},
            ],
            "process_steps": [
                "신청·접수", "신청자격 검토", "선정평가 (서면/대면)",
                "이의신청", "최종선정", "협약 및 정부지원연구개발비 지급",
            ],
            "required_documents": ["사업계획서", "사업자등록증", "재무제표(2년)", "4대보험가입자명부"],
            "exclusion_conditions": ["최근 3년 내 동일 사업 수혜 기업 제외"],
            "important_keywords": ["AI", "데이터", "디지털 전환", "공정 자동화"],
            "ai_interpretation": {
                "선정 가능성을 높이는 핵심 요건": [
                    "필수 자격: 중소기업기본법 제2조 중소기업 + 기업부설연구소 보유 (연구개발전담부서 불인정)",
                    "비수도권 가점 2점 신설 → 사업장 위치 확인 후 활용",
                    "기술성 40점 비중이 가장 큼 → 기술 차별성·실현가능성 정량 지표 제시",
                ],
                "제안서 작성 전략": [
                    "글로벌협력형 — 해외협력기관과의 구체적 공동연구 계획·MOU 등 사전 확보 권장",
                    "정량적 사업화 지표(매출·고용·수출) 우선 제시",
                ],
                "탈락 방지 체크리스트": [
                    "⚠️ 접수 마감 18시 정각 — 17시 이전 제출 완료 권장 (전산 폭주 위험)",
                    "⚠️ 부채비율 1,000% 초과 또는 자본전액잠식 시 지원 제외 (예외조항 충족 시 가능)",
                    "신청자격 서류·가점 증빙은 추가/수정 제출 불가",
                ],
                "이 공고만의 특이점": [
                    "해외협력기관 10곳 중 선택 (프라운호퍼·MIT·퍼듀 등) → RFP 개별 검토",
                    "기술료 매출 기반 약정 경상기술료 — 사업 종료 후 5년간 매출 추적",
                ],
            },
            "extras": [
                {
                    "category": "가점",
                    "label": "비수도권 소재 기업 가점",
                    "value": "비수도권 소재 기업에 대한 가점 2점 신설",
                    "value_type": "text",
                    "source_page": 2,
                    "source_quote": "(가점 신설) 비수도권 소재 기업에 대한 가점 신설(2점)",
                    "confidence": 0.95,
                    "importance": "high",
                },
                {
                    "category": "가점",
                    "label": "정부 표창 가점 확대",
                    "value": "대통령·국무총리 포상 등 정부 표창 가점 인정 범위 확대",
                    "value_type": "text",
                    "source_page": 2,
                    "source_quote": "(가점 확대) 대통령, 국무총리 포상 및 시상을 포함하여 정부 표창 가점 인정 범위 확대",
                    "confidence": 0.92,
                    "importance": "medium",
                },
                {
                    "category": "사업 구조",
                    "label": "세부과제 3종",
                    "value": ["사전기획형", "예비연구형", "자유공모형(혁신기업형)"],
                    "value_type": "list",
                    "source_page": 3,
                    "source_quote": "사전기획형(사전연구) / 예비연구형(사전연구) / 자유공모형(혁신기업형)",
                    "confidence": 0.98,
                    "importance": "high",
                },
                {
                    "category": "사업 구조",
                    "label": "세부과제별 예산 분배",
                    "value": [
                        {"구분": "사전기획형", "예산": "110억원 내외", "과제수": "100개 내외"},
                        {"구분": "예비연구형", "예산": "5.5억원 내외", "과제수": "5개 내외"},
                        {"구분": "자유공모형(혁신기업형)", "예산": "80억원 내외", "과제수": "32개 내외"},
                    ],
                    "value_type": "table",
                    "source_page": 3,
                    "source_quote": "사전기획형 110억원 내외 100개 내외 / 예비연구형 5.5억원 내외 5개 내외 / 자유공모형(혁신기업형) 80억원 내외 32개 내외",
                    "confidence": 0.97,
                    "importance": "medium",
                },
                {
                    "category": "제도",
                    "label": "3책5공 적용",
                    "value": "연구자 최대 5개 과제(책임자 최대 3개) 동시수행 제한 제도 적용",
                    "value_type": "text",
                    "source_page": 5,
                    "source_quote": "본 사업은 3책5공 제도를 적용하는 사업임",
                    "confidence": 0.9,
                    "importance": "medium",
                },
            ],
            "source_pages": {"target": 3, "benefit": 4, "deadline": 11},
        }

    @audit_log(task_type="form_parser")
    async def form_parser(self, form_text: str, form_name: str = "", *, request_id: str = "", session_id: str = "") -> dict:
        return {
            "form_id": "form_mock_001",
            "form_name": form_name or "사업계획서.pdf",
            "source_file": form_name or "form.pdf",
            "sections": [
                {
                    "section_id": "S001", "title": "신청기업 개요", "order": 1,
                    "questions": [
                        {
                            "question_id": "I-1", "title": "기업 현황",
                            "requirement": "기업 개요 및 주요 사업 작성",
                            "constraints": {"max_length": 800, "min_length": 0},
                            "is_required": True, "is_table_item": False,
                            "source_page": 2, "order": 1,
                        },
                    ],
                },
            ],
        }

    @audit_log(task_type="evidence_extractor")
    async def evidence_extractor(
        self, ref_text: str, source_file: str = "", source_page: int = 0,
        *, request_id: str = "", session_id: str = "",
    ) -> dict:
        return {
            "items": [
                {
                    "evidence_id": "ev_mock_001",
                    "source_file": source_file or "ref.pdf",
                    "source_page": source_page or 1,
                    "type": "정량 실적",
                    "content": "[mock] 2024년 매출 142억, 영업이익률 11.4%",
                    "raw_text": "원문 텍스트 ...",
                    "embedding": [0.0] * 1024,  # bge-m3-ko 1024-dim placeholder
                },
            ]
        }

    @audit_log(task_type="company_analyzer")
    async def company_analyzer(
        self, company_files: list, notice_schema: dict,
        *, request_id: str = "", session_id: str = "",
    ) -> dict:
        return {
            "company": {
                "company_profile_id": "cp_mock_001",
                "name": "아진산업㈜",
                "representative": "홍길동",
                "industry": "제조업 / 자동차 부품",
                "founded": "2015-01-01",
                "capabilities": [
                    {
                        "capability_id": "cap_001", "name": "제조 데이터 분석 역량",
                        "description": "공정 데이터 기반 불량 원인 분석 4건 보유",
                        "confidence": 0.86, "source": "회사소개서.pdf p.4",
                    },
                ],
            },
            "fit_analysis": {
                "axes": [
                    {
                        "name": "기술성", "weight": 40, "score": 78,
                        "level": "높음", "level_color": "success",
                        "description": "AI 기반 제조 데이터 분석 경험",
                        "evidence": ["기술백서.pdf p.8"],
                        "recommendation": "PMS-AI 플랫폼 사례 강조",
                    },
                    {
                        "name": "사업성", "weight": 30, "score": 28,
                        "level": "낮음", "level_color": "error",
                        "description": "시장 규모 외부 자료 부족",
                        "evidence": [],
                        "recommendation": "시장조사 보고서·LOI 보강",
                    },
                    {
                        "name": "수행역량", "weight": 30, "score": 52,
                        "level": "중간", "level_color": "warning",
                        "description": "유사 프로젝트 경험 있으나 정량 실적 부족",
                        "evidence": ["프로젝트실적.xlsx"],
                        "recommendation": "성과보고서 정량 지표 보강",
                    },
                ],
                "overall_score": 56,
            },
        }

    @audit_log(task_type="evidence_mapper")
    async def evidence_mapper(
        self, form_schema: dict, evidence_list: list, notice_schema: dict,
        matching_threshold: float = 0.70,
        *, request_id: str = "", session_id: str = "",
    ) -> dict:
        return {
            "session_id": session_id or "session_mock_001",
            "question_mappings": [
                {
                    "question_id": "I-1",
                    "matched_evidence_ids": ["ev_mock_001"],
                    "used_evidence_ids": ["ev_mock_001"],
                    "confidence_score": 0.85,
                    "missing_evidence_types": [],
                    "match_status": "auto_confirmed",
                },
            ],
            "overall_missing_count": 0,
            "coverage_rate": 1.0,
        }

    @audit_log(task_type="missing_material")
    async def missing_material(
        self, mapping_result: dict,
        *, request_id: str = "", session_id: str = "",
    ) -> list:
        return [
            {
                "missing_id": "miss_mock_001",
                "session_id": session_id or "session_mock_001",
                "question_id": "II-1",
                "missing_type": "정량 데이터",
                "name": "최근 3년 시장 규모 통계",
                "description": "KOSIS 또는 산업연구원 자료 권장",
                "input_type": "file",
                "status": "open",
            },
        ]

    @audit_log(task_type="draft_writer")
    async def draft_writer(
        self, question: dict, matched_evidence: list,
        company_schema: dict, notice_schema: dict,
        writing_guidelines: list = None, constraints: dict = None,
        *, request_id: str = "", session_id: str = "",
    ) -> dict:
        max_length = (constraints or {}).get("max_length", 1000)
        evidence_ids = [e.get("evidence_id", "") for e in matched_evidence]
        title = question.get("title", "문항")
        content = (
            f"[Mock 초안] {title} — 기업 역량과 evidence를 바탕으로 작성된 답변입니다. "
            f"현재 매칭된 evidence {len(evidence_ids)}개를 인용하여 환각 없이 작성되었습니다."
        )
        return {
            "draft_id": f"draft_mock_{question.get('question_id', 'unknown')}",
            "session_id": session_id,
            "question_id": question.get("question_id", ""),
            "content": content[:max_length],
            "table_data": [],
            "used_evidence_ids": evidence_ids,
            "char_count": len(content),
            "status": "generated",
            "warnings": [],
            "ai_metadata": {
                "model": "mock",
                "prompt_version": "draft_writer_v001",
                "generated_at": datetime.utcnow().isoformat(),
            },
        }

    @audit_log(task_type="draft_rewriter")
    async def draft_rewriter(
        self, question_id: str, current_draft: str, user_message: str,
        evidence_list: list,
        *, request_id: str = "", session_id: str = "",
    ) -> dict:
        return {
            "suggestion": (
                f"[Mock 보완] '{user_message}' 요청 반영:\n\n"
                f"{current_draft}\n\n(요청 내용에 따라 강조점이 추가되었습니다.)"
            ),
            "diff_summary": f"사용자 요청 '{user_message}' 반영",
            "used_evidence_ids": [e.get("evidence_id", "") for e in evidence_list[:3]],
        }

    # ──────────────────────────────────────────────
    # V1 호환 5 메서드 (기존)
    # ──────────────────────────────────────────────

    @audit_log(task_type="generate_draft")
    async def generate_draft(self, notice_text: str, profile: dict, section: str) -> str:
        company = profile.get("company_name", "신청기업")
        templates = {
            "overview": f"{company}는 제조 분야 전문기업으로, 본 사업을 통해 경쟁력을 강화하고자 합니다.",
            "purpose": "현재 공정상 비효율 요소를 개선하여 생산성 향상 및 불량률 감소를 목표로 합니다.",
            "plan": "1단계: 현황 분석 및 설계 (1~2개월)\n2단계: 시스템 구축 및 테스트 (3~5개월)\n3단계: 안정화 및 운영 (6개월~)",
            "effect": "생산성 20% 향상, 불량률 50% 감소, 에너지 비용 15% 절감 기대",
            "budget": "총 사업비: 000백만원 / 정부지원금: 000백만원 / 자부담: 000백만원",
        }
        return templates.get(section, f"[Mock] {section} 내용을 작성해 주세요.")

    @audit_log(task_type="evaluate_draft")
    async def evaluate_draft(self, draft_text: str, notice_text: str) -> dict:
        return {
            "score": 72,
            "grade": "B",
            "feedback": "[Mock 평가] 초안의 기본 구조는 양호합니다. 구체적인 수치와 근거를 보강하면 점수가 올라갑니다.",
            "by_section": {
                "논리성": 75,
                "구체성": 65,
                "적합성": 80,
                "완성도": 68,
            },
        }

    @audit_log(task_type="improve_draft")
    async def improve_draft(self, draft_text: str, instruction: str) -> str:
        return f"[Mock 개선]\n{draft_text}\n\n(개선 지시: {instruction}에 따라 내용을 보완했습니다.)"

    @audit_log(task_type="check_completeness")
    async def check_completeness(self, uploaded_docs: dict, notice_text: str) -> dict:
        return {
            "total": 60,
            "by_section": {
                "신청기업 개요": 80,
                "사업 추진 필요성": 60,
                "기술개발 내용": 50,
                "기대효과": 55,
                "예산 사용계획": 45,
            },
            "missing_required": [
                {"section": "기술개발 내용", "field": "tech_description", "hint": "기술 개발 내용 상세 설명이 필요합니다."},
                {"section": "예산 사용계획", "field": "total_budget", "hint": "총사업비 정보가 필요합니다."},
            ],
            "missing_optional": [],
        }

    @audit_log(task_type="chat_review")
    async def chat_review(self, message: str, draft_content: str, notice_title: str, history: list) -> str:
        return (
            f"[Mock 검토] '{message}'에 대한 답변입니다.\n"
            "초안 내용을 검토한 결과, 구체적인 수치와 단계별 실행 계획을 보강하면 "
            "더 좋은 평가를 받을 수 있습니다. 특히 기대효과 항목에 정량적 지표를 추가하세요."
        )

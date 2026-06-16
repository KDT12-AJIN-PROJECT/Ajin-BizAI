"""
작성 가능률 계산 서비스

업로드된 문서와 인터뷰 답변에서 키워드를 찾아
각 평가 섹션의 준비 상태를 판단합니다.
"""

# 평가 섹션별로 필요한 정보 목록
REQUIRED_FIELDS_MAP = {
    "신청기업 개요": [
        "company_name", "representative", "business_type", "address"
    ],
    "사업 추진 필요성": [
        "current_problem", "market_size", "pain_point", "current_defect_rate"
    ],
    "기술개발 내용": [
        "target_system", "tech_description", "development_plan", "timeline"
    ],
    "사업화 계획": [
        "commercialization_plan", "target_market", "sales_strategy"
    ],
    "예산 사용계획": [
        "equipment_cost", "sw_cost", "consulting_cost", "total_budget"
    ],
    "기대효과": [
        "expected_productivity", "expected_defect_rate", "employment_effect", "sales_effect"
    ],
}

# 각 필드를 문서에서 찾는 키워드
FIELD_KEYWORDS = {
    "company_name":          ["기업명", "회사명", "상호"],
    "representative":        ["대표자", "대표이사", "대표"],
    "business_type":         ["업종", "업태", "사업 분야"],
    "address":               ["주소", "소재지"],
    "current_problem":       ["문제점", "개선", "필요성", "현황"],
    "market_size":           ["시장", "규모", "시장규모"],
    "pain_point":            ["불편", "애로", "어려움"],
    "current_defect_rate":   ["불량률", "ppm", "불량"],
    "target_system":         ["도입", "시스템", "솔루션", "ai", "mes", "erp"],
    "tech_description":      ["기술", "개발", "구현"],
    "development_plan":      ["계획", "단계", "일정"],
    "timeline":              ["월", "기간", "일정"],
    "commercialization_plan":["사업화", "판매", "매출"],
    "target_market":         ["시장", "고객", "타겟"],
    "sales_strategy":        ["전략", "판매", "마케팅"],
    "equipment_cost":        ["장비", "설비", "기자재"],
    "sw_cost":               ["sw", "소프트웨어", "솔루션"],
    "consulting_cost":       ["컨설팅", "용역"],
    "total_budget":          ["총사업비", "예산", "합계"],
    "expected_productivity": ["생산성", "생산량", "향상"],
    "expected_defect_rate":  ["불량률", "목표", "감소"],
    "employment_effect":     ["고용", "채용", "일자리"],
    "sales_effect":          ["매출", "수출", "증가"],
}


def check_field_in_text(field: str, all_text: str) -> bool:
    """특정 필드의 키워드가 텍스트에 있는지 확인"""
    keywords = FIELD_KEYWORDS.get(field, [field])
    text_lower = all_text.lower()
    return any(kw in text_lower for kw in keywords)


def calculate_completeness(
    notice_text: str,
    uploaded_docs: dict,
    interview_answers: dict,
) -> dict:
    """
    작성 가능률 계산

    반환:
    {
        "total": 64,            # 전체 가능률 (0~100)
        "by_section": {
            "신청기업 개요": 100,
            "사업 추진 필요성": 50,
            ...
        },
        "missing_required": [   # 필수 보완 항목
            {
                "section": "사업 추진 필요성",
                "field": "current_defect_rate",
                "hint": "현재 공정 불량률(PPM 또는 %) 정보가 필요합니다."
            },
            ...
        ],
        "missing_optional": []  # 선택 보완 항목
    }
    """
    # 모든 텍스트를 하나로 합침
    all_texts = [notice_text or ""]
    for doc_text in (uploaded_docs or {}).values():
        if isinstance(doc_text, str):
            all_texts.append(doc_text)
    for answer in (interview_answers or {}).values():
        if answer:
            all_texts.append(str(answer))

    all_text = " ".join(all_texts)

    section_scores = {}
    missing_required = []
    missing_optional = []

    # 섹션별 점수 계산
    REQUIRED_SECTIONS = ["신청기업 개요", "사업 추진 필요성", "기술개발 내용", "기대효과"]
    OPTIONAL_SECTIONS = ["사업화 계획", "예산 사용계획"]

    for section, fields in REQUIRED_FIELDS_MAP.items():
        found = sum(1 for f in fields if check_field_in_text(f, all_text))
        score = int(found / len(fields) * 100) if fields else 100
        section_scores[section] = score

        # 부족한 항목 수집
        for field in fields:
            if not check_field_in_text(field, all_text):
                hint = f"{section} 작성에 '{field}' 정보가 필요합니다."
                if section in REQUIRED_SECTIONS:
                    missing_required.append({
                        "section": section,
                        "field": field,
                        "hint": hint,
                    })
                else:
                    missing_optional.append({
                        "section": section,
                        "field": field,
                        "hint": hint,
                    })

    # 전체 평균 점수
    total = int(sum(section_scores.values()) / len(section_scores)) if section_scores else 0

    return {
        "total": total,
        "by_section": section_scores,
        "missing_required": missing_required[:10],   # 최대 10개
        "missing_optional": missing_optional[:5],    # 최대 5개
    }

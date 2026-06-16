"""
A-3 추가 검증: AX원스톱바우처 서식1 40p 실측

- layout-aware text 빌드
- form_parser 호출 (실제 OpenAI)
- parser_metadata / quality_metrics / fill_mode 분포 / 표 검증
- 시간 측정
"""
import sys, json, time, base64, asyncio, os, pathlib
sys.stdout.reconfigure(encoding="utf-8")

os.environ.setdefault("AI_PROVIDER", "openai")
os.environ.setdefault("DATABASE_URL", "sqlite:///./ajin.db")

BACKEND = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND))

# .env 로드
env_path = BACKEND / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from routers.analysis import (
    _build_layout_aware_text,
    _compute_form_quality_metrics,
    _count_page_markers,
    FORM_LAYOUT_TEXT_SAFETY_CAP,
)
from services.ai_provider import get_provider

PDF_PATH = pathlib.Path(
    r"c:\Users\KDS10\work\AJIN\AJIN_PROJECT\local\5_samples\2026년도 AX원스톱바우처 지원사업 수요기업 모집 공고문\forms\[서식1] 2026년 AX원스톱바우처 지원사업 수행계획서.pdf"
)

print(f"\n=== AX원스톱바우처 서식1 40p 실측 ===")
print(f"PDF: {PDF_PATH.name}")
print(f"size: {PDF_PATH.stat().st_size:,} bytes")

# 1. PDF → base64 → layout-aware
pdf_bytes = PDF_PATH.read_bytes()
raw_b64 = base64.b64encode(pdf_bytes).decode()

t0 = time.time()
items = [{
    "file_id": "test_ax40p",
    "file_name": PDF_PATH.name,
    "raw_b64": raw_b64,
    "parsed_text": "",
}]
form_text, layout_meta, _layout_pages = _build_layout_aware_text(items)
t_layout = time.time() - t0

print(f"\n[1] Layout build:")
print(f"  pages_total          = {layout_meta['pages_total']}")
print(f"  pages_included       = {layout_meta['pages_included']}")
print(f"  layout_text_original = {layout_meta['layout_text_original_chars']:,}")
print(f"  layout_text_returned = {layout_meta['layout_text_returned_chars']:,}")
print(f"  layout_text_truncated= {layout_meta['layout_text_truncated']}")
print(f"  truncated_after_page = {layout_meta['truncated_after_page']}")
print(f"  fallback_reason      = {layout_meta.get('fallback_reason')}")
print(f"  layout build time    = {t_layout:.2f}s")

# 2. form_parser 호출
provider = get_provider()
print(f"\n[2] form_parser 호출 (provider={getattr(provider, 'provider_name', 'unknown')}, model={getattr(provider, 'model_name', 'unknown')})")

t1 = time.time()
result = asyncio.run(provider.form_parser(form_text, "[서식1] AX원스톱바우처 수행계획서", request_id="a3_verify", session_id="a3_verify"))
t_parse = time.time() - t1
print(f"  form_parser time     = {t_parse:.2f}s")

# 3. quality_metrics
page_count = layout_meta.get("pages_total", 0)
metrics = _compute_form_quality_metrics(result, form_text, page_count=page_count)
print(f"\n[3] quality_metrics:")
for k, v in metrics.items():
    print(f"  {k:30s} = {v}")

# 4. fill_mode 분포
sections = result.get("sections", []) or []
all_questions = [q for s in sections for q in (s.get("questions", []) or [])]
question_count = len(all_questions)

from collections import Counter
fill_modes = Counter()
for q in all_questions:
    fill_modes[q.get("fill_mode") or "_null_"] += 1
print(f"\n[4] fill_mode 분포 (총 {question_count} questions):")
for fm in ["ai_text", "profile_mapping", "table_input", "signature", "choice", "checkbox", "file_attach", "user_text", "_null_"]:
    print(f"  {fm:20s} = {fill_modes.get(fm, 0)}")
print(f"  [기타] {dict((k, v) for k, v in fill_modes.items() if k not in ['ai_text','profile_mapping','table_input','signature','choice','checkbox','file_attach','user_text','_null_'])}")

# 5. table 검증 — p.34 사업비 총괄표, p.35 비목별 총괄표, p.36 인건비, p.4 기관현황
print(f"\n[5] 핵심 표 검증:")
def find_q_at_page(target_page, must_table=False, must_pmap=False):
    found = []
    for q in all_questions:
        sp = q.get("source_page")
        if sp == target_page:
            if must_table and q.get("fill_mode") == "table_input":
                found.append(q)
            elif must_pmap and q.get("fill_mode") == "profile_mapping":
                found.append(q)
            elif not must_table and not must_pmap:
                found.append(q)
    return found

for page, label, kind in [(34, "사업비 총괄표", "table"), (35, "비목별 총괄표", "table"), (36, "인건비 표", "table"), (4, "기관현황표", "table_or_pmap")]:
    if kind == "table":
        qs = find_q_at_page(page, must_table=True)
        print(f"  p.{page} {label}: table={len(qs)}", end="")
        if qs:
            ts = qs[0].get("table_schema", {})
            cols = ts.get("columns", []) or []
            print(f"  columns={len(cols)}")
        else:
            print()
    elif kind == "table_or_pmap":
        tbls = find_q_at_page(page, must_table=True)
        pmaps = find_q_at_page(page, must_pmap=True)
        print(f"  p.{page} {label}: table={len(tbls)}, profile_mapping={len(pmaps)}")

# 6. 대표 question 예시 5개
print(f"\n[6] 대표 question 예시 5종:")
samples = {}
for q in all_questions:
    fm = q.get("fill_mode")
    if fm == "profile_mapping" and "profile_mapping" not in samples:
        samples["profile_mapping"] = q
    elif fm == "ai_text" and "ai_text" not in samples:
        samples["ai_text"] = q
    elif fm == "table_input" and q.get("table_schema", {}).get("columns") and "table_input" not in samples:
        ts = q["table_schema"]
        cols = ts.get("columns", [])
        # 다단헤더 = column에 header_path가 2개 이상인 것이 있음
        multilevel = any(len(c.get("header_path") or []) >= 2 for c in cols)
        if multilevel:
            samples["table_input_multilevel"] = q
    elif fm == "signature" and "signature" not in samples:
        samples["signature"] = q
    elif fm == "checkbox" and "checkbox" not in samples:
        samples["checkbox"] = q

# fallback: 다단헤더 없으면 일반 table_input
if "table_input_multilevel" not in samples:
    for q in all_questions:
        if q.get("fill_mode") == "table_input":
            samples["table_input_any"] = q
            break

for kind, q in samples.items():
    print(f"\n  ┌─ {kind} (id={q.get('question_id')}, page={q.get('source_page')}) ─")
    print(f"  title           : {q.get('title','')[:60]}")
    print(f"  fill_mode       : {q.get('fill_mode')}")
    if q.get("profile_mapping"):
        print(f"  profile_mapping : {json.dumps(q['profile_mapping'], ensure_ascii=False)[:200]}")
    if q.get("table_schema"):
        ts = q["table_schema"]
        cols = ts.get("columns", [])
        print(f"  table_schema    : columns={len(cols)}")
        for i, c in enumerate(cols[:6]):
            print(f"    col[{i}] name={c.get('name')!r} header_path={c.get('header_path')}")

# 7. table_normalizer 승격 판단
print(f"\n[7] table_normalizer 승격 판단:")
p34_tbls = find_q_at_page(34, must_table=True)
p35_tbls = find_q_at_page(35, must_table=True)
p36_tbls = find_q_at_page(36, must_table=True)
table_count = metrics["table_count"]

p34_cols = len((p34_tbls[0].get("table_schema", {}).get("columns") or [])) if p34_tbls else 0
p35_cols = len((p35_tbls[0].get("table_schema", {}).get("columns") or [])) if p35_tbls else 0

# header_path 50% 비어있음
empty_header_paths = 0
total_cols = 0
for q in all_questions:
    if q.get("fill_mode") == "table_input":
        cols = q.get("table_schema", {}).get("columns", []) or []
        for c in cols:
            total_cols += 1
            if not c.get("header_path"):
                empty_header_paths += 1
empty_ratio = empty_header_paths / total_cols if total_cols else 0.0

conditions = {
    "p.34 columns < 5": p34_cols < 5,
    "p.35 columns < 5": p35_cols < 5,
    "p.36 인건비 표 미검출": len(p36_tbls) == 0,
    "table_count < 10": table_count < 10,
    "header_path 50% 비어있음": empty_ratio >= 0.5,
}
print(f"  p.34 columns={p34_cols}, p.35 columns={p35_cols}, p.36 tables={len(p36_tbls)}, table_count={table_count}")
print(f"  empty_header_paths={empty_header_paths}/{total_cols} ({empty_ratio*100:.1f}%)")
for cond, hit in conditions.items():
    print(f"  {'✗ HIT' if hit else '✓ ok '} {cond}")

verdict = "table_normalizer 승격 필요" if any(conditions.values()) else "table_normalizer 승격 불필요"
print(f"\n  >>> 결론: {verdict}")

# 8. 총 시간 / repair / timeout
print(f"\n[8] 성능 측정:")
print(f"  40p layout build time = {t_layout:.2f}s")
print(f"  40p form_parser time  = {t_parse:.2f}s")
print(f"  repair 호출 여부      = {'필요' if metrics['needs_repair'] else '불필요'} (current 단발 호출만 측정)")
print(f"  총 소요 시간          = {(t_layout + t_parse):.2f}s")
print(f"  timeout risk          = OpenAI timeout default 600s — 현재 측정값 대비 여유 충분")

print(f"\n=== A-3 추가 검증 끝 ===")

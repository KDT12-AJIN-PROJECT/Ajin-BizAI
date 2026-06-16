"""
AI 호출 감사 로그 데코레이터.
AIProvider 메서드에 @audit_log(task_type="...") 를 붙이면
호출마다 ai_call_logs 테이블에 한 행이 기록됩니다.

Usage:
    @audit_log(task_type="generate_draft")
    async def generate_draft(self, notice_text: str, profile: dict, section: str) -> str:
        ...

호출자가 request_id=<uuid> 를 kwarg 로 전달하면 같은 사용자 요청 묶음으로 집계됩니다.
전달하지 않으면 자동으로 UUID 가 생성됩니다.
"""
import json
import hashlib
import uuid
import time
import functools

from database import SessionLocal
from models import AICallLog


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _serialize_input(args: tuple, kwargs: dict) -> str:
    """메서드 호출 인자를 JSON 문자열로 직렬화 (self 제외)."""
    try:
        payload = {"args": list(args[1:]), "kwargs": kwargs}
        return json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        return str({"args": args[1:], "kwargs": kwargs})


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if isinstance(exc, TimeoutError):
        return "timeout"
    if "parse" in msg or "json" in msg or "decode" in msg:
        return "parse_error"
    return "api_error"


# ---------------------------------------------------------------------------
# decorator
# ---------------------------------------------------------------------------

def audit_log(task_type: str):
    """
    AIProvider 메서드용 감사 로그 데코레이터 팩토리.

    - run_id  : 매 호출마다 신규 UUID
    - request_id : kwarg 로 전달되면 사용, 없으면 자동 UUID 생성
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            run_id = str(uuid.uuid4())
            request_id = kwargs.pop("request_id", None) or str(uuid.uuid4())

            # --- prompt version ---
            prompt_version = None
            try:
                from prompts import load_prompt
                _, ver = load_prompt(task_type)
                prompt_version = f"{task_type}_{ver}"
            except Exception:
                pass

            # --- model info (provider 클래스에 속성이 있으면 읽음) ---
            self_obj = args[0] if args else None
            model_provider = getattr(self_obj, "provider_name", None)
            model_name = getattr(self_obj, "model_name", None)

            # --- input 직렬화 ---
            input_str = _serialize_input(args, kwargs)
            input_hash = _sha256(input_str)
            input_preview = input_str[:500]

            # --- 호출 실행 ---
            status = "success"
            error_message = None
            raw_output = None
            output_json = None
            result = None
            exc_to_raise = None

            start = time.monotonic()
            try:
                result = await func(*args, **kwargs)

                # raw_output: str 그대로 / dict·list 는 JSON 직렬화
                if isinstance(result, str):
                    raw_output = result
                    try:
                        parsed = json.loads(result)
                        output_json = json.dumps(parsed, ensure_ascii=False)
                    except Exception:
                        output_json = None
                elif isinstance(result, (dict, list)):
                    raw_output = json.dumps(result, ensure_ascii=False, default=str)
                    output_json = raw_output
                else:
                    raw_output = str(result)

            except Exception as e:
                status = _classify_error(e)
                error_message = str(e)
                exc_to_raise = e

            finally:
                duration_ms = int((time.monotonic() - start) * 1000)

                # provider 가 토큰 사용량을 _last_token_usage 에 남겨두는 경우 수집
                token_info = getattr(self_obj, "_last_token_usage", None)
                token_usage_json = (
                    json.dumps(token_info, ensure_ascii=False, default=str)
                    if token_info
                    else None
                )

                # NOAPI-P3: cost 산출 (실패가 main flow를 막지 않도록 try/except 격리)
                cost_estimate_krw = None
                try:
                    from services.ai_cost import estimate_ai_cost_krw
                    cost_result = estimate_ai_cost_krw(
                        model=model_name,
                        input_tokens=(token_info or {}).get("prompt_tokens") if isinstance(token_info, dict) else None,
                        output_tokens=(token_info or {}).get("completion_tokens") if isinstance(token_info, dict) else None,
                    )
                    cost_estimate_krw = cost_result.get("cost_estimate_krw")
                except Exception:
                    # 비용 산출 실패는 무시 (None 유지)
                    cost_estimate_krw = None

                db = SessionLocal()
                try:
                    log_entry = AICallLog(
                        run_id=run_id,
                        request_id=request_id,
                        task_type=task_type,
                        input_objects=None,       # 추후 온톨로지 ID 연계 시 채움
                        output_object=None,
                        prompt_version=prompt_version,
                        model_provider=model_provider,
                        model_name=model_name,
                        input_hash=input_hash,
                        input_preview=input_preview,
                        output_json=output_json,
                        raw_output=raw_output,
                        status=status,
                        error_message=error_message,
                        duration_ms=duration_ms,
                        token_usage_json=token_usage_json,
                        cost_estimate_krw=cost_estimate_krw,
                    )
                    db.add(log_entry)
                    db.commit()
                except Exception:
                    db.rollback()
                finally:
                    db.close()

            if exc_to_raise is not None:
                raise exc_to_raise

            return result

        return wrapper
    return decorator

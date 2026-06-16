"""
Migration 0002: ai_call_logs 테이블 추가
- 신규 테이블만 추가 (기존 테이블 손대지 않음)
- 검증: 컬럼, 인덱스 존재 + 기존 4개 테이블 row 수 전후 동일
- 실패 시 백업 롤백 + sys.exit(1)
"""
import sqlite3
import shutil
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'ajin.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')

EXPECTED_COLUMNS = [
    'id', 'run_id', 'request_id', 'task_type',
    'input_objects', 'output_object', 'prompt_version',
    'model_provider', 'model_name', 'input_hash', 'input_preview',
    'output_json', 'raw_output', 'status', 'error_message',
    'duration_ms', 'token_usage_json', 'cost_estimate_krw', 'created_at',
]

EXPECTED_INDEXES = [
    'ix_ai_call_logs_request_id',
    'ix_ai_call_logs_task_type',
    'ix_ai_call_logs_status',
    'ix_ai_call_logs_created_at',
]

GUARD_TABLES = ['drafts', 'notices', 'bookmarks', 'profile']


def get_row_counts(cur):
    return {t: cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in GUARD_TABLES}


def main():
    db_path = os.path.abspath(DB_PATH)
    backup_dir = os.path.abspath(BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)

    # 백업 경로 (이미 작업 전 필수 보고에서 완료됐지만 만약을 위해 중복 방지)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'ajin_0002_pre_{ts}.db')
    shutil.copy2(db_path, backup_path)
    print(f'[BACKUP] {backup_path}')

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # ── Pre-migration 보호 테이블 row 수 스냅샷 ──────────────
        pre_counts = get_row_counts(cur)
        print(f'[PRE] row counts: {pre_counts}')

        # ── ai_call_logs 이미 존재 여부 체크 ──────────────────────
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ai_call_logs'")
        if cur.fetchone():
            print('[SKIP] ai_call_logs already exists. Running verification only.')
        else:
            # ── 테이블 생성 ────────────────────────────────────────
            cur.execute("""
CREATE TABLE ai_call_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            TEXT NOT NULL,
    request_id        TEXT NOT NULL,
    task_type         TEXT NOT NULL,
    input_objects     TEXT,
    output_object     TEXT,
    prompt_version    TEXT,
    model_provider    TEXT,
    model_name        TEXT,
    input_hash        TEXT,
    input_preview     TEXT,
    output_json       TEXT,
    raw_output        TEXT,
    status            TEXT,
    error_message     TEXT,
    duration_ms       INTEGER,
    token_usage_json  TEXT,
    cost_estimate_krw REAL,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
            cur.execute('CREATE INDEX ix_ai_call_logs_request_id ON ai_call_logs(request_id)')
            cur.execute('CREATE INDEX ix_ai_call_logs_task_type  ON ai_call_logs(task_type)')
            cur.execute('CREATE INDEX ix_ai_call_logs_status     ON ai_call_logs(status)')
            cur.execute('CREATE INDEX ix_ai_call_logs_created_at ON ai_call_logs(created_at)')
            conn.commit()
            print('[OK] ai_call_logs table created.')

        # ── 검증 1: 컬럼 확인 ──────────────────────────────────────
        cur.execute('PRAGMA table_info(ai_call_logs)')
        actual_cols = [row[1] for row in cur.fetchall()]
        missing_cols = [c for c in EXPECTED_COLUMNS if c not in actual_cols]
        if missing_cols:
            raise RuntimeError(f'[ERROR] Missing columns: {missing_cols}')
        print(f'[VERIFY] columns OK: {actual_cols}')

        # ── 검증 2: 인덱스 확인 ────────────────────────────────────
        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='ai_call_logs'")
        actual_indexes = [row[0] for row in cur.fetchall()]
        missing_idx = [i for i in EXPECTED_INDEXES if i not in actual_indexes]
        if missing_idx:
            raise RuntimeError(f'[ERROR] Missing indexes: {missing_idx}')
        print(f'[VERIFY] indexes OK: {actual_indexes}')

        # ── 검증 3: 기존 테이블 row 수 보전 ────────────────────────
        post_counts = get_row_counts(cur)
        for t in GUARD_TABLES:
            if pre_counts[t] != post_counts[t]:
                raise RuntimeError(f'[ERROR] Row count changed for {t}: {pre_counts[t]} → {post_counts[t]}')
        print(f'[VERIFY] row counts unchanged: {post_counts}')

        print('[OK] Migration 0002 succeeded.')

    except Exception as e:
        print(f'[EXCEPTION] {e}')
        conn.close()
        shutil.copy2(backup_path, db_path)
        print('[ROLLBACK] Restored from backup')
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    main()

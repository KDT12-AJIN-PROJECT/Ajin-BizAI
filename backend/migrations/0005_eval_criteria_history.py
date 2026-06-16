"""
Migration 0005: eval_criteria_mappings.history JSON 컬럼 (v0.2.1 V2)

PRD-13 §19.3 옵션 A — 단일 row history JSON 보존.
v0.3 multi-user 전환 시 별도 테이블로 마이그레이션 검토 (옵션 B).

ALTER 1 컬럼:
  - history  TEXT DEFAULT '[]'     (JSON 배열, list of changes)

저장 구조 (예시):
  [
    {"at": "2026-05-11T18:00:00", "by": "user",
     "changes": {"scope": ["section", "question"]}}
  ]

기존 테이블 보호 (CLAUDE.md §4):
  - notices / drafts / bookmarks / profile / ai_call_logs / application_sessions
    row 수 전후 동일 검증

검증: 1 컬럼 추가 + 기존 row 수 보전. 실패 시 백업 롤백.
"""
import sqlite3
import shutil
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'ajin.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')

GUARD_TABLES = ['notices', 'drafts', 'bookmarks', 'profile', 'ai_call_logs',
                'application_sessions']

NEW_COLUMNS = [
    ('history', "TEXT DEFAULT '[]'"),
]


def get_row_counts(cur):
    counts = {}
    for t in GUARD_TABLES:
        try:
            counts[t] = cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        except sqlite3.OperationalError:
            counts[t] = None
    return counts


def main():
    db_path = os.path.abspath(DB_PATH)
    backup_dir = os.path.abspath(BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'ajin_0005_pre_{ts}.db')
    shutil.copy2(db_path, backup_path)
    print(f'[BACKUP] {backup_path}')

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        pre_counts = get_row_counts(cur)
        print(f'[PRE] guard table row counts: {pre_counts}')

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='eval_criteria_mappings'")
        if not cur.fetchone():
            raise RuntimeError('[ERROR] eval_criteria_mappings table missing (run 0003 first)')

        cur.execute('PRAGMA table_info(eval_criteria_mappings)')
        existing_cols = {row[1] for row in cur.fetchall()}
        for col_name, col_type in NEW_COLUMNS:
            if col_name in existing_cols:
                print(f'[SKIP] eval_criteria_mappings.{col_name} already exists')
                continue
            cur.execute(f'ALTER TABLE eval_criteria_mappings ADD COLUMN {col_name} {col_type}')
            print(f'[OK] ALTER eval_criteria_mappings ADD COLUMN {col_name}')

        conn.commit()

        # 검증 1: 컬럼 추가 확인
        cur.execute('PRAGMA table_info(eval_criteria_mappings)')
        cols_after = {row[1] for row in cur.fetchall()}
        for col_name, _ in NEW_COLUMNS:
            if col_name not in cols_after:
                raise RuntimeError(f'[ERROR] eval_criteria_mappings.{col_name} missing')
        print(f'[VERIFY] eval_criteria_mappings has {len(cols_after)} columns')

        # 검증 2: guard row 보전
        post_counts = get_row_counts(cur)
        for t in GUARD_TABLES:
            if pre_counts[t] != post_counts[t]:
                raise RuntimeError(
                    f'[ERROR] {t} row count changed: {pre_counts[t]} → {post_counts[t]}'
                )
        print(f'[VERIFY] guard table row counts preserved: {post_counts}')

        print('\n[SUCCESS] Migration 0005 complete.')

    except Exception as e:
        print(f'\n[FAIL] {e}')
        print(f'[ROLLBACK] Restoring from {backup_path}')
        conn.close()
        shutil.copy2(backup_path, db_path)
        sys.exit(1)

    conn.close()


if __name__ == '__main__':
    main()

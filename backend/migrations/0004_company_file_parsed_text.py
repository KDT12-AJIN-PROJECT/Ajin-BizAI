"""
Migration 0004: CompanyFile parsed_text + safety cap 메타 (Phase 4-H A3)

company_files ADD COLUMN (7개):
  - ext                              TEXT DEFAULT ''
  - parsed_text                      TEXT DEFAULT ''         (≤200K, A1 safety cap 정합)
  - char_count                       INTEGER DEFAULT 0       (원본 전체 char)
  - parsed_text_stored_char_count    INTEGER DEFAULT 0       (저장된 parsed_text 길이)
  - parsed_text_truncated            INTEGER DEFAULT 0       (BOOLEAN, 200K 초과 시 1)
  - parse_success                    INTEGER DEFAULT 1       (BOOLEAN)
  - warning                          TEXT

배경:
  - 0003 schema에 company_files 테이블은 있으나 parsed_text 컬럼 없음
  - A3에서 Step1Common이 실제 API 사용 → parsed_text 필요
  - A1과 동일한 safety cap 정책 (200K char) 적용 → 정합성

기존 테이블 보호 (CLAUDE.md §4):
  - notices / drafts / bookmarks / profile / ai_call_logs / application_sessions
    row 수 전후 동일 검증

검증: 7 컬럼 추가 + 기존 row 수 보전. 실패 시 백업 롤백.
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
    ('ext', 'TEXT DEFAULT \'\''),
    ('parsed_text', 'TEXT DEFAULT \'\''),
    ('char_count', 'INTEGER DEFAULT 0'),
    ('parsed_text_stored_char_count', 'INTEGER DEFAULT 0'),
    ('parsed_text_truncated', 'INTEGER DEFAULT 0'),
    ('parse_success', 'INTEGER DEFAULT 1'),
    ('warning', 'TEXT'),
]


def get_row_counts(cur):
    counts = {}
    for t in GUARD_TABLES:
        try:
            counts[t] = cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        except sqlite3.OperationalError:
            counts[t] = None  # 테이블 없음 — 무시
    return counts


def main():
    db_path = os.path.abspath(DB_PATH)
    backup_dir = os.path.abspath(BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'ajin_0004_pre_{ts}.db')
    shutil.copy2(db_path, backup_path)
    print(f'[BACKUP] {backup_path}')

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # ── Pre-migration row 수 스냅샷 ──────────────────────────
        pre_counts = get_row_counts(cur)
        print(f'[PRE] guard table row counts: {pre_counts}')

        # ── company_files 존재 확인 ──────────────────────────────
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='company_files'")
        if not cur.fetchone():
            raise RuntimeError('[ERROR] company_files table missing (run 0003 first)')

        # ── ALTER company_files ADD COLUMN ──────────────────────
        cur.execute('PRAGMA table_info(company_files)')
        existing_cols = {row[1] for row in cur.fetchall()}
        for col_name, col_type in NEW_COLUMNS:
            if col_name in existing_cols:
                print(f'[SKIP] company_files.{col_name} already exists')
                continue
            cur.execute(f'ALTER TABLE company_files ADD COLUMN {col_name} {col_type}')
            print(f'[OK] ALTER company_files ADD COLUMN {col_name}')

        conn.commit()

        # ── 검증 1: 7 컬럼 모두 존재 ───────────────────────────
        cur.execute('PRAGMA table_info(company_files)')
        cols_after = {row[1] for row in cur.fetchall()}
        for col_name, _ in NEW_COLUMNS:
            if col_name not in cols_after:
                raise RuntimeError(f'[ERROR] company_files.{col_name} missing')
        print(f'[VERIFY] company_files has {len(cols_after)} columns')

        # ── 검증 2: 기존 테이블 row 수 보전 ─────────────────────
        post_counts = get_row_counts(cur)
        for t in GUARD_TABLES:
            if pre_counts[t] != post_counts[t]:
                raise RuntimeError(
                    f'[ERROR] {t} row count changed: {pre_counts[t]} → {post_counts[t]}'
                )
        print(f'[VERIFY] guard table row counts preserved: {post_counts}')

        print('\n[SUCCESS] Migration 0004 complete.')

    except Exception as e:
        print(f'\n[FAIL] {e}')
        print(f'[ROLLBACK] Restoring from {backup_path}')
        conn.close()
        shutil.copy2(backup_path, db_path)
        sys.exit(1)

    conn.close()


if __name__ == '__main__':
    main()

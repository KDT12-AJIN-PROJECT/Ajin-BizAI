"""
Migration 0003: v0.2 schema (PRD §13.1 11종 + §13.10 운영 보조)

신규 테이블 (9개):
  - application_sessions   (PRD §13.9, 모든 산출물의 부모)
  - evidence_items         (PRD §13.3)
  - mapping_results        (PRD §13.4)
  - missing_materials      (PRD §13.5)
  - supplemental_materials (PRD §13.6)
  - fit_analyses           (PRD §13.x)
  - eval_criteria_mappings (PRD §13.8)
  - draft_items            (PRD §13.7, 기존 drafts 테이블과 별개)
  - company_files          (PRD §13.10, 운영 보조)

기존 테이블 ALTER (1개):
  - ai_call_logs ADD COLUMN data_classification, policy_check_result (test_03 §3.7.1)

기존 테이블 보호 (CLAUDE.md §4):
  - notices / drafts / bookmarks / profile / ai_call_logs (row 수 전후 동일 검증)

검증: 컬럼 + 인덱스 + 기존 row 수 보전. 실패 시 백업 롤백.
"""
import sqlite3
import shutil
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'ajin.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')

GUARD_TABLES = ['notices', 'drafts', 'bookmarks', 'profile', 'ai_call_logs']

NEW_TABLES = {
    'application_sessions': """
CREATE TABLE application_sessions (
    session_id                  TEXT PRIMARY KEY,
    user_id                     TEXT NOT NULL,
    company_profile_id          TEXT,
    notice_file_id              TEXT,
    form_file_id                TEXT,
    reference_file_ids          TEXT DEFAULT '[]',
    selected_company_file_ids   TEXT DEFAULT '[]',
    status                      TEXT NOT NULL DEFAULT 'created',
    current_step                INTEGER NOT NULL DEFAULT 1,
    notice_schema_json          TEXT DEFAULT '{}',
    form_schema_json            TEXT DEFAULT '{}',
    company_schema_json         TEXT DEFAULT '{}',
    drafts_preservation_policy  TEXT DEFAULT 'user_choice',
    created_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                  DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity_at            DATETIME,
    confirmed_step2_at          DATETIME,
    completed_at                DATETIME,
    abandoned_at                DATETIME,
    exported_at                 DATETIME,
    export_count                INTEGER DEFAULT 0,
    last_export_file_id         TEXT
)
""",
    'evidence_items': """
CREATE TABLE evidence_items (
    evidence_id              TEXT PRIMARY KEY,
    session_id               TEXT NOT NULL,
    source_file              TEXT NOT NULL,
    source_page              INTEGER,
    source_block             TEXT,
    type                     TEXT DEFAULT 'etc',
    content                  TEXT NOT NULL,
    raw_text                 TEXT,
    matched_questions        TEXT DEFAULT '[]',
    confidence_per_question  TEXT DEFAULT '{}',
    embedding_blob           TEXT,
    created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES application_sessions(session_id)
)
""",
    'mapping_results': """
CREATE TABLE mapping_results (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id              TEXT NOT NULL,
    question_id             TEXT NOT NULL,
    matched_evidence_ids    TEXT DEFAULT '[]',
    used_evidence_ids       TEXT DEFAULT '[]',
    confidence_score        REAL DEFAULT 0.0,
    missing_evidence_types  TEXT DEFAULT '[]',
    match_status            TEXT DEFAULT 'awaiting_user_confirm',
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES application_sessions(session_id)
)
""",
    'missing_materials': """
CREATE TABLE missing_materials (
    missing_id        TEXT PRIMARY KEY,
    session_id        TEXT NOT NULL,
    question_id       TEXT NOT NULL,
    missing_type      TEXT NOT NULL,
    name              TEXT NOT NULL,
    description       TEXT,
    input_type        TEXT DEFAULT 'both',
    status            TEXT DEFAULT 'open',
    supplemental_ids  TEXT DEFAULT '[]',
    resolved_at       DATETIME,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES application_sessions(session_id)
)
""",
    'supplemental_materials': """
CREATE TABLE supplemental_materials (
    supplemental_id  TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL,
    question_id      TEXT NOT NULL,
    missing_id       TEXT,
    type             TEXT NOT NULL,
    content          TEXT,
    file_id          TEXT,
    evidence_ids     TEXT DEFAULT '[]',
    status           TEXT DEFAULT 'uploaded',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES application_sessions(session_id),
    FOREIGN KEY (missing_id) REFERENCES missing_materials(missing_id)
)
""",
    'fit_analyses': """
CREATE TABLE fit_analyses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL UNIQUE,
    company_profile_id  TEXT NOT NULL,
    axes_json           TEXT DEFAULT '[]',
    overall_score       INTEGER,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES application_sessions(session_id)
)
""",
    'eval_criteria_mappings': """
CREATE TABLE eval_criteria_mappings (
    criteria_id        TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    criteria_name      TEXT NOT NULL,
    weight             INTEGER DEFAULT 0,
    scope              TEXT DEFAULT 'section',
    mapped_questions   TEXT DEFAULT '[]',
    mapping_type       TEXT DEFAULT 'direct',
    mapped_by          TEXT DEFAULT 'ai',
    confidence         REAL DEFAULT 0.0,
    reason             TEXT,
    source_page        INTEGER,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES application_sessions(session_id)
)
""",
    'draft_items': """
CREATE TABLE draft_items (
    draft_id           TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL,
    question_id        TEXT NOT NULL,
    content            TEXT DEFAULT '',
    table_data         TEXT DEFAULT '[]',
    used_evidence_ids  TEXT DEFAULT '[]',
    char_count         INTEGER DEFAULT 0,
    status             TEXT DEFAULT 'draft',
    warnings           TEXT DEFAULT '[]',
    ai_metadata        TEXT DEFAULT '{}',
    approved_at        DATETIME,
    approved_by        TEXT,
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES application_sessions(session_id)
)
""",
    'company_files': """
CREATE TABLE company_files (
    file_id              TEXT PRIMARY KEY,
    company_profile_id   TEXT NOT NULL,
    file_name            TEXT NOT NULL,
    file_size_bytes      INTEGER DEFAULT 0,
    file_storage_path    TEXT,
    file_type            TEXT DEFAULT '기타',
    uploaded_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
    uploaded_by          TEXT,
    status               TEXT DEFAULT 'active',
    expires_at           DATETIME,
    tags                 TEXT DEFAULT '[]'
)
""",
}

NEW_INDEXES = [
    'CREATE INDEX ix_application_sessions_user_id     ON application_sessions(user_id)',
    'CREATE INDEX ix_application_sessions_status      ON application_sessions(status)',
    'CREATE INDEX ix_evidence_items_session_id        ON evidence_items(session_id)',
    'CREATE INDEX ix_mapping_results_session_id       ON mapping_results(session_id)',
    'CREATE INDEX ix_mapping_results_question_id      ON mapping_results(question_id)',
    'CREATE INDEX ix_mapping_results_match_status     ON mapping_results(match_status)',
    'CREATE INDEX ix_missing_materials_session_id     ON missing_materials(session_id)',
    'CREATE INDEX ix_missing_materials_question_id    ON missing_materials(question_id)',
    'CREATE INDEX ix_missing_materials_status         ON missing_materials(status)',
    'CREATE INDEX ix_supplemental_materials_session_id ON supplemental_materials(session_id)',
    'CREATE INDEX ix_supplemental_materials_status    ON supplemental_materials(status)',
    'CREATE INDEX ix_fit_analyses_session_id          ON fit_analyses(session_id)',
    'CREATE INDEX ix_eval_criteria_mappings_session_id ON eval_criteria_mappings(session_id)',
    'CREATE INDEX ix_draft_items_session_id           ON draft_items(session_id)',
    'CREATE INDEX ix_draft_items_question_id          ON draft_items(question_id)',
    'CREATE INDEX ix_draft_items_status               ON draft_items(status)',
    'CREATE INDEX ix_company_files_company_profile_id ON company_files(company_profile_id)',
    'CREATE INDEX ix_company_files_status             ON company_files(status)',
]

# AICallLog 16 필드 보강 (test_03 §3.7.1)
AI_CALL_LOG_NEW_COLUMNS = [
    ('data_classification', 'TEXT'),  # PII / PHI / Public / Confidential
    ('policy_check_result', 'TEXT'),  # passed / failed / skipped (v1.0+)
]


def get_row_counts(cur):
    return {t: cur.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in GUARD_TABLES}


def main():
    db_path = os.path.abspath(DB_PATH)
    backup_dir = os.path.abspath(BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'ajin_0003_pre_{ts}.db')
    shutil.copy2(db_path, backup_path)
    print(f'[BACKUP] {backup_path}')

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        # ── Pre-migration row 수 스냅샷 ──────────────────────────
        pre_counts = get_row_counts(cur)
        print(f'[PRE] guard table row counts: {pre_counts}')

        # ── 신규 테이블 생성 (이미 있으면 SKIP) ─────────────────
        for table_name, ddl in NEW_TABLES.items():
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if cur.fetchone():
                print(f'[SKIP] {table_name} already exists')
                continue
            cur.execute(ddl)
            print(f'[OK] Created table: {table_name}')

        # ── 인덱스 생성 (이미 있으면 IGNORE) ─────────────────────
        for idx_ddl in NEW_INDEXES:
            try:
                cur.execute(idx_ddl)
            except sqlite3.OperationalError as e:
                if 'already exists' in str(e):
                    continue
                raise
        print(f'[OK] Created {len(NEW_INDEXES)} indexes')

        # ── ai_call_logs ALTER (16 필드 정합) ────────────────────
        cur.execute('PRAGMA table_info(ai_call_logs)')
        existing_cols = {row[1] for row in cur.fetchall()}
        for col_name, col_type in AI_CALL_LOG_NEW_COLUMNS:
            if col_name in existing_cols:
                print(f'[SKIP] ai_call_logs.{col_name} already exists')
                continue
            cur.execute(f'ALTER TABLE ai_call_logs ADD COLUMN {col_name} {col_type}')
            print(f'[OK] ALTER ai_call_logs ADD COLUMN {col_name}')

        conn.commit()

        # ── 검증 1: 신규 테이블 모두 존재 ───────────────────────
        for table_name in NEW_TABLES.keys():
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if not cur.fetchone():
                raise RuntimeError(f'[ERROR] Table missing after migration: {table_name}')
        print(f'[VERIFY] All {len(NEW_TABLES)} new tables exist')

        # ── 검증 2: ai_call_logs 16 필드 ───────────────────────
        cur.execute('PRAGMA table_info(ai_call_logs)')
        cols_after = {row[1] for row in cur.fetchall()}
        for col_name, _ in AI_CALL_LOG_NEW_COLUMNS:
            if col_name not in cols_after:
                raise RuntimeError(f'[ERROR] ai_call_logs.{col_name} missing')
        print(f'[VERIFY] ai_call_logs has {len(cols_after)} columns')

        # ── 검증 3: 기존 테이블 row 수 보전 ────────────────────
        post_counts = get_row_counts(cur)
        for t in GUARD_TABLES:
            if pre_counts[t] != post_counts[t]:
                raise RuntimeError(
                    f'[ERROR] Row count changed for {t}: '
                    f'{pre_counts[t]} → {post_counts[t]}'
                )
        print(f'[VERIFY] guard table row counts unchanged: {post_counts}')

        print('[OK] Migration 0003 succeeded.')

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

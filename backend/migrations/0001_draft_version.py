"""
Migration 0001: drafts 테이블 버전 관리 구조 전환
- version INTEGER NOT NULL DEFAULT 1 추가
- UNIQUE(notice_id, version) 복합 제약 추가
- status, submitted_at, result, result_date, result_memo 추가
- parent_draft_id, version_note, is_archived 추가
- 기존 행 → version=1, status='작성중' 마이그레이션
"""
import sqlite3
import hashlib
import json
import shutil
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'ajin.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'backups')


def row_checksum(row: dict) -> str:
    data = {
        'id': row['id'],
        'notice_id': row['notice_id'],
        'notice_snapshot': str(row['notice_snapshot']),
        'created_at': str(row['created_at']),
        'updated_at': str(row['updated_at']),
    }
    s = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def main():
    db_path = os.path.abspath(DB_PATH)
    backup_dir = os.path.abspath(BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)

    # ── Step 1: 마이그레이션 직전 백업 ─────────────────────────────
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'ajin_pre_migration_{ts}.db')
    shutil.copy2(db_path, backup_path)
    print(f'[BACKUP] {backup_path}')

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.cursor()

        # ── Step 2: 마이그레이션 전 데이터 스냅샷 ─────────────────
        cur.execute('SELECT id, notice_id, notice_snapshot, created_at, updated_at FROM drafts ORDER BY id')
        pre_rows = [dict(r) for r in cur.fetchall()]
        pre_count = len(pre_rows)
        pre_checksums = {r['id']: row_checksum(r) for r in pre_rows}
        print(f'[PRE]  row count = {pre_count}')
        print(f'[PRE]  checksums = {list(pre_checksums.items())}')

        # ── Step 3: 기존 데이터에서 notice_id별 버전 번호 계산 ───────
        # 같은 notice_id가 여러 행 있으면 id 오름차순으로 version=1,2,3 배정
        cur.execute('SELECT id, notice_id FROM drafts ORDER BY notice_id, id')
        all_rows = cur.fetchall()
        version_map: dict[int, int] = {}  # {id: version}
        version_counter: dict[str, int] = {}
        for row in all_rows:
            rid, nid = row[0], row[1]
            version_counter[nid] = version_counter.get(nid, 0) + 1
            version_map[rid] = version_counter[nid]
        print(f'[PLAN] version assignments: {version_map}')

        # ── Step 4: drafts_new 생성 ────────────────────────────────
        backup_table = f'drafts_backup_{ts}'
        cur.execute('PRAGMA foreign_keys = OFF')
        cur.execute(f"""
CREATE TABLE drafts_new (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    notice_id        TEXT    NOT NULL,
    notice_snapshot  TEXT    DEFAULT '{{}}',
    current_step     INTEGER DEFAULT 1,
    completed_steps  TEXT    DEFAULT '[]',
    uploads          TEXT    DEFAULT '{{}}',
    drafts           TEXT    DEFAULT '{{}}',
    version          INTEGER NOT NULL DEFAULT 1,
    status           TEXT    DEFAULT '작성중',
    submitted_at     DATETIME,
    result           TEXT,
    result_date      DATETIME,
    result_memo      TEXT,
    parent_draft_id  INTEGER,
    version_note     TEXT,
    is_archived      INTEGER DEFAULT 0,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(notice_id, version)
)
""")

        # 행별로 계산된 version으로 INSERT
        cur.execute('SELECT id, notice_id, notice_snapshot, current_step, completed_steps, uploads, drafts, created_at, updated_at FROM drafts ORDER BY id')
        all_draft_rows = cur.fetchall()
        for dr in all_draft_rows:
            rid = dr[0]
            ver = version_map[rid]
            cur.execute("""
INSERT INTO drafts_new (id, notice_id, notice_snapshot, current_step, completed_steps, uploads, drafts, version, status, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, '작성중', ?, ?)
""", (dr[0], dr[1], dr[2], dr[3], dr[4], dr[5], dr[6], ver, dr[7], dr[8]))
        conn.commit()

        cur.execute(f'ALTER TABLE drafts RENAME TO {backup_table}')
        cur.execute('ALTER TABLE drafts_new RENAME TO drafts')
        cur.execute('CREATE INDEX IF NOT EXISTS ix_drafts_notice_id ON drafts(notice_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS ix_drafts_status ON drafts(status)')
        cur.execute('CREATE INDEX IF NOT EXISTS ix_drafts_is_archived ON drafts(is_archived)')
        cur.execute('PRAGMA foreign_keys = ON')
        conn.commit()
        conn.commit()

        # ── Step 4: 마이그레이션 후 검증 ──────────────────────────
        cur.execute('SELECT id, notice_id, notice_snapshot, created_at, updated_at FROM drafts ORDER BY id')
        post_rows = [dict(r) for r in cur.fetchall()]
        post_count = len(post_rows)
        post_checksums = {r['id']: row_checksum(r) for r in post_rows}
        print(f'[POST] row count = {post_count}')
        print(f'[POST] checksums = {list(post_checksums.items())}')

        # row 수 검증
        if pre_count != post_count:
            print(f'[ERROR] Row count mismatch: pre={pre_count}, post={post_count}')
            conn.close()
            shutil.copy2(backup_path, db_path)
            print('[ROLLBACK] Restored from backup')
            sys.exit(1)

        # 체크섬 검증
        mismatches = []
        for rid, pre_cs in pre_checksums.items():
            post_cs = post_checksums.get(rid)
            if pre_cs != post_cs:
                mismatches.append({'id': rid, 'pre': pre_cs, 'post': post_cs})

        if mismatches:
            print(f'[ERROR] Checksum mismatch: {mismatches}')
            conn.close()
            shutil.copy2(backup_path, db_path)
            print('[ROLLBACK] Restored from backup')
            sys.exit(1)

        # version 컬럼 확인
        cur.execute('SELECT id, version, status FROM drafts ORDER BY id')
        version_check = [dict(r) for r in cur.fetchall()]
        print(f'[VERIFY] version/status: {version_check}')

        print(f'[OK] Migration succeeded. {post_count} rows, all checksums match.')
        print(f'[OK] Backup table: {backup_table}')

    except Exception as e:
        print(f'[EXCEPTION] {e}')
        conn.close()
        shutil.copy2(backup_path, db_path)
        print('[ROLLBACK] Restored from backup')
        raise

    finally:
        conn.close()


if __name__ == '__main__':
    main()

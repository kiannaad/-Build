-- 大肥鱼 Memory v2 · SQLite schema
-- 五层：L0 工作记忆（不落库）、L1 daily_digests、L2 memories、L3 events、L4 core_memories

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- L3 事件原始层：权威，只追加，turn_id 幂等
CREATE TABLE IF NOT EXISTS events (
  id              TEXT PRIMARY KEY,
  turn_id         TEXT NOT NULL UNIQUE,
  occurred_at     TEXT NOT NULL,
  source_platform TEXT NOT NULL DEFAULT 'local',
  session_id      TEXT,
  actor           TEXT NOT NULL,
  role            TEXT NOT NULL,
  content         TEXT NOT NULL,
  content_hash    TEXT NOT NULL,
  sensitivity     TEXT NOT NULL DEFAULT 'private'
                  CHECK (sensitivity IN ('public_safe','private','restricted')),
  fact_owner      TEXT NOT NULL DEFAULT 'observed'
                  CHECK (fact_owner IN ('explicit_user','user_confirmed','observed','inferred','assistant_generated')),
  status          TEXT NOT NULL DEFAULT 'active',
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id, occurred_at);

-- L2 语义记忆卡：可重建，必须引用来源事件
CREATE TABLE IF NOT EXISTS memories (
  id                 TEXT PRIMARY KEY,
  kind               TEXT NOT NULL,
  body               TEXT NOT NULL,
  tags               TEXT NOT NULL DEFAULT '',
  fact_owner         TEXT NOT NULL
                    CHECK (fact_owner IN ('explicit_user','user_confirmed','observed','inferred','assistant_generated')),
  importance         INTEGER NOT NULL DEFAULT 3 CHECK (importance BETWEEN 1 AND 5),
  confidence         REAL NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
  sensitivity        TEXT NOT NULL DEFAULT 'private'
                    CHECK (sensitivity IN ('public_safe','private','restricted')),
  status             TEXT NOT NULL DEFAULT 'candidate'
                    CHECK (status IN ('candidate','active','archived','deleted')),
  half_life_days     REAL NOT NULL DEFAULT 30 CHECK (half_life_days > 0),
  reinforcement      INTEGER NOT NULL DEFAULT 0 CHECK (reinforcement >= 0),
  last_reinforced_at TEXT,
  valid_from         TEXT,
  valid_to           TEXT,
  archived_at        TEXT,
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status, kind);
CREATE INDEX IF NOT EXISTS idx_memories_archived ON memories(archived_at);

CREATE TABLE IF NOT EXISTS memory_sources (
  memory_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  event_id  TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  relation  TEXT NOT NULL DEFAULT 'supports',
  PRIMARY KEY (memory_id, event_id)
);

CREATE TABLE IF NOT EXISTS memory_embeddings (
  memory_id    TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  model        TEXT NOT NULL,
  dim          INTEGER NOT NULL,
  vector       BLOB NOT NULL,
  content_hash TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  PRIMARY KEY (memory_id, model)
);

-- L4 核心记忆：只能经确认或受控晋升
CREATE TABLE IF NOT EXISTS core_memories (
  id           TEXT PRIMARY KEY,
  body         TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'proposed'
               CHECK (status IN ('proposed','confirmed','superseded','deleted')),
  version      INTEGER NOT NULL DEFAULT 1,
  confirmed_at TEXT,
  reason       TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

-- L1 每日摘要：只读当天事件与已确认记忆
CREATE TABLE IF NOT EXISTS daily_digests (
  day              TEXT PRIMARY KEY,
  summary          TEXT NOT NULL,
  mood             TEXT NOT NULL DEFAULT '',
  todos_json       TEXT NOT NULL DEFAULT '[]',
  source_event_ids TEXT NOT NULL DEFAULT '[]',
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_audit (
  id           TEXT PRIMARY KEY,
  action       TEXT NOT NULL,
  subject_type TEXT NOT NULL,
  subject_id   TEXT,
  detail_json  TEXT NOT NULL DEFAULT '{}',
  created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_time ON memory_audit(created_at);

CREATE TABLE IF NOT EXISTS jobs (
  id              TEXT PRIMARY KEY,
  kind            TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  status          TEXT NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','done','failed')),
  attempts        INTEGER NOT NULL DEFAULT 0,
  next_run_at     TEXT,
  last_error      TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_due ON jobs(status, next_run_at);

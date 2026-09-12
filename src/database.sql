-- Bản snapshot THAM KHẢO của schema Postgres — KHÔNG phải nguồn sự thật.
--
-- Nguồn sự thật là SQLAlchemy models (src/models/*.py), thực thi qua
-- Base.metadata.create_all() ở src/main.py lifespan. File này không được ai
-- load (không mount vào docker-entrypoint-initdb.d, không script nào đọc nó) —
-- chỉ để người đọc nhanh xem hình dạng schema mà không cần lần qua từng model.
--
-- Quyết định 2026-08-05 (theo review database.sql của Yến Nhi, UI/UX Lead):
-- trước đây file này và models đã lệch nhau (connections.user_id sai kiểu,
-- cluster_key/sync_cursors.key unique thiếu scope user_id — bug cross-user
-- thật). Từ giờ sửa model trước, generate lại file này sau, không sửa tay.
--
-- Generate lại bằng:
--   python -c "
--   from sqlalchemy.schema import CreateTable, CreateIndex
--   from sqlalchemy.dialects import postgresql
--   from src.db import Base
--   import src.main
--   dialect = postgresql.dialect()
--   lines = []
--   for table in Base.metadata.sorted_tables:
--       lines.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ';')
--       for index in table.indexes:
--           lines.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ';')
--   print('\n\n'.join(lines))
--   " > src/database.sql   # rồi dán lại phần header này vào đầu file

CREATE TABLE connections (
	id SERIAL NOT NULL,
	user_id VARCHAR(128) NOT NULL,
	provider VARCHAR(32) NOT NULL,
	account_label VARCHAR(255),
	provider_user_id VARCHAR(128),
	access_token_encrypted VARCHAR(2048),
	refresh_token_encrypted VARCHAR(2048),
	scopes VARCHAR(512),
	expires_at TIMESTAMP WITH TIME ZONE,
	connected_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_connection_user_provider UNIQUE (user_id, provider)
);

CREATE INDEX ix_connections_user_id ON connections (user_id);

CREATE TABLE sync_cursors (
	id SERIAL NOT NULL,
	user_id VARCHAR(128) NOT NULL,
	key VARCHAR(128) NOT NULL,
	value VARCHAR(255) NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_sync_cursor_user_key UNIQUE (user_id, key)
);

CREATE INDEX ix_sync_cursors_user_id ON sync_cursors (user_id);

CREATE TABLE tasks (
	id SERIAL NOT NULL,
	user_id VARCHAR(128) NOT NULL,
	cluster_key VARCHAR(64) NOT NULL,
	title VARCHAR(500) NOT NULL,
	detail TEXT NOT NULL,
	due_at TIMESTAMP WITH TIME ZONE,
	all_day BOOLEAN NOT NULL,
	ambiguous BOOLEAN NOT NULL,
	status VARCHAR(32) NOT NULL,
	source_count INTEGER NOT NULL,
	signal_strength FLOAT NOT NULL,
	calendar_event_id VARCHAR(255),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_task_user_cluster_key UNIQUE (user_id, cluster_key)
);

CREATE INDEX ix_tasks_user_status ON tasks (user_id, status);

CREATE INDEX ix_tasks_user_id ON tasks (user_id);

CREATE TABLE users (
	id SERIAL NOT NULL,
	email VARCHAR(255) NOT NULL,
	password_hash VARCHAR(255) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	last_synced_at TIMESTAMP WITH TIME ZONE,
	PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE TABLE clusters (
	id SERIAL NOT NULL,
	user_id VARCHAR(128) NOT NULL,
	cluster_key VARCHAR(64) NOT NULL,
	signal_strength FLOAT NOT NULL,
	due_at TIMESTAMP WITH TIME ZONE,
	ambiguous BOOLEAN NOT NULL,
	task_id INTEGER,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_cluster_user_cluster_key UNIQUE (user_id, cluster_key),
	FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE SET NULL
);

CREATE INDEX ix_clusters_user_id ON clusters (user_id);

CREATE TABLE messages (
	id SERIAL NOT NULL,
	user_id VARCHAR(128) NOT NULL,
	connection_id INTEGER,
	provider VARCHAR(32) NOT NULL,
	source_id VARCHAR(128) NOT NULL,
	external_id VARCHAR(255) NOT NULL,
	thread_id VARCHAR(255),
	author_id VARCHAR(128),
	author_name VARCHAR(255),
	is_self BOOLEAN NOT NULL,
	is_dm BOOLEAN NOT NULL,
	text TEXT NOT NULL,
	sent_at TIMESTAMP WITH TIME ZONE NOT NULL,
	deep_link VARCHAR(1024),
	ingested_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_message_provider_source_external UNIQUE (provider, source_id, external_id),
	FOREIGN KEY(connection_id) REFERENCES connections (id) ON DELETE SET NULL
);

CREATE INDEX ix_messages_user_sent_at ON messages (user_id, sent_at);

CREATE INDEX ix_messages_user_id ON messages (user_id);

CREATE TABLE runs (
	id SERIAL NOT NULL,
	user_id INTEGER NOT NULL,
	sources JSON NOT NULL,
	range_from TIMESTAMP WITH TIME ZONE NOT NULL,
	range_to TIMESTAMP WITH TIME ZONE NOT NULL,
	idempotency_key VARCHAR(128) NOT NULL,
	status VARCHAR(16) NOT NULL,
	error_message VARCHAR(1024),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT uq_run_user_idempotency_key UNIQUE (user_id, idempotency_key),
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_runs_user_id ON runs (user_id);

CREATE TABLE briefs (
	id SERIAL NOT NULL,
	run_id INTEGER NOT NULL,
	user_id INTEGER NOT NULL,
	summary TEXT NOT NULL,
	top_priority JSON NOT NULL,
	schedule_conflicts JSON NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE,
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_briefs_user_id ON briefs (user_id);

CREATE INDEX ix_briefs_run_id ON briefs (run_id);

CREATE TABLE cluster_messages (
	cluster_id INTEGER NOT NULL,
	message_id INTEGER NOT NULL,
	PRIMARY KEY (cluster_id, message_id),
	FOREIGN KEY(cluster_id) REFERENCES clusters (id) ON DELETE CASCADE,
	FOREIGN KEY(message_id) REFERENCES messages (id) ON DELETE CASCADE
);

CREATE INDEX ix_cluster_messages_message_id ON cluster_messages (message_id);

CREATE TABLE run_node_events (
	id SERIAL NOT NULL,
	run_id INTEGER NOT NULL,
	node VARCHAR(32) NOT NULL,
	status VARCHAR(16) NOT NULL,
	count INTEGER,
	message TEXT,
	at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE
);

CREATE INDEX ix_run_node_events_run_id ON run_node_events (run_id);

CREATE TABLE task_evidence (
	id SERIAL NOT NULL,
	task_id INTEGER NOT NULL,
	message_id INTEGER,
	provider VARCHAR(32) NOT NULL,
	evidence_quote TEXT NOT NULL,
	deep_link VARCHAR(1024) NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE CASCADE,
	FOREIGN KEY(message_id) REFERENCES messages (id) ON DELETE SET NULL
);

CREATE INDEX ix_task_evidence_task_id ON task_evidence (task_id);

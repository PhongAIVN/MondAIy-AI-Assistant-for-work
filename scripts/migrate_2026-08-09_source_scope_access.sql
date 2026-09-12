-- Explicit, revocable user -> source scope grants.
-- Deny by default: no rows means retrieval receives an empty scope list.
CREATE TABLE IF NOT EXISTS source_scope_access (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL,
    scope_id INTEGER NOT NULL REFERENCES source_scopes(id),
    status VARCHAR(16) NOT NULL DEFAULT 'confirmed',
    granted_by VARCHAR(128),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMPTZ,
    CONSTRAINT ck_source_scope_access_status CHECK (status IN ('pending', 'confirmed', 'revoked'))
);

CREATE INDEX IF NOT EXISTS ix_scope_access_active_user
    ON source_scope_access (user_id, status, valid_to);
CREATE INDEX IF NOT EXISTS ix_scope_access_scope
    ON source_scope_access (scope_id, status);

ALTER TABLE users ADD COLUMN IF NOT EXISTS program_access_level VARCHAR(1) NOT NULL DEFAULT 'C';
UPDATE users SET program_access_level = 'C' WHERE program_access_level IS NULL;

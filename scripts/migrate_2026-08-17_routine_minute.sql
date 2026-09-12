-- Store minute precision for user-configured routine briefings.
ALTER TABLE routines ADD COLUMN IF NOT EXISTS minute INTEGER NOT NULL DEFAULT 0;
ALTER TABLE routines ADD CONSTRAINT routines_minute_range CHECK (minute BETWEEN 0 AND 59);

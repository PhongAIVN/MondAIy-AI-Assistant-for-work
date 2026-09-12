-- Store the cadence selected for every-other-day routines.
ALTER TABLE routines ADD COLUMN IF NOT EXISTS interval_days INTEGER NOT NULL DEFAULT 2;
ALTER TABLE routines ADD CONSTRAINT routines_interval_days_range CHECK (interval_days BETWEEN 1 AND 31);

CREATE_EXPENSES = """
CREATE TABLE IF NOT EXISTS expenses (
    id            SERIAL PRIMARY KEY,
    fecha         DATE         NOT NULL,
    subcategoria  TEXT,
    categoria     TEXT,
    concepto      TEXT         NOT NULL,
    valor         INTEGER      NOT NULL,
    compartida    VARCHAR(2)   NOT NULL,
    valor_a_pagar NUMERIC(12,2),
    quien_pago_id INTEGER,
    debt_user_id  INTEGER,
    couple_id     INTEGER      REFERENCES couples(id),
    created_at    TIMESTAMPTZ  DEFAULT NOW()
);
"""

CREATE_COUPLES = """
CREATE TABLE IF NOT EXISTS couples (
    id          SERIAL PRIMARY KEY,
    invite_code VARCHAR(8) UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(50) NOT NULL,
    couple_id       INTEGER REFERENCES couples(id),
    chat_id         BIGINT UNIQUE,
    status          TEXT DEFAULT 'trial' CHECK (status IN ('trial', 'active', 'suspended')),
    status_updated_at TIMESTAMPTZ DEFAULT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_COUPLE_SETTINGS = """
CREATE TABLE IF NOT EXISTS couple_settings (
    couple_id        INTEGER NOT NULL REFERENCES couples(id),
    user_id          INTEGER NOT NULL REFERENCES users(id),
    split_percentage NUMERIC(5,4) NOT NULL,
    left_at          TIMESTAMPTZ NULL,
    PRIMARY KEY (couple_id, user_id)
);
"""

CREATE_INCOMES = """
CREATE TABLE IF NOT EXISTS incomes (
    id         SERIAL PRIMARY KEY,
    fecha      DATE         NOT NULL,
    concepto   TEXT         NOT NULL,
    valor      INTEGER      NOT NULL,
    user_id    INTEGER      NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ  DEFAULT NOW()
);
"""

DROP_OLD_EXPENSE_COLUMNS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='expenses' AND column_name='quien_pago') THEN
        ALTER TABLE expenses DROP COLUMN quien_pago;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='expenses' AND column_name='observacion') THEN
        ALTER TABLE expenses DROP COLUMN observacion;
    END IF;
END$$;
"""

ADD_COUPLE_ID_TO_EXPENSES = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='expenses' AND column_name='couple_id') THEN
        ALTER TABLE expenses ADD COLUMN couple_id INTEGER REFERENCES couples(id);
    END IF;
END$$;
"""

ADD_LEFT_AT_TO_COUPLE_SETTINGS = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='couple_settings' AND column_name='left_at') THEN
        ALTER TABLE couple_settings ADD COLUMN left_at TIMESTAMPTZ NULL;
    END IF;
END$$;
"""

MIGRATE_USERS_STATUS = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name='users' AND column_name='status') THEN
        UPDATE users SET status = 'active' WHERE status IS NULL;
    END IF;
END$$;
"""

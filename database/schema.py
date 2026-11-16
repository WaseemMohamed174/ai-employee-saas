"""Schema definitions for AI Employee (shop-assistant).

Two databases:
- platform.db: shared tables (USERS, STORES, API_KEYS, PLANS, SUBSCRIPTIONS, PERSONAS, ...).
- tenant_<slug>.db: per-store tables (STORE_DATA, CONVERSATIONS, MESSAGES, ANALYSES, ...).

No migrations. To change the schema, edit this file and re-run `python init_db.py`.
For tenant DBs, the connection manager re-creates them via `get_tenant_ddl()` when first opened.
"""
from __future__ import annotations

# ============== PLATFORM SCHEMA (platform.db) ==============

PLATFORM_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL DEFAULT '',
        is_email_verified INTEGER NOT NULL DEFAULT 0,
        is_platform_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",

    """
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_user_id INTEGER NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        default_persona_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (owner_user_id) REFERENCES users(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_stores_slug ON stores(slug)",
    "CREATE INDEX IF NOT EXISTS idx_stores_owner ON stores(owner_user_id)",

    """
    CREATE TABLE IF NOT EXISTS api_keys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER NOT NULL,
        key_hash TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL DEFAULT 'default',
        last_used_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        revoked_at TEXT,
        FOREIGN KEY (store_id) REFERENCES stores(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)",
    "CREATE INDEX IF NOT EXISTS idx_api_keys_store ON api_keys(store_id)",

    """
    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        data_limit_kb INTEGER NOT NULL,
        token_limit_month INTEGER NOT NULL,
        conversation_limit_month INTEGER NOT NULL,
        price_usd_cents INTEGER NOT NULL,
        is_trial INTEGER NOT NULL DEFAULT 0
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active',
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        ends_at TEXT,
        canceled_at TEXT,
        FOREIGN KEY (store_id) REFERENCES stores(id),
        FOREIGN KEY (plan_id) REFERENCES plans(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_subscriptions_store ON subscriptions(store_id)",

    """
    CREATE TABLE IF NOT EXISTS personas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        system_prompt_template TEXT NOT NULL
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS oauth_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        provider TEXT NOT NULL,
        provider_user_id TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE (provider, provider_user_id)
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS email_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        purpose TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_email_verifications_token ON email_verifications(token)",

    """
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER NOT NULL,
        amount_usd_cents INTEGER NOT NULL,
        status TEXT NOT NULL,
        stripe_charge_id TEXT,
        paid_at TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (store_id) REFERENCES stores(id)
    )
    """,
]

# ============== TENANT SCHEMA (tenant_<slug>.db) ==============

TENANT_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS store_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT,
        content TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'api',
        upload_log_id INTEGER,
        uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_store_data_item_id ON store_data(item_id)",

    """
    CREATE TABLE IF NOT EXISTS data_upload_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        item_count INTEGER NOT NULL DEFAULT 0,
        file_size_bytes INTEGER NOT NULL DEFAULT 0,
        uploaded_by_user_id INTEGER,
        uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_id TEXT,
        case_status TEXT NOT NULL DEFAULT 'active',
        first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
        banned_at TEXT,
        banned_reason TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_customers_external_id ON customers(external_id)",
    "CREATE INDEX IF NOT EXISTS idx_customers_case_status ON customers(case_status)",

    """
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        started_at TEXT NOT NULL DEFAULT (datetime('now')),
        last_message_at TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_conversations_customer ON conversations(customer_id)",

    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        store_data_id INTEGER,
        ai_decision_raw TEXT,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)",

    """
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        sentiment TEXT,
        is_complaint INTEGER NOT NULL DEFAULT 0,
        is_violation INTEGER NOT NULL DEFAULT 0,
        violation_type TEXT,
        severity TEXT,
        FOREIGN KEY (message_id) REFERENCES messages(id)
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        expires_at TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_violations_customer ON violations(customer_id)",

    """
    CREATE TABLE IF NOT EXISTS transfer_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        requested_at TEXT NOT NULL DEFAULT (datetime('now')),
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        FOREIGN KEY (conversation_id) REFERENCES conversations(id),
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS token_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER NOT NULL,
        prompt_tokens INTEGER NOT NULL DEFAULT 0,
        completion_tokens INTEGER NOT NULL DEFAULT 0,
        total_tokens INTEGER NOT NULL DEFAULT 0,
        cost_usd_micros INTEGER NOT NULL DEFAULT 0,
        recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (message_id) REFERENCES messages(id)
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'info',
        message TEXT NOT NULL,
        payload TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        dismissed_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(type)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_dismissed ON alerts(dismissed_at)",

    """
    CREATE TABLE IF NOT EXISTS store_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        persona_id INTEGER,
        alerts_thresholds_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,

    """
    CREATE TABLE IF NOT EXISTS violation_policies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL UNIQUE,
        threshold_count INTEGER NOT NULL DEFAULT 1,
        threshold_window_hours INTEGER NOT NULL DEFAULT 24,
        auto_apply INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_violation_policies_action ON violation_policies(action)",
]


def get_platform_ddl() -> list[str]:
    """Returns the list of CREATE TABLE statements for platform.db."""
    return list(PLATFORM_DDL)


def get_tenant_ddl() -> list[str]:
    """Returns the list of CREATE TABLE statements for tenant_<slug>.db."""
    return list(TENANT_DDL)

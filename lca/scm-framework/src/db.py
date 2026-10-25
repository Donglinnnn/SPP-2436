import json
import sqlite3

from .config import DATA_DIR, DB_PATH


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(pathways)")}
        if columns and "functional_unit_kg" not in columns:
            # Keep the pre-preview database recoverable before this additive migration.
            backup_path = DB_PATH.with_name("scm_projects.before-ui-v2.sqlite3")
            if not backup_path.exists():
                with sqlite3.connect(backup_path) as backup:
                    conn.backup(backup)
            conn.execute("ALTER TABLE pathways ADD COLUMN functional_unit_kg REAL NOT NULL DEFAULT 1")
        if columns and 'lca_settings_json' not in columns:
            # Additive migration; original project inputs and material snapshots stay intact.
            backup_path = DB_PATH.with_name('scm_projects.before-lca-v2.sqlite3')
            conn.commit()
            if not backup_path.exists():
                with sqlite3.connect(backup_path) as backup:
                    conn.backup(backup)
            conn.execute("ALTER TABLE pathways ADD COLUMN lca_settings_json TEXT NOT NULL DEFAULT '{}'")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pathways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_type TEXT NOT NULL,
                pathway_name TEXT NOT NULL,
                reference_product TEXT NOT NULL,
                system_boundary TEXT NOT NULL DEFAULT 'A1-A3',
                location TEXT,
                flow_chart_json TEXT NOT NULL,
                functional_unit_kg REAL NOT NULL DEFAULT 1,
                lca_settings_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pathway_id INTEGER NOT NULL,
                material_type TEXT NOT NULL,
                material_name TEXT NOT NULL,
                feedstock_burden_rule TEXT,
                note TEXT,
                FOREIGN KEY (pathway_id) REFERENCES pathways(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS process_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pathway_id INTEGER NOT NULL,
                process_name TEXT NOT NULL,
                process_order INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pathway_id) REFERENCES pathways(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS parameter_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                process_instance_id INTEGER NOT NULL,
                parameter_code TEXT NOT NULL,
                parameter_label TEXT,
                value TEXT,
                unit TEXT,
                provenance TEXT,
                source_note TEXT,
                FOREIGN KEY (process_instance_id)
                    REFERENCES process_instances(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS scm_items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                density_kg_m3 REAL NOT NULL,
                snapshot_json TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS recipe_records (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def row_to_dict(row: sqlite3.Row) -> dict[str, object]:
    return {key: row[key] for key in row.keys()}

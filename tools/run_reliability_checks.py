"""Smoke checks rapides de fiabilité pour l'application.

Usage:
  python tools/run_reliability_checks.py
  python tools/run_reliability_checks.py --require-test-users
"""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from app.models import Role, User
from app.rbac import ROLE_TEMPLATES, bootstrap_rbac

REQUIRED_TABLES = {
    "user",
    "role",
    "permission",
    "user_roles",
    "role_permissions",
}

CRITICAL_ROLES = {"admin_tech", "direction", "finance", "responsable_secteur"}
TEST_USERS = {"admin.test@mars.local", "directeur.test@mars.local"}


def _check_tables() -> None:
    existing = set(inspect(db.engine).get_table_names())
    missing = sorted(REQUIRED_TABLES - existing)
    if missing:
        raise RuntimeError(f"Tables manquantes: {', '.join(missing)}")


def _check_roles() -> None:
    existing = {r.code for r in Role.query.all()}
    missing_templates = sorted(CRITICAL_ROLES - set(ROLE_TEMPLATES.keys()))
    if missing_templates:
        raise RuntimeError(
            "Rôles critiques absents des templates RBAC: " + ", ".join(missing_templates)
        )

    missing_in_db = sorted(CRITICAL_ROLES - existing)
    if missing_in_db:
        raise RuntimeError("Rôles critiques absents en DB: " + ", ".join(missing_in_db))


def _check_test_users() -> None:
    existing = {
        u.email.strip().lower()
        for u in User.query.filter(User.email.in_(list(TEST_USERS))).all()
    }
    missing = sorted(TEST_USERS - existing)
    if missing:
        raise RuntimeError("Utilisateurs de test manquants: " + ", ".join(missing))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-test-users",
        action="store_true",
        help="Échoue si les comptes de test admin/directeur n'existent pas.",
    )
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        db.create_all()
        bootstrap_rbac()

        _check_tables()
        _check_roles()

        client = app.test_client()
        resp = client.get("/healthz")
        if resp.status_code != 200:
            raise RuntimeError(f"/healthz KO (status={resp.status_code})")

        if args.require_test_users:
            _check_test_users()

    print("[OK] reliability checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

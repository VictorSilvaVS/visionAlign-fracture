"""
Script para criar usuários de fábrica no VisionAlign.
Execute: python create_users.py
"""
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.database import Database
from werkzeug.security import generate_password_hash

SENHA = "canpack@2026"

USERS = [
    {'username': 'wahser22', 'first_name': 'Wahser', 'last_name': '22'},
    {'username': 'wahser23', 'first_name': 'Wahser', 'last_name': '23'},
]

def reset_factory_users():
    db = Database()

    for user in USERS:
        username = user['username']

        # Apaga se existir
        try:
            with db.conn:
                db.conn.execute("DELETE FROM users WHERE username = ?", (username,))
            print(f"[DEL] Usuário '{username}' removido (se existia).")
        except Exception as e:
            print(f"[ERRO] Falha ao remover '{username}': {e}")

        # Recria com nova senha
        hashed = generate_password_hash(SENHA)
        email = f"{username}@fabrica.local"
        success = db.create_user(
            username=username,
            password=hashed,
            email=email,
            first_name=user['first_name'],
            last_name=user['last_name'],
            is_admin=0
        )

        if success:
            print(f"[OK]  Usuário '{username}' criado | Senha: {SENHA}")
        else:
            print(f"[ERRO] Falha ao criar '{username}'.")

    db.close()
    print("\nConcluído.")

if __name__ == "__main__":
    print("=== Reset de Usuários VisionAlign ===\n")
    reset_factory_users()

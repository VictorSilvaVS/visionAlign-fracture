import os
import sys

# Adicionar o diretório raiz ao path para importar módulos existentes
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from utils.database import Database

class DatabaseService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseService, cls).__new__(cls)
            cls._instance.db = Database()
        return cls._instance

    def get_db(self):
        return self.db

db_service = DatabaseService()

def get_db():
    return db_service.get_db()

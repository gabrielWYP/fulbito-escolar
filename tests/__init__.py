import os
import tempfile

# Aislar la BD de los tests ANTES de importar la app.
_tmp = tempfile.mkdtemp(prefix="fulbito-tests-")
os.environ["DATA_DIR"] = _tmp
os.environ["DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ.setdefault("ADMIN_PASSWORD", "secreto-test")
os.environ.setdefault("SESSION_SECRET", "clave-de-sesion-para-tests")
os.environ.setdefault("SEED_DEMO", "false")

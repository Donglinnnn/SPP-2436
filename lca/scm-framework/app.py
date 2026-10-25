from src.application import create_app
from src.config import FLASK_HOST, FLASK_PORT
from src.db import init_db

app = create_app()

if __name__ == "__main__":
    init_db()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, use_reloader=False)

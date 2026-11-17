# run.py
# Servidor de DESARROLLO (Werkzeug). En contenedores se usa Gunicorn
# (ver gunicorn.conf.py): el servidor de Werkzeug no es para produccion y su
# modo debug permite ejecutar codigo remoto desde el navegador.

import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        # Antes debug=True fijo. Ahora se activa a proposito con FLASK_DEBUG=1.
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )

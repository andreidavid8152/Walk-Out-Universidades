from flask import Flask
from routes.main import main_bp
from routes.mapa_calor_universidades import mapa_uni_bp
from routes.mapa_calor_colegios import mapa_colegios_bp
from routes.mapa_calor_empresas import mapa_empresas_bp

app = Flask(__name__)
app.register_blueprint(main_bp)
app.register_blueprint(mapa_uni_bp)
app.register_blueprint(mapa_colegios_bp)
app.register_blueprint(mapa_empresas_bp)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

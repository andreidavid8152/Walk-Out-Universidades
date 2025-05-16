from flask import Blueprint

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    print("✅ Ruta '/' accedida correctamente")
    return "¡Todo bien desde Flask Blueprint!"

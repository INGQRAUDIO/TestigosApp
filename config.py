"""
Configuración central del sistema de Testigos.
Edita SOLO este archivo para adaptar rutas y reglas a tu servidor.
"""
import re

# --- Rutas ---------------------------------------------------------------
# Carpetas raíz donde viven los audios, agrupadas por "colección". Cada
# colección aparece como un botón en la app web (ej. "Históricos", "Actuales").
# Dentro de una colección puedes tener una sola ruta o varias:
#   - Si tiene UNA sola ruta, la app entra directo a sus subcarpetas al
#     elegir el botón (igual que el comportamiento actual).
#   - Si tiene VARIAS rutas, la app las muestra primero como si fueran
#     carpetas (usando su "nombre"), y de ahí para adentro cada una.
# Cada ruta puede tener subcarpetas por programa, por fecha, o todo junto —
# el indexador las recorre todas igual que antes.
RECORDINGS_ROOTS = {
    "Históricos": [
        {"nombre": "2026", "ruta": r"D:\L\2026"},
        {"nombre": "2025", "ruta": r"D:\L\2025"},
    ],
    "Actuales": [
        {"nombre": "Testigo Archivos", "ruta": r"D:\I\Testigos Archivos"},
    ],
}

# Dónde vive la base de datos SQLite con el índice de archivos.
DB_PATH = r"D:\TestigosApp\testigos.db"

# --- Tipos de archivo a indexar -------------------------------------------
AUDIO_EXTENSIONS = {".mp3", ".wav", ".wma", ".m4a"}

# --- Cómo extraer "programa" y "fecha" del nombre del archivo -------------
# Total Recorder suele nombrar archivos como: NombrePrograma_20240527_115500.mp3
# Si tus archivos siguen otro patrón, ajusta este regex.
# Grupos esperados: programa, fecha (YYYYMMDD), hora (HHMMSS) - los que no
# apliquen pueden omitirse del regex, el indexador usa metadata del archivo
# (fecha de modificación, carpeta contenedora) como respaldo.
FILENAME_PATTERN = re.compile(
    r"(?P<programa>.+?)[_\-\s]+(?P<fecha>\d{8})(?:[_\-\s]+(?P<hora>\d{6}))?",
)

# Si el nombre no coincide con el patrón de arriba, se usa el nombre de la
# carpeta contenedora como "programa" (útil si organizas por subcarpetas).
USE_FOLDER_NAME_AS_FALLBACK = True

# --- Autenticación ----------------------------------------------------------
AUTH_CONFIG_PATH = r"D:\TestigosApp\auth_config.yaml"

# --- Límite de resultados mostrados por defecto (evita cargar miles) -------
DEFAULT_RESULT_LIMIT = 300
"""
app.py — Portal de Testigos de transmisión (versión nube)
Ejecutar con:  streamlit run app.py
Esta es la versión que vive en GitHub + Streamlit Cloud. No lee nada
del disco local — todo el catálogo viene de Supabase, y los archivos
de audio se piden bajo demanda vía app_local.py + Cloudflare R2.

Credenciales: se leen ÚNICAMENTE de st.secrets (nunca de variables de
entorno ni de archivos .env). Localmente eso significa un archivo
.streamlit/secrets.toml junto a este script (ver secrets.toml.example);
en Streamlit Cloud, se configuran en Settings -> Secrets de la app.
"""
import os
import time
import traceback
from datetime import date, datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from supabase import create_client

import config

st.set_page_config(
    page_title="Testigos 90.9 FM",
    page_icon=" ",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* --- Fondo negro en toda la app (respaldo del theme de config.toml) --- */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stSidebar"],
[data-testid="stToolbar"] {
    background-color: #000000 !important;
}

/* --- Fuente global: Bebas Neue en absolutamente todo el texto de la app --- */
html, body, .stApp, .stApp * {
    font-family: 'Bebas Neue', sans-serif !important;
}

/* Los íconos de Streamlit (flechita de abrir/cerrar el sidebar, chevrons de
   expanders, etc.) se dibujan con una fuente de símbolos especial
   (Material Symbols) — el nombre del ícono (ej. "keyboard_double_arrow_right")
   es en realidad el texto que ESA fuente convierte en el dibujo. La regla de
   arriba se lo pisó con Bebas Neue, y por eso se veía el nombre en vez de la
   flecha. Esta regla, al ir después, le devuelve su fuente correcta. */
[data-testid="stIconMaterial"],
span[class*="material-symbols"],
i[class*="material-symbols"],
[class*="material-icons"] {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] button {
    border: none;
    background: transparent;
    width: 100%;
    text-align: center;
    padding: 0;
}
div[data-testid="stVerticalBlockBorderWrapper"] button p {
    font-size: 0.9rem;
    white-space: normal;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(button):hover {
    border-color: #22c55e;
}

/* --- Lista de carpetas estilo explorador de archivos (Dropbox/Windows) --- */
.st-key-carpeta_lista div[data-testid="stButton"] button {
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    text-align: left !important;
    background: transparent !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 6px 10px !important;
    width: 100% !important;
}
.st-key-carpeta_lista div[data-testid="stButton"] button div {
    justify-content: flex-start !important;
    width: 100% !important;
}
.st-key-carpeta_lista div[data-testid="stButton"] button p {
    text-align: left !important;
    font-size: 0.95rem !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
.st-key-carpeta_lista div[data-testid="stButton"] button:hover {
    background-color: rgba(255, 255, 255, 0.08) !important;
}
.st-key-carpeta_lista div[data-testid="stButton"] {
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

/* --- Lista de archivos: encabezado + filas con columnas REALES (st.columns),
   igual que el breadcrumb. El nombre del archivo es el botón clickeable;
   fecha/duración/tamaño son texto plano en su propia columna. Nada de
   relleno con espacios ni fuentes monoespaciadas — la alineación la
   garantiza el propio layout de columnas de Streamlit. --- */
.st-key-encabezado_archivos {
    color: rgba(255, 255, 255, 0.5);
    font-size: 0.8rem;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    margin-bottom: 4px;
}
.st-key-archivo_lista div[data-testid="stButton"] button {
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    justify-content: flex-start !important;
    text-align: left !important;
    background: transparent !important;
    border: none !important;
    border-radius: 4px !important;
    padding: 6px 10px 6px 34px !important;
    width: 100% !important;
    font-weight: 400 !important;
}
/* El ícono se dibuja con un pseudo-elemento + mask-image (no background-image):
   así controlamos el color desde CSS (background-color de abajo) sin importar
   qué color de relleno traiga el onda.svg original — si el SVG viene con
   relleno oscuro, con background-image se "perdía" contra el fondo oscuro
   de la app y parecía que no cargaba. Con mask, siempre se ve. */
.st-key-archivo_lista div[data-testid="stButton"] button::before {
    content: "";
    position: absolute;
    left: 8px;
    top: 50%;
    transform: translateY(-50%);
    width: 18px;
    height: 18px;
    background-color: rgba(255, 255, 255, 0.75);
    -webkit-mask-image: url("app/static/onda.svg");
    mask-image: url("app/static/onda.svg");
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-size: contain;
    mask-size: contain;
    -webkit-mask-position: center;
    mask-position: center;
    pointer-events: none;
}
.st-key-archivo_lista div[data-testid="stButton"] button div {
    justify-content: flex-start !important;
    width: 100% !important;
}
.st-key-archivo_lista div[data-testid="stButton"] button p {
    text-align: left !important;
    font-size: 1.15rem !important;
    font-weight: 400 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
.st-key-archivo_lista div[data-testid="stButton"] button:hover {
    background-color: rgba(255, 255, 255, 0.08) !important;
}

/* --- Check del archivo seleccionado: mismo truco de mask-image que el ícono
   de onda.svg de arriba, así hereda el verde de acento (#7bc90f) sin importar
   el color de relleno que traiga check.svg. Aplica a CUALQUIER botón cuya key
   empiece con "filasel_" (una por archivo, dinámica según su path). --- */
[class*="st-key-filasel_"] button {
    padding-right: 34px !important;
}
[class*="st-key-filasel_"] button::after {
    content: "";
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    width: 18px;
    height: 18px;
    background-color: #7bc90f;
    -webkit-mask-image: url("app/static/check.svg");
    mask-image: url("app/static/check.svg");
    -webkit-mask-repeat: no-repeat;
    mask-repeat: no-repeat;
    -webkit-mask-size: contain;
    mask-size: contain;
    -webkit-mask-position: center;
    mask-position: center;
    pointer-events: none;
}
.st-key-archivo_lista div[data-testid="stHorizontalBlock"] {
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.st-key-archivo_lista div[data-testid="stHorizontalBlock"] > div {
    display: flex;
    align-items: center;
}


/* --- Botón "volver": ícono flecha.svg en vez del emoji ↩️ --- */
.st-key-miga_inicio button {
    background-image: url("app/static/flecha.svg");
    background-repeat: no-repeat;
    background-position: center;
    background-size: 20px 20px;
}
.st-key-miga_inicio button p {
    visibility: hidden;   /* el texto sigue ahí para accesibilidad, solo se oculta visualmente */
}

/* --- Fila del breadcrumb: gap más chico entre el botón "volver" y el
   primer segmento de ruta, para que queden pegados uno al otro --- */
.st-key-fila_migas div[data-testid="stHorizontalBlock"] {
    gap: 0.15rem !important;
}
.st-key-fila_migas div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    width: auto !important;
    min-width: 0 !important;
    flex: 0 0 auto !important;
}

/* --- Botón "Descargar ahora" (link_button, key=btn_descargar): texto en
   negritas y verde. Sin animación — esa se movió al botón "Descargar" de
   abajo, que es el que el usuario ve/clickea primero. --- */
.st-key-btn_descargar a,
.st-key-btn_descargar a p,
.st-key-btn_descargar a span {
    color: #7bc90f !important;
    font-weight: 700 !important;
}

/* --- Botón "Descargar" (el que dispara la preparación del archivo, key
   dinámico "pedir_<path>" — por eso el selector usa *= en vez del nombre
   exacto, así aplica sin importar qué archivo esté seleccionado). Corre la
   animación "roll-in" UNA SOLA VEZ (no "infinite"): así llama la atención
   al aparecer, pero no se queda repitiéndose en loop mientras el usuario
   mira la pantalla. "forwards" mantiene el estado final (visible, en su
   lugar) en vez de volver de golpe al estado inicial al terminar. --- */
[class*="st-key-pedir_"] button {
    display: inline-block;
    animation: roll-in 2s ease 1;
    animation-fill-mode: forwards;
}
@keyframes roll-in {
    0% {
        opacity: 0;
        transform: translateX(-100%) rotate(-120deg);
    }
    100% {
        opacity: 1;
        transform: translateX(0px) rotate(0deg);
    }
}

/* --- Oculta la barra de herramientas nativa (ojo/descargar/buscar/ampliar)
   que Streamlit muestra al pasar el mouse sobre tablas y otros widgets --- */
div[data-testid="stElementToolbar"] {
    display: none !important;
}

/* --- Botones de colección (Históricos / Actuales) --- */
.st-key-fila_colecciones {
    margin-bottom: 1rem;
}
.st-key-fila_colecciones button {
    font-size: 1.1rem !important;
    padding: 0.6rem 1rem !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 6px !important;
}
.st-key-fila_colecciones button:hover {
    border-color: #7bc90f !important;
}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Credenciales de Supabase (URL + llave ANON, nunca la service_role aquí)
# ----------------------------------------------------------------------------
def obtener_credencial(nombre: str) -> str:
    if nombre not in st.secrets:
        st.error(
            f"Falta configurar '{nombre}' en Secrets. Localmente: crea "
            f".streamlit/secrets.toml (ver secrets.toml.example). En Streamlit "
            f"Cloud: agrégalo en Settings -> Secrets de la app."
        )
        st.stop()
    return st.secrets[nombre]


SUPABASE_URL = obtener_credencial("SUPABASE_URL")
SUPABASE_ANON_KEY = obtener_credencial("SUPABASE_ANON_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# ----------------------------------------------------------------------------
# Autenticación (igual que antes, pero con respaldo en Streamlit Secrets)
# ----------------------------------------------------------------------------
if os.path.exists(config.AUTH_CONFIG_PATH):
    with open(config.AUTH_CONFIG_PATH, encoding="utf-8") as f:
        auth_cfg = yaml.load(f, Loader=SafeLoader)
elif "auth_config" in st.secrets:
    auth_cfg = yaml.safe_load(st.secrets["auth_config"])
else:
    st.error(
        "No se encontró la configuración de usuarios. Localmente, corre "
        "`python generate_password.py`. En Streamlit Cloud, agrega el "
        "contenido de auth_config.yaml como el secret 'auth_config'."
    )
    st.stop()

authenticator = stauth.Authenticate(
    auth_cfg["credentials"],
    auth_cfg["cookie"]["name"],
    auth_cfg["cookie"]["key"],
    auth_cfg["cookie"]["expiry_days"],
)

authenticator.login()
auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("Usuario o contraseña incorrectos.")
    st.stop()
elif auth_status is None:
    st.info("Ingresa tu usuario y contraseña para continuar.")
    st.stop()

name = st.session_state.get("name")
username = st.session_state.get("username")



def main():
    # ----------------------------------------------------------------------------
    # Datos: catálogo desde Supabase
    # ----------------------------------------------------------------------------
    def registrar_descarga(path: str, usuario: str):
        try:
            supabase.table("downloads_log").insert({
                "path": path,
                "usuario": usuario,
                "fecha_hora": datetime.now().isoformat(),
            }).execute()
        except Exception:
            pass  # el log es informativo, no debe tronar la descarga


    def construir_ruta_visible(raiz: str, carpeta: str, multi_raiz: bool) -> str:
        """Combina 'raiz' (nombre de la carpeta raíz, ej. '2026') y 'carpeta'
        (subcarpeta relativa dentro de esa raíz) en una sola ruta de
        navegación. Si la colección solo tiene una raíz, el nombre de la raíz
        no se muestra como nivel aparte — se navega directo a sus subcarpetas,
        igual que el comportamiento original."""
        if not multi_raiz:
            return carpeta or ""
        return f"{raiz}/{carpeta}" if carpeta else raiz

    def descomponer_ruta(ruta_actual: list, multi_raiz: bool, nombres_raiz: list):
        """Inverso de construir_ruta_visible: a partir de los segmentos de
        ruta_actual, regresa (raiz, carpeta) para filtrar en Supabase.
        Si multi_raiz es True y ruta_actual está vacía, regresa (None, None)
        porque todavía no se eligió ninguna raíz (se están mostrando como
        carpetas de primer nivel)."""
        if multi_raiz:
            if not ruta_actual:
                return None, None
            return ruta_actual[0], "/".join(ruta_actual[1:])
        return (nombres_raiz[0] if nombres_raiz else None), "/".join(ruta_actual)

    @st.cache_data(ttl=60)
    def obtener_carpetas_distintas(coleccion: str, multi_raiz: bool):
        """Todas las rutas de carpeta que existen en el catálogo para esta
        colección (ej. 'DISCO LOVE', 'DISCO LOVE/Remixes', o si hay varias
        raíces, '2026/DISCO LOVE'). '' representa la raíz sin subcarpetas."""
        resp = supabase.table("recordings").select("carpeta,raiz").eq("coleccion", coleccion).execute()
        return sorted({
            construir_ruta_visible(r.get("raiz") or "", r.get("carpeta") or "", multi_raiz)
            for r in resp.data
        })


    def subcarpetas_de(carpetas: list, ruta_actual: list) -> list:
        """Dada la lista completa de rutas de carpeta y la ruta donde estamos
        parados (lista de segmentos), regresa los nombres de las subcarpetas
        inmediatas disponibles ahí."""
        prefijo = "/".join(ruta_actual)
        hijos = set()
        for c in carpetas:
            if prefijo == "":
                resto = c
            elif c == prefijo:
                continue
            elif c.startswith(prefijo + "/"):
                resto = c[len(prefijo) + 1:]
            else:
                continue
            if resto:
                hijos.add(resto.split("/")[0])
        return sorted(hijos, key=str.casefold)


    # ----------------------------------------------------------------------------
    # Barra lateral: usuario + filtros
    # ----------------------------------------------------------------------------
    with st.sidebar:
        st.markdown(f"**👤 {name}**")
        authenticator.logout("Cerrar sesión", "sidebar")


    # ----------------------------------------------------------------------------
    # Selector de colección: "Históricos" / "Actuales" (definidas en config.py)
    # ----------------------------------------------------------------------------
    st.title("Testigos 90.9 FM")

    nombres_coleccion = list(config.RECORDINGS_ROOTS.keys())

    if "coleccion" not in st.session_state:
        st.session_state.coleccion = None  # nada preseleccionado: el usuario debe elegir

    with st.container(key="fila_colecciones"):
        cols_coleccion = st.columns(len(nombres_coleccion))
        for i, nombre_col in enumerate(nombres_coleccion):
            es_activa = st.session_state.coleccion == nombre_col
            etiqueta = f"●  {nombre_col}" if es_activa else nombre_col
            if cols_coleccion[i].button(etiqueta, key=f"coleccion_{nombre_col}", use_container_width=True):
                if st.session_state.coleccion != nombre_col:
                    st.session_state.coleccion = nombre_col
                    st.session_state.ruta_actual = []
                    st.session_state.pop("archivo_sel", None)
                    st.rerun()

    if st.session_state.coleccion is None:
        st.markdown(
            '<p style="font-size:0.85rem; color:rgba(255,255,255,0.5); '
            'margin:0.4rem 0 0 0.1rem;">Selecciona tu gestor.</p>',
            unsafe_allow_html=True,
        )
        st.stop()

    coleccion_actual = st.session_state.coleccion
    raices_de_coleccion = config.RECORDINGS_ROOTS[coleccion_actual]
    nombres_raiz = [r["nombre"] for r in raices_de_coleccion]
    multi_raiz = len(nombres_raiz) > 1

    carpetas_todas = obtener_carpetas_distintas(coleccion_actual, multi_raiz)


    # ----------------------------------------------------------------------------
    # Navegador tipo explorador de archivos — una sola área: carpetas + audios
    # ----------------------------------------------------------------------------
    if "ruta_actual" not in st.session_state:
        st.session_state.ruta_actual = []
    ruta_actual = st.session_state.ruta_actual


    def construir_query_base():
        """Crea una consulta NUEVA cada vez (no reutiliza el objeto), porque los
        métodos .eq()/.ilike() de supabase-py mutan y regresan el mismo objeto —
        reutilizarlo entre dos búsquedas distintas apilaba los filtros en vez de
        mantenerlos independientes, y por eso antes "perdía" resultados."""
        return supabase.table("recordings").select("*")


    prefijo_carpeta = "/".join(ruta_actual)

    # --- ¿Esta ubicación tiene subcarpetas? Estilo Dropbox: si las hay, SOLO se
    # muestran las carpetas (acción 1); si no las hay (estamos en una carpeta
    # "hoja"), SOLO se muestra su contenido de archivos (acción 2). Nunca las dos
    # cosas juntas en la misma pantalla.
    hijos = subcarpetas_de(carpetas_todas, ruta_actual)

    df = pd.DataFrame()
    if not hijos:
        # carpeta hoja: solo archivos que viven exactamente aquí, dentro de
        # la colección y raíz actuales (raiz_sel es None solo si multi_raiz
        # es True y todavía no se eligió ninguna raíz — pero en ese caso
        # 'hijos' no estaría vacío, así que aquí siempre hay una raíz definida)
        raiz_sel, carpeta_sel = descomponer_ruta(ruta_actual, multi_raiz, nombres_raiz)
        query = construir_query_base().eq("coleccion", coleccion_actual)
        if raiz_sel is not None:
            query = query.eq("raiz", raiz_sel)
        query = query.eq("carpeta", carpeta_sel or "")
        datos = query.execute().data
        df = pd.DataFrame(datos)
        if not df.empty:
            df = (
                df.sort_values(["fecha", "hora"], ascending=False)
                .head(config.DEFAULT_RESULT_LIMIT)
                .reset_index(drop=True)
            )

    with st.container(border=True):

        # El botón "volver al inicio" debe verse en CUALQUIER nivel al que ya
        # navegamos (tenga o no subcarpetas esta ubicación) — antes solo
        # aparecía en carpetas "hoja" (sin subcarpetas), y se perdía al
        # entrar a una carpeta intermedia como "2025".
        mostrar_volver = bool(ruta_actual)
        n_migas = len(ruta_actual) + (1 if mostrar_volver else 0)

        if n_migas > 0:
            with st.container(key="fila_migas"):
                anchos = [0.09] * n_migas + [1]  # la última columna es relleno: empuja todo a la izquierda
                migas = st.columns(anchos)
                idx = 0
                if mostrar_volver:
                    if migas[idx].button("↩️", key="miga_inicio", disabled=not ruta_actual, help="Volver al inicio"):
                        st.session_state.ruta_actual = []
                        st.session_state.pop("archivo_sel", None)
                        st.rerun()
                    idx += 1
                for i, segmento in enumerate(ruta_actual):
                    es_actual = i == len(ruta_actual) - 1
                    if migas[idx].button(segmento, key=f"miga_{i}", disabled=es_actual):
                        st.session_state.ruta_actual = ruta_actual[: i + 1]
                        st.session_state.pop("archivo_sel", None)
                        st.rerun()
                    idx += 1

        if hijos:
            # --- Acción 1: solo carpetas, en lista vertical A-Z ---
            with st.container(key="carpeta_lista"):
                for nombre_hijo in hijos:  # ya vienen ordenados A-Z (subcarpetas_de)
                    if st.button(
                        f"📁  {nombre_hijo}",
                        key=f"abrir_{'/'.join(ruta_actual)}/{nombre_hijo}",
                        use_container_width=True,
                    ):
                        st.session_state.ruta_actual = ruta_actual + [nombre_hijo]
                        st.session_state.pop("archivo_sel", None)
                        st.rerun()
        else:
            # --- Acción 2: solo el contenido (archivos) de esta carpeta ---
            if df.empty:
                st.caption("Esta carpeta está vacía.")
            else:
                df_display = df.copy()
                df_display["duracion"] = df_display["duracion_seg"].apply(
                    lambda s: f"{int(s // 60)}:{int(s % 60):02d}" if pd.notnull(s) else "—"
                )
                df_display["tamaño"] = df_display["tamano_bytes"].apply(
                    lambda b: f"{b / 1024 / 1024:.1f} MB" if pd.notnull(b) else "—"
                )

                # Mismas proporciones de columna para encabezado Y cada fila —
                # así quedan perfectamente alineadas entre sí (igual que el
                # breadcrumb, que ya usa st.columns real).
                RATIOS_COLUMNAS = [4.2, 1, 0.8, 0.9]

                # Encabezado (solo texto, no clicleable)
                with st.container(key="encabezado_archivos"):
                    ec1, ec2, ec3, ec4 = st.columns(RATIOS_COLUMNAS, vertical_alignment="center")
                    ec1.write("Nombre")
                    ec2.write("Fecha")
                    ec3.write("Duración")
                    ec4.write("Tamaño")

                # Filas: el nombre del archivo es el botón clickeable (es el
                # área más grande y obvia de la fila); fecha/duración/tamaño
                # son texto plano en su propia columna real.
                seleccionado_actual = st.session_state.get("archivo_sel")
                with st.container(key="archivo_lista"):
                    for _, fila_df in df_display.iterrows():
                        es_sel = fila_df["path"] == seleccionado_actual
                        etiqueta = fila_df["filename"]
                        # Cuando el archivo está seleccionado, usamos un key con
                        # el prefijo "filasel_" en vez de "fila_" — así el CSS de
                        # abajo (selector por *= sobre esa key) le agrega el
                        # ícono de check.svg sin tocar el texto del botón.
                        clave_boton = f"filasel_{fila_df['path']}" if es_sel else f"fila_{fila_df['path']}"
                        fc1, fc2, fc3, fc4 = st.columns(RATIOS_COLUMNAS, vertical_alignment="center")
                        if fc1.button(
                            etiqueta,
                            key=clave_boton,
                            use_container_width=True,
                        ):
                            st.session_state.archivo_sel = fila_df["path"]
                            st.rerun()
                        fc2.write(fila_df["fecha"])
                        fc3.write(fila_df["duracion"])
                        fc4.write(fila_df["tamaño"])

    if hijos or df.empty:
        st.stop()

    archivo_sel_path = st.session_state.get("archivo_sel")
    filas_sel = df.index[df["path"] == archivo_sel_path].tolist() if archivo_sel_path else []

    st.divider()

    if not filas_sel:
        st.caption("Selecciona el archivo que quieres descargar de la lista de arriba.")
    else:
        fila = df.loc[filas_sel[0]]
        if fila["path"] != archivo_sel_path:
            # Salvaguarda: si por cualquier motivo la fila encontrada no es
            # la que el usuario seleccionó, no permitimos continuar con una
            # descarga que podría ser la de otro archivo.
            st.error("No se pudo confirmar la selección. Vuelve a elegir el archivo de la lista.")
            st.session_state.pop("archivo_sel", None)
            st.stop()
        st.subheader(fila["filename"])

        # Ancla + auto-scroll: cada vez que hay un archivo seleccionado, la
        # página baja sola hasta aquí (donde vive el botón de descarga), para
        # que el usuario no tenga que buscarlo manualmente. st.markdown no
        # ejecuta <script>, así que el scroll se hace con components.html
        # (corre en un iframe que sí puede ejecutar JS y alcanzar la página
        # principal vía window.parent, porque es del mismo origen).
        st.markdown('<div id="zona-descarga"></div>', unsafe_allow_html=True)
        components.html(
            """
            <script>
                var el = window.parent.document.getElementById('zona-descarga');
                if (el) { el.scrollIntoView({behavior: 'smooth', block: 'start'}); }
            </script>
            """,
            height=0,
        )

        # Estado por archivo: recuerda si ya se preparó la descarga, para que
        # el botón "Preparar descarga" se reemplace por "Descargar ahora" EN
        # EL MISMO LUGAR tras el rerun, en vez de desaparecer todo.
        clave_estado = f"descarga_{fila['path']}"
        estado = st.session_state.setdefault(clave_estado, {"listo": False, "url": None, "auto_disparado": False})

        if not estado["listo"]:
            if st.button("Descargar", key=f"pedir_{fila['path']}"):
                insercion = supabase.table("solicitudes_descarga").insert({
                    "path": fila["path"],
                    "filename": fila["filename"],
                    "usuario": username,
                }).execute()
                solicitud_id = insercion.data[0]["id"]

                url_lista = None
                error_msg = None
                agotado = False
                MAX_INTENTOS = 90  # 90 * 2 seg = 3 minutos máximo de espera

                with st.spinner("Preparando tu descarga... esto normalmente tarda unos segundos."):
                    for _ in range(MAX_INTENTOS):
                        check = supabase.table("solicitudes_descarga").select("*").eq("id", solicitud_id).execute()
                        estado_sol = check.data[0]

                        if estado_sol["estado"] == "listo":
                            url_lista = estado_sol["url_temporal"]
                            break
                        elif estado_sol["estado"] == "error":
                            error_msg = estado_sol.get("error_msg", "error desconocido")
                            break

                        time.sleep(2)
                    else:
                        agotado = True

                if error_msg:
                    st.error(f"No se pudo preparar el archivo: {error_msg}")
                elif agotado:
                    st.warning(
                        "Está tardando más de lo esperado. Verifica que app_local.py "
                        "siga corriendo en el servidor, o intenta de nuevo."
                    )
                elif url_lista:
                    registrar_descarga(fila["path"], username)
                    estado["listo"] = True
                    estado["url"] = url_lista
                    st.session_state[clave_estado] = estado
                    st.rerun()  # vuelve a correr el script; esta vez entra al bloque de abajo
        else:
            st.success("¡Listo! Tu descarga está lista (el enlace expira en unos minutos):")
            st.link_button("Descargar Nuevamente", estado["url"], key="btn_descargar")

            if not estado["auto_disparado"]:
                # Dispara la descarga automáticamente, una sola vez, sin que
                # el usuario tenga que apretar el botón de arriba. El botón
                # se deja de todas formas como respaldo (por si el navegador
                # bloquea la descarga automática).
                components.html(
                    f"""
                    <a id="auto_dl" href="{estado['url']}" download style="display:none"></a>
                    <script>document.getElementById('auto_dl').click();</script>
                    """,
                    height=0,
                )
                estado["auto_disparado"] = True
                st.session_state[clave_estado] = estado

try:
    main()
except Exception:
    # Cualquier falla inesperada (conexion, datos, etc.) se registra en la
    # consola del servidor para diagnostico, pero al usuario final se le
    # muestra un mensaje simple en vez del traceback tecnico de Streamlit.
    traceback.print_exc()
    st.error("\u26a0\ufe0f Hubo una falla de conexi\u00f3n con el servidor. Por favor, recarga la p\u00e1gina.")
    st.stop()
# Practica final SQLite

Pipeline en Python para alimentar una base de datos SQLite con videos de YouTube, sus transcripciones y resumenes generados con Gemini.

El proyecto esta pensado como parte previa al portal Django: descarga informacion de videos, guarda los registros en la tabla `VIDEOS` y genera resumenes en la tabla `RESUMEN` de la base de datos usada por la web.

## Que hace

1. Pide por consola el nombre de un canal de YouTube.
2. Pide un rango de fechas en formato `DD/MM/AAAA`.
3. Busca videos publicados en ese intervalo.
4. Detecta cuales no estan aun en la base de datos.
5. Obtiene la transcripcion de cada video.
6. Inserta los videos nuevos en SQLite.
7. Genera resumenes con Gemini para los videos pendientes.
8. Guarda los resumenes asociados a cada video.

## Archivos principales

```text
0_PRACTICA FINAL_SQLite/
├── script0_main.py                  # Ejecuta el flujo principal
├── script1_youtube_serpapi.py        # Busca videos y obtiene transcripciones con SerpAPI
├── script1_youtube.py                # Variante usando youtube-transcript-api
├── script2_resumen.py                # Genera resumenes con Gemini y los guarda en SQLite
├── utils.py                          # Funciones auxiliares para leer la BD
├── debug_youtube_transcript.py       # Script auxiliar de depuracion
├── config.example.py                 # Plantilla segura de configuracion
├── requirements.txt                  # Dependencias del proyecto
└── README.md
```

## Instalacion

1. Clona el repositorio y entra en la carpeta:

```bash
git clone <url-del-repositorio>
cd "DjangoProject_Backend"
```

2. Crea y activa un entorno virtual:

```bash
python -m venv venv
venv\Scripts\activate
```

3. Instala las dependencias:

```bash
pip install -r requirements.txt
```

## Configuracion

1. Copia la plantilla de configuracion:

```bash
copy config.example.py config.py
```

2. Edita `config.py` y rellena tus claves reales:

- `YOUTUBE_API_KEY`
- `SERPAPI_API_KEY`
- `GEMINI_API_KEY`
- `DB_PATH`

`DB_PATH` debe apuntar a la base SQLite que quieras alimentar. En este proyecto se usa normalmente la base del portal Django:

```python
DB_PATH = "C:\\Users\\tu_usuario\\Desktop\\djangoproject\\db.sqlite3"
```

## Tablas esperadas

El pipeline trabaja principalmente con estas tablas:

### VIDEOS

Campos usados por los scripts:

- `ID`
- `FECHA`
- `CANAL`
- `TITULO`
- `URL`
- `TRANSCRIPCION`

### RESUMEN

Campos usados por los scripts:

- `ID_RESUMEN`
- `VIDEO_ID`
- `RESUMEN_TEXTO`

## Uso

Ejecuta el flujo completo con:

```bash
python script0_main.py
```

Durante la ejecucion se pediran estos datos:

```text
Introduce el nombre del canal:
Desde (DD/MM/AAAA):
Hasta (DD/MM/AAAA):
```

Ejemplo:

```text
Introduce el nombre del canal: Nombre del canal
Desde (DD/MM/AAAA): 01/05/2026
Hasta (DD/MM/AAAA): 15/05/2026
```

## Flujo de scripts

`script0_main.py` ejecuta:

```python
script1_youtube_serpapi.script_1()
script2_resumen.script_2()
```

La variante `script1_youtube.py` queda disponible si se prefiere obtener transcripciones con `youtube-transcript-api` en lugar de SerpAPI.

## Archivos que no se suben a GitHub

El `.gitignore` evita subir archivos locales, generados o sensibles:

- `config.py`
- `database.db`
- `*.db`
- `*.sqlite3`
- `__pycache__/`
- `*.pyc`
- `venv/`

## Nota de seguridad

`config.py` contiene claves API y credenciales, por eso no debe subirse a GitHub. Si alguna clave ha estado en un repositorio publico, conviene revocarla y generar una nueva desde el proveedor correspondiente.

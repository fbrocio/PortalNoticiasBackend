import requests
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta
import config
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

def script_1():
    # =========================================================
    # CONFIG SQLITE
    # =========================================================
    DB_PATH = config.DB_PATH

    # =========================================================
    # PROCESO 1 - Busca vídeos en un canal de YT en un rango
    # =========================================================

    def get_channel_id_by_name(channel_name, api_key):
        url = 'https://www.googleapis.com/youtube/v3/search'
        params = {
            "part": "id",
            "q": channel_name,
            "type": "channel",
            "maxResults": 1,
            "key": api_key
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data["items"][0]["id"]["channelId"]

    def get_list_of_videos(channel_id, api_key, fecha_inicio, fecha_fin):
        url = 'https://www.googleapis.com/youtube/v3/search'
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "publishedAfter": fecha_inicio,
            "publishedBefore": fecha_fin,
            "type": "video",
            "maxResults": 50,
            "order": "date",
            "key": api_key
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        all_videos = []
        for item in data.get("items", []):
            fecha_str = item["snippet"]["publishedAt"]
            fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%dT%H:%M:%SZ")
            video_info = {
                "video_id": item["id"]["videoId"],
                "video_url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "titulo": item["snippet"]["title"],
                "fecha": fecha_dt,
                "canal": item["snippet"]["channelTitle"],
                "descripcion": item["snippet"]["description"]
            }
            all_videos.append(video_info)

        return all_videos

    mi_api_key = config.YOUTUBE_API_KEY

    nombre_canal = input('Introduce el nombre del canal: ')
    id_canal = get_channel_id_by_name(nombre_canal, mi_api_key)

    fecha_inicio_str = input("Desde (DD/MM/AAAA): ")
    fecha_inicio_dt = datetime.strptime(fecha_inicio_str, "%d/%m/%Y")
    fecha_inicio_api = fecha_inicio_dt.isoformat() + "Z"

    fecha_fin_str = input("Hasta (DD/MM/AAAA): ")
    fecha_fin_dt = datetime.strptime(fecha_fin_str, "%d/%m/%Y")
    fecha_fin_api = (fecha_fin_dt + timedelta(days=1)).isoformat() + "Z"

    videos_busqueda = get_list_of_videos(id_canal, mi_api_key, fecha_inicio_api, fecha_fin_api)

    print("\n" + "!" * 20, flush=True)
    print(f"VÍDEOS ENCONTRADOS EN YT: {len(videos_busqueda)}", flush=True)
    for v in videos_busqueda:
        print(f"  - {v['titulo']}", flush=True)
    print("!" * 20 + "\n", flush=True)

    # =========================================================
    # PROCESO 2 - LECTURA SQLITE
    # =========================================================

    dfs = {}
    tablas = ['VIDEOS', 'RESUMEN']

    with sqlite3.connect(DB_PATH) as conn:
        for tabla in tablas:
            query = f'SELECT * FROM {tabla}'
            try:
                df_db = pd.read_sql(query, conn)
                df_db.columns = df_db.columns.str.lower()
                dfs[tabla.lower()] = df_db
                print(f'Tabla {tabla} leída correctamente. Filas: {len(df_db)}', flush=True)
            except Exception as e:
                print(f'Error leyendo la tabla {tabla}: {e}', flush=True)

    print("Conexión cerrada.\n", flush=True)

    titulos_db = set(dfs['videos']['titulo'])
    videos_nuevos = [v for v in videos_busqueda if v['titulo'] not in titulos_db]

    if not videos_nuevos:
        print("\n" + "!" * 30, flush=True)
        print("NO SE ENCONTRARON VÍDEOS NUEVOS.", flush=True)
        print("!" * 30, flush=True)
        return

    df_visualizacion = pd.DataFrame(videos_nuevos)
    print("\n" + "=" * 60, flush=True)
    print(f"SE HAN ENCONTRADO {len(videos_nuevos)} VÍDEOS NUEVOS:", flush=True)
    print("=" * 60, flush=True)
    with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 1000):
        print(df_visualizacion[['fecha', 'titulo', 'canal']].to_string(), flush=True)
    print("=" * 60 + "\n", flush=True)

    # =========================================================
    # PROCESOS 3 y 4 - TRANSCRIPCIONES
    # =========================================================

    def extract_video_id(video_url):
        return video_url.split("v=")[-1]

    MAX_REINTENTOS  = 3
    ESPERA_REINTENTO = 15

    def get_video_transcript(video_url):
        video_id = extract_video_id(video_url)
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=["es", "en"])
        return " ".join(item.text for item in transcript).strip()
    
    def get_all_video_transcript(list_of_videos):
        transcripciones_list = []
        total = len(list_of_videos)

        for i, v in enumerate(list_of_videos, start=1):
            titulo = v['titulo']
            url = v['video_url']
            transcripcion = ""

            print(f"\n[{i}/{total}] Transcribiendo: '{titulo}'", flush=True)
            print(f"       URL: {url}", flush=True)

            for intento in range(1, MAX_REINTENTOS + 1):
                try:
                    resultado = get_video_transcript(url)

                    if not resultado:
                        if intento < MAX_REINTENTOS:
                            print(f"Reintentando...", flush=True)
                            time.sleep(ESPERA_REINTENTO)
                    else:
                        transcripcion = resultado
                        break

                except TranscriptsDisabled:
                    time.sleep(ESPERA_REINTENTO)
                except NoTranscriptFound:
                    time.sleep(ESPERA_REINTENTO)
                except Exception as e:
                    print(f"ERROR: {e}", flush=True)
                    if intento < MAX_REINTENTOS:
                        time.sleep(ESPERA_REINTENTO)

            transcripciones_list.append(transcripcion)

        return transcripciones_list

    nuevas_transcripciones = get_all_video_transcript(videos_nuevos)

    # =========================================================
    # PROCESO 5 - INSERT SQLITE
    # =========================================================

    df_videos_nuevos = pd.DataFrame(videos_nuevos)
    df_videos_nuevos["fecha"] = pd.to_datetime(df_videos_nuevos["fecha"]).astype(str)
    df_videos_nuevos['transcripcion'] = nuevas_transcripciones

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        query = """INSERT INTO VIDEOS (FECHA, CANAL, TITULO, URL, TRANSCRIPCION)
                   VALUES (?, ?, ?, ?, ?)"""

        list_videos_nuevos = list(
            df_videos_nuevos[["fecha", "canal", "titulo", "video_url", "transcripcion"]]
            .itertuples(index=False, name=None)
        )

        cursor.executemany(query, list_videos_nuevos)
        conn.commit()

        print(f"{len(list_videos_nuevos)} vídeo(s) insertados en BD.", flush=True)
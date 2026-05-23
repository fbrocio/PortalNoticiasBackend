import requests
import pandas as pd
import sqlite3
import time
from datetime import datetime, timedelta
import config

def script_1():

    DB_PATH = config.DB_PATH
    YT_API_KEY = config.YOUTUBE_API_KEY
    SERPAPI_API_KEY = config.SERPAPI_API_KEY

    # =========================================================
    # PROCESO 1 - Obtener vídeos
    # =========================================================

    def get_channel_id_by_name(channel_name):
        url = 'https://www.googleapis.com/youtube/v3/search'
        params = {
            "part": "id",
            "q": channel_name,
            "type": "channel",
            "maxResults": 1,
            "key": YT_API_KEY
        }
        r = requests.get(url, params=params)
        r.raise_for_status()
        return r.json()["items"][0]["id"]["channelId"]

    def get_list_of_videos(channel_id, fecha_inicio, fecha_fin):
        url = 'https://www.googleapis.com/youtube/v3/search'
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "publishedAfter": fecha_inicio,
            "publishedBefore": fecha_fin,
            "type": "video",
            "maxResults": 50,
            "order": "date",
            "key": YT_API_KEY
        }
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json()

        videos = []
        for item in data.get("items", []):
            fecha = datetime.strptime(item["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            videos.append({
                "video_id": item["id"]["videoId"],
                "video_url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "titulo": item["snippet"]["title"],
                "fecha": fecha,
                "canal": item["snippet"]["channelTitle"],
                "descripcion": item["snippet"]["description"]
            })
        return videos

    nombre_canal = input('Introduce el nombre del canal: ')
    id_canal = get_channel_id_by_name(nombre_canal)

    f_ini = datetime.strptime(input("Desde (DD/MM/AAAA): "), "%d/%m/%Y")
    f_fin = datetime.strptime(input("Hasta (DD/MM/AAAA): "), "%d/%m/%Y") + timedelta(days=1)

    videos_busqueda = get_list_of_videos(id_canal, f_ini.isoformat()+"Z", f_fin.isoformat()+"Z")

    # =========================================================
    # PROCESO 2 - Leer BD
    # =========================================================

    with sqlite3.connect(DB_PATH) as conn:
        df_db = pd.read_sql("SELECT * FROM VIDEOS", conn)
        df_db.columns = df_db.columns.str.lower()

    titulos_db = set(df_db['titulo'])
    videos_nuevos = [v for v in videos_busqueda if v['titulo'] not in titulos_db]

    if not videos_nuevos:
        print("No hay vídeos nuevos")
        return

    print(f"{len(videos_nuevos)} vídeos nuevos detectados")

    # =========================================================
    # PROCESO 3 - TRANSCRIPCIONES (SERPAPI)
    # =========================================================

    def extract_video_id(url):
        return url.split("v=")[-1]

    def get_video_transcript(url):
        params = {
            "api_key": SERPAPI_API_KEY,
            "engine": "youtube_video_transcript",
            "v": extract_video_id(url),
            "type": "asr"
        }

        r = requests.get("https://serpapi.com/search", params=params)
        r.raise_for_status()
        data = r.json()

        if "error" in data:
            return ""

        return " ".join(
            item.get("snippet", "")
            for item in data.get("transcript", [])
        ).strip()

    def get_all_transcripts(videos):
        resultados = []

        for i, v in enumerate(videos, 1):
            print(f"[{i}/{len(videos)}] {v['titulo']}")

            texto = ""

            try:
                texto = get_video_transcript(v['video_url'])
                if not texto:
                    print("  ⚠️ Sin transcripción")
                else:
                    print(f"  ✅ {len(texto.split())} palabras")

            except Exception as e:
                print(f"  ❌ ERROR: {e}")

            # 🔒 GARANTÍA ABSOLUTA
            resultados.append(str(texto))

        return resultados

    nuevas_transcripciones = get_all_transcripts(videos_nuevos)

    # 🔴 VALIDACIÓN CRÍTICA
    if len(videos_nuevos) != len(nuevas_transcripciones):
        raise ValueError("Desalineación entre vídeos y transcripciones")

    # =========================================================
    # PROCESO 5 - INSERT SQLITE
    # =========================================================

    df = pd.DataFrame(videos_nuevos)
    df["fecha"] = pd.to_datetime(df["fecha"]).astype(str)
    df["transcripcion"] = nuevas_transcripciones

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.executemany("""
            INSERT INTO VIDEOS (FECHA, CANAL, TITULO, URL, TRANSCRIPCION)
            VALUES (?, ?, ?, ?, ?)
        """, list(df[["fecha","canal","titulo","video_url","transcripcion"]]
                  .itertuples(index=False, name=None)))

        conn.commit()

    print(f"{len(df)} vídeos insertados correctamente")
import pandas as pd
import sqlite3
import google.generativeai as genai
import google.api_core.exceptions
import utils
import time
import math
import config

def script_2():
    # =========================================================
    # CONFIG SQLITE
    # =========================================================
    DB_PATH = config.DB_PATH

    # =========================================================
    # PROCESO 6 - Leer tablas y detectar vídeos pendientes
    # =========================================================
    dfs = utils.extraer_info_bd()
    df_videos = dfs.get("videos", pd.DataFrame())
    df_resumen = dfs.get("resumen", pd.DataFrame())

    df_videos.columns = df_videos.columns.str.lower().str.strip()
    df_resumen.columns = df_resumen.columns.str.lower().str.strip()

    def detectar_columna_id(df, candidatos):
        columnas = set(df.columns)
        for nombre in candidatos:
            if nombre in columnas:
                return nombre
        return None

    id_col_videos = detectar_columna_id(df_videos, ["id"])
    id_col_resumen = detectar_columna_id(df_resumen, ["video_id"])

    if id_col_videos is None:
        raise KeyError(f"No se encontró columna ID en VIDEOS. Columnas disponibles: {list(df_videos.columns)}")

    def select_new_videos(df_videos_local, df_resumen_local, col_id_videos, col_id_resumen):
        df_con_transcripcion = df_videos_local[
            df_videos_local["transcripcion"].notna() &
            (df_videos_local["transcripcion"].str.strip() != "")
        ]

        ids_videos = list(df_con_transcripcion[col_id_videos])

        if col_id_resumen is None:
            return ids_videos

        ids_resumen = set(df_resumen_local[col_id_resumen])
        return [video_id for video_id in ids_videos if video_id not in ids_resumen]

    ids_pendientes = select_new_videos(df_videos, df_resumen, id_col_videos, id_col_resumen)

    total_sin_transcripcion = (
        df_videos["transcripcion"].isna() |
        (df_videos["transcripcion"].str.strip() == "")
    ).sum()

    if total_sin_transcripcion:
        print(f"⚠️  {total_sin_transcripcion} vídeo(s) omitidos por no tener transcripción.", flush=True)

    if not ids_pendientes:
        print("No hay vídeos pendientes de resumen.", flush=True)
        return

    def obtener_transcripciones_por_ids(df, ids, col_id):
        textos = df.loc[df[col_id].isin(ids), "transcripcion"].tolist()
        return [t.read() if hasattr(t, "read") else t for t in textos]

    nuevas_transcripciones = obtener_transcripciones_por_ids(df_videos, ids_pendientes, id_col_videos)

    # =========================================================
    # PROCESOS 7 y 8 - Gemini
    # =========================================================

    def clasificar_error_gemini(e):
        mensaje = str(e).lower()

        if isinstance(e, google.api_core.exceptions.ResourceExhausted):
            if "perday" in mensaje or "per_day" in mensaje or "daily" in mensaje:
                return "token_limit", 0

            if "rate" in mensaje or "requests per minute" in mensaje or "rpm" in mensaje or "retry" in mensaje:
                retry_seconds = getattr(e, "retry_delay", None)
                if retry_seconds is None:
                    try:
                        for detail in e.details():
                            if hasattr(detail, "retry_delay"):
                                retry_seconds = detail.retry_delay.seconds
                                break
                    except Exception:
                        pass
                return "rate_limit", math.ceil(retry_seconds) if retry_seconds else 60

            return "token_limit", 0

        return "otro", 60

    def summarize_text_with_gemini(text, api_key):
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("models/gemini-2.5-flash-lite")
        prompt = (
            "Voy a pasar una transcripción de un vídeo."
            "Resume únicamente el contenido de valor de forma clara, concisa y estructurada, obviando todo lo 'contextual'."
            "No empiece con frases de relleno como 'Aquí tienes un resumen..."
            "Responde unicamente el resumen, de manera que pueda copiarse y pegarse directamente a un noticiero sin necesidad de editarlo."
            "Ajústate a 200-250 palabras y utiliza formato de boletín de noticias."
            "Utiliza un tono divulgativo y cercano, pero más formal que el orador original.\n\n"
            f"{text}"
        )
        response = model.generate_content(prompt)
        return response.text

    BATCH_SIZE = 5
    total_videos = len(nuevas_transcripciones)
    num_batches = math.ceil(total_videos / BATCH_SIZE)

    print(f"\nVídeos pendientes de resumen: {total_videos} | Lotes: {num_batches}", flush=True)

    for i in range(num_batches):
        batch_transcripciones = nuevas_transcripciones[i * BATCH_SIZE:(i + 1) * BATCH_SIZE]
        batch_ids = ids_pendientes[i * BATCH_SIZE:(i + 1) * BATCH_SIZE]
        batch_resumenes = []

        print(f"\n{'=' * 60}", flush=True)
        print(f"LOTE {i + 1}/{num_batches} — {len(batch_transcripciones)} vídeo(s)", flush=True)
        print(f"{'=' * 60}", flush=True)

        for idx, transcripcion in enumerate(batch_transcripciones, start=1):
            video_id = batch_ids[idx - 1]
            fila = df_videos.loc[df_videos[id_col_videos] == video_id]
            titulo = fila["titulo"].values[0] if not fila.empty and "titulo" in fila.columns else f"ID {video_id}"

            print(f"\n  [{idx}/{len(batch_transcripciones)}] Resumiendo: '{titulo}'", flush=True)

            while True:
                try:
                    resumen = summarize_text_with_gemini(transcripcion, config.GEMINI_API_KEY)

                    if not resumen or not resumen.strip():
                        print(f"  ⚠️  Gemini devolvió un resumen vacío para '{titulo}'.", flush=True)
                        resumen = ""
                    else:
                        palabras = resumen.split()
                        preview = " ".join(palabras[:20])
                        puntos = "..." if len(palabras) > 20 else ""
                        print(f"  ✅ Resumen obtenido ({len(palabras)} palabras).", flush=True)
                        print(f"     Vista previa: {preview}{puntos}", flush=True)

                    batch_resumenes.append(resumen)
                    break

                except Exception as e:
                    print(f"  🔍 DEBUG — Tipo de excepción: {type(e).__name__}", flush=True)
                    print(f"  🔍 DEBUG — Mensaje completo: {str(e)}", flush=True)

                    tipo, segundos = clasificar_error_gemini(e)

                    if tipo == "rate_limit":
                        time.sleep(segundos)
                    elif tipo == "token_limit":
                        raise SystemExit(1)
                    else:
                        time.sleep(segundos)

        vacios = sum(1 for r in batch_resumenes if not r)

        print(f"\n  Lote {i + 1} completado: {len(batch_resumenes) - vacios}/{len(batch_resumenes)}", flush=True)

        df_videos_resumidos = pd.DataFrame({
            "id": batch_ids,
            "resumen": batch_resumenes
        })

        query = "INSERT INTO RESUMEN (VIDEO_ID, RESUMEN_TEXTO) VALUES (?, ?)"
        list_resumenes_nuevos = list(
            df_videos_resumidos[["id", "resumen"]].itertuples(index=False, name=None)
        )

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.executemany(query, list_resumenes_nuevos)
            conn.commit()

        print(f"  💾 Lote {i + 1} guardado en Base de Datos.", flush=True)

    print(f"\n{'=' * 60}", flush=True)
    print(f"PROCESO COMPLETADO: {total_videos} vídeo(s) procesados en {num_batches} lote(s).", flush=True)
    print(f"{'=' * 60}\n", flush=True)
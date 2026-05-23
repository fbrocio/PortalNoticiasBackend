from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# ============================================================
# Archivo de diagnóstico - youtube-transcript-api
# ============================================================

VIDEOS_TEST = {
    "falla":    "https://www.youtube.com/watch?v=9MB2pSIusoE",  # <- URL que fallaba con SerpAPI
    "funciona": "https://www.youtube.com/watch?v=IYNZ6VIIiHs",  # <- URL que funcionaba con SerpAPI
}


def extract_video_id(video_url):
    return video_url.split("v=")[-1]


def debug_transcript(label, video_url):
    video_id = extract_video_id(video_url)

    print("\n" + "=" * 60)
    print(f"VÍDEO: {label}")
    print(f"URL:   {video_url}")
    print(f"ID:    {video_id}")
    print("=" * 60)

    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=["es", "en"])
        texto = " ".join(item.text for item in transcript).strip()

        if texto:
            palabras = texto.split()
            preview = " ".join(palabras[:30])
            puntos = "..." if len(palabras) > 30 else ""
            print(f"✅ Transcripción obtenida ({len(palabras)} palabras).")
            print(f"   Vista previa: {preview}{puntos}")
        else:
            print("⚠️  La API respondió pero devolvió texto vacío.")

    except TranscriptsDisabled:
        print("❌ ERROR: Las transcripciones están desactivadas para este vídeo.")

    except NoTranscriptFound:
        print("❌ ERROR: No se encontró transcripción en español ni inglés.")

    except Exception as e:
        print(f"❌ ERROR INESPERADO: {e}")


if __name__ == "__main__":
    for label, url in VIDEOS_TEST.items():
        debug_transcript(label, url)

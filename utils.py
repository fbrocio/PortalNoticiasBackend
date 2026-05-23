# Script con funciones auxiliares

import sqlite3
import pandas as pd
import config


# La función extraer_info_bd consulta la BD y devuelve dos dataframes con la información

def extraer_info_bd():

    DB_PATH = config.DB_PATH

    # Instanciamos un diccionario vacío donde se almacenarán los dataframes
    dfs = {}

    # Query SQL - bucle que recorra la lista con el nombre de las tablas
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

    return dfs
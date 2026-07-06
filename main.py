import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
from google.cloud import bigquery
import os
from datetime import datetime, timezone

# Konfiguracja środowiska
CREDENTIALS_FILE = 'gcp-credentials.json'
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE

bq_client = bigquery.Client()

TABELA_DZIENNA_ID = "weather-pipeline-497920.weather_data.dzienna"
TABELA_GODZINOWA_ID = "weather-pipeline-497920.weather_data.godzinowa"
TABELA_LOGI_ID = "weather-pipeline-497920.weather_data.logi"

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1XRKxPVophXOG6CTwXXG2s_JnqZdUuWaDuXnPerTW3Cg/edit?usp=sharing'

def get_sheet_data(credentials_file, sheet_url):
    print("Autoryzacja w Google Cloud...")
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/bigquery'
    ]
    creds = Credentials.from_service_account_file(credentials_file, scopes=scopes)
    client = gspread.authorize(creds)
    
    print("Pobieranie danych z arkusza...")
    sheet = client.open_by_url(sheet_url).sheet1
    records = sheet.get_all_records()
    return pd.DataFrame(records)

def get_coordinates(city_name):
    """Pobiera współrzędne geograficzne lub zwraca komunikat o błędzie."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "en", "format": "json"}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "results" in data and len(data["results"]) > 0:
            lat = data["results"][0]["latitude"]
            lon = data["results"][0]["longitude"]
            return lat, lon, None
        else:
            return None, None, "Błędne miasto (brak w API)"
            
    except requests.exceptions.RequestException as e:
        return None, None, f"Błędna odpowiedź API (Geocoding): {e}"
    
def get_weather_data(lat, lon, date):
    """Pobiera dane pogodowe lub zwraca komunikat o błędzie."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date,
        "end_date": date,
        "hourly": "temperature_2m",
        "daily": [
            "temperature_2m_max", 
            "temperature_2m_min", 
            "temperature_2m_mean", 
            "precipitation_sum", 
            "sunrise", 
            "sunset"
        ],
        "timezone": "auto" 
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.RequestException as e:
        return None, f"Błędna odpowiedź API (Pogoda): {e}"

def check_if_exists_daily(client, table_id, miasto, data):
    """Sprawdza duplikaty w tabeli dziennej."""
    query = f"""
        SELECT 1
        FROM `{table_id}`
        WHERE miasto = '{miasto}' AND data = '{data}'
        LIMIT 1
    """
    try:
        query_job = client.query(query)
        results = list(query_job.result())
        return len(results) > 0
    except Exception as e:
        print(f"⚠️ Błąd podczas sprawdzania duplikatów dziennych: {e}")
        return False

def check_if_exists_hourly(client, table_id, miasto, data):
    """Sprawdza duplikaty w tabeli godzinowej za pomocą filtra na kolumnę 'czas'."""
    query = f"""
        SELECT 1
        FROM `{table_id}`
        WHERE miasto = '{miasto}' AND CAST(czas AS STRING) LIKE '{data}%'
        LIMIT 1
    """
    try:
        query_job = client.query(query)
        results = list(query_job.result())
        return len(results) > 0
    except Exception as e:
        print(f"⚠️ Błąd podczas sprawdzania duplikatów godzinowych: {e}")
        return False

def insert_to_bq(client, table_id, rows):
    """Uniwersalna funkcja do zapisu wsadowego (wspierana przez Free Tier)."""
    if not rows: return
    job_config = bigquery.LoadJobConfig(write_disposition=bigquery.WriteDisposition.WRITE_APPEND)
    try:
        job = client.load_table_from_json(rows, table_id, job_config=job_config)
        job.result()
    except Exception as e:
        print(f"❌ Błąd zapisu do BigQuery ({table_id}): {e}")


if __name__ == "__main__":
    df_input = get_sheet_data(CREDENTIALS_FILE, SHEET_URL)
    print("\nRozpoczynam proces ETL...")

    for index, row in df_input.iterrows():
        miasto = row['miasto']
        data_pogody = str(row['data'])

        print(f"\n--- Przetwarzanie: {miasto} ({data_pogody}) ---")

        # Krok A: Geocoding (Pobieranie współrzędnych)
        lat, lon, geo_error = get_coordinates(miasto)

        if geo_error:
            print(f"⚠️ {geo_error}")
            # ZAPIS DO LOGÓW
            log_row = [{
                "czas_zdarzenia": datetime.now(timezone.utc).isoformat(),
                "typ_bledu": "GEOCODING_ERROR",
                "miasto": miasto,
                "szczegoly": geo_error
            }]
            insert_to_bq(bq_client, TABELA_LOGI_ID, log_row)
            continue

        print(f"✅ Znaleziono współrzędne: {lat}, {lon}")

        # Krok B: Pobieranie pogody
        weather_data, weather_error = get_weather_data(lat, lon, data_pogody)

        if weather_error:
            print(f"⚠️ {weather_error}")
            # ZAPIS DO LOGÓW
            log_row = [{
                "czas_zdarzenia": datetime.now(timezone.utc).isoformat(),
                "typ_bledu": "WEATHER_API_ERROR",
                "miasto": miasto,
                "szczegoly": weather_error
            }]
            insert_to_bq(bq_client, TABELA_LOGI_ID, log_row)
            continue

        # Sprawdzenie czy dane istnieją w odpowiedzi
        if 'daily' not in weather_data or not weather_data['daily'].get('time'):
            error_msg = "Brak danych dla danego dnia/miasta"
            print(f"⚠️ {error_msg}")
            # ZAPIS DO LOGÓW
            log_row = [{
                "czas_zdarzenia": datetime.now(timezone.utc).isoformat(),
                "typ_bledu": "NO_DATA",
                "miasto": miasto,
                "szczegoly": error_msg
            }]
            insert_to_bq(bq_client, TABELA_LOGI_ID, log_row)
            continue

        # Wypakowywanie danych dziennych
        srednia_temp = weather_data['daily']['temperature_2m_mean'][0]
        max_temp = weather_data['daily']['temperature_2m_max'][0]
        min_temp = weather_data['daily']['temperature_2m_min'][0]
        opady = weather_data['daily']['precipitation_sum'][0]
        wschod = weather_data['daily']['sunrise'][0]
        zachod = weather_data['daily']['sunset'][0]

        print(f"🌦️ Pogoda pobrana! Max temp: {max_temp}°C, Opady: {opady} mm")

        # ZAPIS DANYCH DZIENNYCH
        if check_if_exists_daily(bq_client, TABELA_DZIENNA_ID, miasto, data_pogody):
            print(f"⏭️ Dane dzienne dla {miasto} ({data_pogody}) już istnieją. Pomijam.")
        else:
            wiersz_dzienna = [{
                "miasto": miasto,
                "data": data_pogody,
                "srednia_temp": srednia_temp,
                "max_temp": max_temp,
                "min_temp": min_temp,
                "opady": opady,
                "wschod_slonca": wschod,
                "zachod_slonca": zachod
            }]
            insert_to_bq(bq_client, TABELA_DZIENNA_ID, wiersz_dzienna)
            print(f"💾 Zapisano dane DZIENNE dla: {miasto}")

        # ZAPIS DANYCH GODZINOWYCH
        if check_if_exists_hourly(bq_client, TABELA_GODZINOWA_ID, miasto, data_pogody):
            print(f"⏭️ Dane godzinowe dla {miasto} ({data_pogody}) już istnieją. Pomijam.")
        else:
            czasy_godzinowe = weather_data['hourly']['time']
            tempy_godzinowe = weather_data['hourly']['temperature_2m']
            
            wiersze_godzinowe = []
            for t, temp in zip(czasy_godzinowe, tempy_godzinowe):
                wiersze_godzinowe.append({
                    "miasto": miasto,
                    "czas": t,  
                    "temperatura": temp
                })
            
            insert_to_bq(bq_client, TABELA_GODZINOWA_ID, wiersze_godzinowe)
            print(f"💾 Zapisano dane GODZINOWE dla: {miasto} (liczba rekordów: {len(wiersze_godzinowe)})")
# 🌤️ Weather Data ETL Pipeline

Automatyczny proces ETL (Extract, Transform, Load) pobierający dane pogodowe z Open-Meteo API dla miast zdefiniowanych w Google Sheets i ładujący je do hurtowni danych Google BigQuery.

## 🚀 Architektura i Stack Technologiczny
* **Język:** Python (Pandas)
* **Źródła danych:** Google Sheets API, Open-Meteo API (Geocoding & Weather Forecast)
* **Cel (Data Warehouse):** Google BigQuery
* **Autoryzacja:** Google Cloud Service Account

## 🧠 Główne funkcjonalności (Features)
* **Idempotentność:** Skrypt sprawdza istnienie rekordów w tabelach (dziennych i godzinowych) przed wstawieniem, co zapobiega powstawaniu duplikatów w BigQuery podczas ponownego uruchomienia pipeline'u.
* **Geocoding:** Automatyczna transformacja nazw miast z arkusza kalkulacyjnego na precyzyjne współrzędne geograficzne.
* **Error Handling & Logging:** Wszelkie błędy API lub braki danych są przechwytywane i logowane do dedykowanej tabeli audytowej (`weather_data.logi`) w hurtowni danych.
* **Batch Processing:** Zapis do BigQuery realizowany jest wsadowo (batch insert) w formacie JSON, co jest zoptymalizowane pod kątem wydajności.

## ⚙️ Uruchomienie lokalne (How to run)

1. **Sklonuj repozytorium:**
   ```bash
   git clone https://github.com/TwojNick/weather-etl-pipeline.git
   cd weather-etl-pipeline
   ```

2. **Zainstaluj wymagane zależności:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Skonfiguruj autoryzację GCP:**
   * Pobierz swój plik z kluczami Service Account z Google Cloud Console.
   * Umieść go w głównym folderze projektu i zmień jego nazwę na `gcp-credentials.json`. *(Uwaga: Plik ten jest zdefiniowany w `.gitignore` i chroniony przed przypadkowym udostępnieniem).*

4. **Uruchom pipeline:**
   ```bash
   python main.py
   ```

---

## 👨‍💻 O autorze
**Tobiasz Mędrek** Student Ekonomii na Uniwersytecie Warszawskim oraz aktywny członek Koła Naukowego Finansów Obliczeniowych (MIMUW). Projekt zrealizowany w celu optymalizacji przepływu danych i rozwijania kompetencji z obszaru Data Engineeringu (Python, Pandas, SQL).
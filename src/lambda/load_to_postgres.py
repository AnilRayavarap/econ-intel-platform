import json
import boto3
import psycopg2
from datetime import datetime, timezone
import os

# ── Configuration ─────────────────────────────────────────────────────────────
REGION      = "us-east-1"
RAW_BUCKET  = "econ-intel-raw-prod-001"
DB_CONFIG   = {
    "host":     "localhost",
    "database": "econ_intel_db",
    "user":     "postgres",
    "password": "EconIntel@2026!",
    "port":     5432
}

def get_s3_files(date_str):
    """List all FRED JSON files for a given date."""
    s3 = boto3.client("s3", region_name=REGION)
    year  = date_str[:4]
    month = date_str[5:7]
    day   = date_str[8:10]
    prefix = f"fred/{year}/{month}/{day}/"

    response = s3.list_objects_v2(Bucket=RAW_BUCKET, Prefix=prefix)
    files = []
    for obj in response.get("Contents", []):
        key = obj["Key"]
        if "pipeline_summary" not in key:
            files.append(key)
    return files

def read_s3_file(key):
    """Read a JSON file from S3."""
    s3 = boto3.client("s3", region_name=REGION)
    response = s3.get_object(Bucket=RAW_BUCKET, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))

def load_observations(conn, data):
    """Load observations into fact_observations table."""
    cursor = conn.cursor()
    series_id    = data["series_id"]
    captured_date = data["captured_date"]
    captured_ts   = data["captured_ts"]
    observations  = data["observations"]

    inserted = 0
    skipped  = 0

    for obs in observations:
        date_val  = obs.get("date")
        value_str = obs.get("value", "")

        # Skip missing values (FRED uses "." for missing)
        if value_str == "." or value_str == "" or value_str is None:
            skipped += 1
            continue

        try:
            value = float(value_str)
        except ValueError:
            skipped += 1
            continue

        # Upsert — insert or update if exists
        cursor.execute("""
            INSERT INTO econ.fact_observations
                (series_id, observation_date, value,
                 captured_date, captured_ts)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (series_id, observation_date)
            DO UPDATE SET
                value        = EXCLUDED.value,
                captured_date = EXCLUDED.captured_date,
                captured_ts   = EXCLUDED.captured_ts,
                is_revised    = CASE
                    WHEN econ.fact_observations.value
                         != EXCLUDED.value THEN TRUE
                    ELSE FALSE
                END
        """, (series_id, date_val, value, captured_date, captured_ts))
        inserted += 1

    conn.commit()
    cursor.close()
    print(f"   ✅ {series_id}: {inserted} records loaded, {skipped} skipped")
    return inserted, skipped

def log_quality_run(conn, run_date, series_id, total, passed, failed):
    """Log quality run results."""
    cursor = conn.cursor()
    quality_score = round((passed / total * 100), 2) if total > 0 else 0
    status = "PASSED" if quality_score >= 99 else "WARNING"

    cursor.execute("""
        INSERT INTO econ.quality_run_log
            (run_date, run_ts, series_id,
             total_records, passed_records,
             failed_records, quality_score, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        run_date,
        datetime.now(timezone.utc),
        series_id,
        total, passed, failed,
        quality_score, status
    ))
    conn.commit()
    cursor.close()

def main():
    """Main function — loads today's FRED data into PostgreSQL."""
    print("🚀 Loading FRED data into PostgreSQL...")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"📅 Processing date: {today}")

    # ── Connect to PostgreSQL ─────────────────────────────────────────────────
    print("🔌 Connecting to PostgreSQL...")
    conn = psycopg2.connect(**DB_CONFIG)
    print("✅ Connected successfully!")

    # ── Get S3 files for today ────────────────────────────────────────────────
    print("📂 Reading files from S3...")
    files = get_s3_files(today)
    print(f"   Found {len(files)} series files")

    # ── Load each series ──────────────────────────────────────────────────────
    total_inserted = 0
    total_skipped  = 0

    for s3_key in files:
        series_id = s3_key.split("/")[-1].split("_")[0]
        print(f"📊 Loading: {series_id}")

        data     = read_s3_file(s3_key)
        ins, skp = load_observations(conn, data)
        total_inserted += ins
        total_skipped  += skp

        log_quality_run(
            conn, today, series_id,
            ins + skp, ins, skp
        )

    # ── Final summary ─────────────────────────────────────────────────────────
    print(f"\n✅ Load complete!")
    print(f"   Total inserted: {total_inserted}")
    print(f"   Total skipped:  {total_skipped}")

    # ── Verify row count ──────────────────────────────────────────────────────
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM econ.fact_observations")
    count = cursor.fetchone()[0]
    print(f"   Total rows in DB: {count}")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
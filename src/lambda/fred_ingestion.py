import json
import boto3
import requests
import os
from datetime import datetime, timezone

# ── Configuration ─────────────────────────────────────────────────────────────
REGION          = "us-east-1"
SECRET_NAME     = "prod/econ-intel/fred-api-key"
RAW_BUCKET      = "econ-intel-raw-prod-001"
FRED_BASE_URL   = "https://api.stlouisfed.org/fred/series/observations"

# ── 12 Economic Series to track ───────────────────────────────────────────────
FRED_SERIES = {
    "GDP":          "Gross Domestic Product",
    "CPIAUCSL":     "Consumer Price Index - Inflation",
    "UNRATE":       "Unemployment Rate",
    "FEDFUNDS":     "Federal Funds Rate",
    "M2SL":         "M2 Money Supply",
    "UMCSENT":      "Consumer Sentiment Index",
    "INDPRO":       "Industrial Production Index",
    "HOUST":        "Housing Starts",
    "RETAILSMNSA":  "Retail Sales",
    "T10YIE":       "10-Year Inflation Expectations",
    "DGS10":        "10-Year Treasury Yield",
    "DCOILWTICO":   "WTI Crude Oil Price"
}

def get_api_key():
    """Retrieve FRED API key from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name=REGION)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    return response["SecretString"]

def fetch_series(series_id, api_key):
    """Fetch observations for a single FRED series."""
    params = {
        "series_id":          series_id,
        "api_key":            api_key,
        "file_type":          "json",
        "observation_start":  "2020-01-01",
        "sort_order":         "desc",
        "limit":              100
    }
    response = requests.get(FRED_BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def save_to_s3(data, series_id, captured_date):
    """Save raw JSON to S3 with date partition."""
    s3 = boto3.client("s3", region_name=REGION)
    year  = captured_date[:4]
    month = captured_date[5:7]
    day   = captured_date[8:10]
    key   = f"fred/{year}/{month}/{day}/{series_id}_{captured_date}.json"

    s3.put_object(
        Bucket      = RAW_BUCKET,
        Key         = key,
        Body        = json.dumps(data, indent=2),
        ContentType = "application/json"
    )
    print(f"✅ Saved: s3://{RAW_BUCKET}/{key}")
    return key

def lambda_handler(event, context):
    """Main Lambda handler — pulls all 12 FRED series and saves to S3."""
    print("🚀 FRED Economic Data Pipeline started")

    captured_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    captured_ts   = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Get API key from Secrets Manager ──────────────────────────────
    print("🔑 Fetching API key from Secrets Manager...")
    api_key = get_api_key()
    print("✅ API key retrieved successfully")

    # ── Step 2: Pull each series from FRED API ────────────────────────────────
    results      = []
    failed       = []

    for series_id, series_name in FRED_SERIES.items():
        print(f"📊 Fetching: {series_name} ({series_id})")
        try:
            data = fetch_series(series_id, api_key)
            observations = data.get("observations", [])

            # Add metadata to payload
            payload = {
                "series_id":    series_id,
                "series_name":  series_name,
                "captured_date": captured_date,
                "captured_ts":  captured_ts,
                "record_count": len(observations),
                "observations": observations
            }

            # Save to S3
            s3_key = save_to_s3(payload, series_id, captured_date)
            results.append({
                "series_id":   series_id,
                "status":      "success",
                "records":     len(observations),
                "s3_key":      s3_key
            })
            print(f"   → {len(observations)} observations saved")

        except Exception as e:
            print(f"❌ Failed: {series_id} — {str(e)}")
            failed.append({"series_id": series_id, "error": str(e)})

    # ── Step 3: Save summary file to S3 ──────────────────────────────────────
    summary = {
        "pipeline_run_date": captured_date,
        "pipeline_run_ts":   captured_ts,
        "total_series":      len(FRED_SERIES),
        "successful":        len(results),
        "failed":            len(failed),
        "series_results":    results,
        "failed_series":     failed
    }

    s3 = boto3.client("s3", region_name=REGION)
    summary_key = f"fred/{captured_date[:4]}/{captured_date[5:7]}/{captured_date[8:10]}/pipeline_summary_{captured_date}.json"
    s3.put_object(
        Bucket      = RAW_BUCKET,
        Key         = summary_key,
        Body        = json.dumps(summary, indent=2),
        ContentType = "application/json"
    )

    print(f"\n✅ Pipeline complete!")
    print(f"   Successful: {len(results)}/{len(FRED_SERIES)} series")
    print(f"   Failed:     {len(failed)} series")
    print(f"   Summary:    s3://{RAW_BUCKET}/{summary_key}")

    return {
        "statusCode": 200,
        "body": json.dumps(summary)
    }


# ── Local testing ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = lambda_handler({}, None)
    print(json.dumps(json.loads(result["body"]), indent=2))
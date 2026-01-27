from datetime import datetime

import pandas as pd
from influxdb_client import InfluxDBClient

# --- Configuration ---
# These match your podman-compose.yml settings
url = "http://localhost:12130"
token = "your_super_secret_admin_token"
org = "aleutian-finance"
bucket = "financial-data"

# The ID from your recent successful run
run_id = "spy-threshold-demo_v1.0.0_20251219_222820"


def load_backtest_data(run_id):
    print(f"Connecting to InfluxDB at {url}...")

    with InfluxDBClient(url=url, token=token, org=org) as client:
        # Flux query to get data and pivot fields into columns
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: -5y)
          |> filter(fn: (r) => r["_measurement"] == "forecast_evaluations")
          |> filter(fn: (r) => r["run_id"] == "{run_id}")
          // Pivot keeps the timestamp but turns "field" values into columns
          |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
          // Sort by time to ensure correct order
          |> sort(columns: ["_time"])
        '''

        print("Querying data (this might take a second)...")
        # Query directly into a Pandas DataFrame
        df = client.query_api().query_data_frame(query=query)

        # Cleanup: Drop internal InfluxDB columns we don't need
        cols_to_drop = ["result", "table", "_start", "_stop", "_measurement"]
        df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])

        # Rename _time to Date and make it the index
        if "_time" in df.columns:
            df.rename(columns={"_time": "Date"}, inplace=True)
            df.set_index("Date", inplace=True)

        return df


if __name__ == "__main__":
    try:
        df = load_backtest_data(run_id)
        timestampNow = datetime.now().strftime("%Y%m%d%H%M%S")
        df.to_csv(f"./backtest_results_{timestampNow}.csv")

        if df.empty:
            print("⚠️  No data found! Check your Run ID or time range.")
        else:
            print("\n✅ Data Successfully Loaded!")
            print(f"   Rows: {len(df)}")
            print(f"   Columns: {df.columns.tolist()}")

            print("\n--- First 5 Rows ---")
            # Show specific columns of interest
            cols = ["action", "current_price", "forecast_price", "available_cash", "position_after"]
            # Only show columns that actually exist in the dataframe
            cols = [c for c in cols if c in df.columns]
            print(df[cols].head())

            print("\n--- Final Status ---")
            print(df[cols].tail(1))

    except Exception as e:
        print(f"❌ Error: {e}")
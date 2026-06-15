"""
DATA HIGHWAY PROTOTYPE — Step 2: Pi Sensor Simulator → Azure Event Hubs
=========================================================================
Reads pi_sensor_readings.csv and replays it into Azure Event Hubs,
simulating a live OSI Pi feed via the AVEVA Adapter.

Each row is sent as a JSON message. Speed is configurable:
  - REALTIME:  1 row per 15 minutes (matches actual interval — too slow for demo)
  - FAST:      1 batch per second (good for live demos)
  - TURBO:     As fast as possible (good for bulk load testing)

Usage:
    pip install azure-eventhub pandas python-dotenv
    python 02_pi_simulator.py --speed fast
"""

import os
import sys
import json
import time
import argparse
import pandas as pd
from datetime import datetime
from azure.eventhub import EventHubProducerClient, EventData
from dotenv import load_dotenv

load_dotenv()


def create_producer():
    """Create Event Hub producer client."""
    conn_str = os.getenv("EVENTHUB_CONNECTION_STRING")
    hub_name = os.getenv("EVENTHUB_NAME", "pi-telemetry")

    if not conn_str:
        print("  ✗ EVENTHUB_CONNECTION_STRING not set in .env")
        sys.exit(1)

    producer = EventHubProducerClient.from_connection_string(
        conn_str=conn_str,
        eventhub_name=hub_name,
    )
    print(f"  ✓ Connected to Event Hub: {hub_name}")
    return producer


def simulate(speed="fast", max_rows=None):
    """
    Replay Pi sensor data into Event Hubs.

    Args:
        speed: 'realtime', 'fast', or 'turbo'
        max_rows: Stop after this many rows (None = all rows)
    """
    data_dir = os.getenv("DATA_DIR", "./sample_data")
    csv_path = os.path.join(data_dir, "pi_sensor_readings.csv")

    print(f"\n  Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    total = len(df) if max_rows is None else min(max_rows, len(df))
    print(f"  Total rows to send: {total:,}")
    print(f"  Speed mode: {speed.upper()}")

    # Group by timestamp to send all tags for a given time as one batch
    grouped = df.groupby("timestamp")
    timestamps = list(grouped.groups.keys())
    print(f"  Unique timestamps: {len(timestamps):,}")
    print(f"  Tags per timestamp: ~{len(df) // len(timestamps)}")

    # Speed settings
    delays = {
        "realtime": 900,   # 15 minutes between batches
        "fast": 1.0,       # 1 second between batches
        "turbo": 0.05,     # 50ms between batches
    }
    delay = delays.get(speed, 1.0)

    producer = create_producer()
    rows_sent = 0
    batch_count = 0
    start_time = time.time()

    print(f"\n  {'─' * 50}")
    print(f"  Streaming started at {datetime.now().strftime('%H:%M:%S')}")
    print(f"  {'─' * 50}\n")

    try:
        for ts in timestamps:
            if max_rows and rows_sent >= max_rows:
                break

            batch_df = grouped.get_group(ts)

            # Create Event Hub batch
            event_batch = producer.create_batch()

            for _, row in batch_df.iterrows():
                if max_rows and rows_sent >= max_rows:
                    break

                # Build the message in our common schema format
                message = {
                    "timestamp": row["timestamp"],
                    "tag_name": row["tag_name"],
                    "asset_id": row["asset_id"],
                    "value": float(row["value"]),
                    "unit": row["unit"],
                    "quality": row["quality"],
                    "source": "pi_simulator",
                    "ingested_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                }

                try:
                    event_batch.add(EventData(json.dumps(message)))
                except ValueError:
                    # Batch is full, send it and create a new one
                    producer.send_batch(event_batch)
                    event_batch = producer.create_batch()
                    event_batch.add(EventData(json.dumps(message)))

                rows_sent += 1

            # Send the batch
            producer.send_batch(event_batch)
            batch_count += 1

            # Progress
            if batch_count % 50 == 0 or batch_count <= 3:
                elapsed = time.time() - start_time
                rate = rows_sent / elapsed if elapsed > 0 else 0
                pct = (rows_sent / total) * 100
                print(f"  [{datetime.now().strftime('%H:%M:%S')}]"
                      f"  Batch {batch_count:>5,}"
                      f"  |  {rows_sent:>8,} / {total:,} rows"
                      f"  ({pct:5.1f}%)"
                      f"  |  {rate:.0f} rows/sec"
                      f"  |  Timestamp: {ts[:16]}")

            # Pace control
            time.sleep(delay)

    except KeyboardInterrupt:
        print(f"\n\n  ⊘ Stopped by user at {rows_sent:,} rows")
    finally:
        producer.close()

    elapsed = time.time() - start_time
    print(f"\n  {'═' * 50}")
    print(f"  SIMULATION COMPLETE")
    print(f"  {'═' * 50}")
    print(f"  Rows sent:  {rows_sent:,}")
    print(f"  Batches:    {batch_count:,}")
    print(f"  Duration:   {elapsed:.1f}s")
    print(f"  Avg rate:   {rows_sent / elapsed:.0f} rows/sec")
    print(f"  {'═' * 50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pi Sensor Data Simulator")
    parser.add_argument("--speed", choices=["realtime", "fast", "turbo"],
                        default="fast", help="Simulation speed")
    parser.add_argument("--max-rows", type=int, default=None,
                        help="Stop after N rows (default: send all)")
    args = parser.parse_args()

    print("=" * 60)
    print("DATA HIGHWAY — Pi Sensor Simulator → Azure Event Hubs")
    print("=" * 60)

    simulate(speed=args.speed, max_rows=args.max_rows)

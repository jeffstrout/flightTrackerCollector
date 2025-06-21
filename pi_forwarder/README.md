# Raspberry Pi Aircraft Forwarder

This script forwards aircraft data from your local dump1090 instance to the Flight Tracker Collector API.

## Installation on Raspberry Pi

```bash
# Download the script directly from GitHub
wget https://raw.githubusercontent.com/jeffstrout/flightTrackerCollector/main/pi_forwarder/aircraft_forwarder.py

# Make it executable
chmod +x aircraft_forwarder.py

# Test it
python3 aircraft_forwarder.py --interval 5
```

## Configuration

Edit the configuration section at the top of the script:

```python
API_ENDPOINT = "https://api.choppertracker.com/api/v1/aircraft/bulk"
API_KEY = "etex.abc123def456ghi789jkl012"  # Your API key
STATION_ID = "ETEX01"  # Your unique station ID
STATION_NAME = "East Texas 01"  # Your station name
DUMP1090_URL = "http://localhost:8080/data/aircraft.json"  # Your dump1090 URL
```

## Usage

```bash
# Run continuously (default 30 second interval)
python3 aircraft_forwarder.py

# Run with custom interval (5 seconds)
python3 aircraft_forwarder.py --interval 5

# Run once and exit
python3 aircraft_forwarder.py --once

# Run with custom parameters
python3 aircraft_forwarder.py \
  --api-key "etex.your-actual-key" \
  --station-id "YOUR_ID" \
  --station-name "Your Station Name"
```

## Running as a Service

Create a systemd service to run automatically:

```bash
sudo nano /etc/systemd/system/aircraft-forwarder.service
```

Add:
```ini
[Unit]
Description=Aircraft Data Forwarder
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/aircraft_forwarder.py --interval 30
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable aircraft-forwarder
sudo systemctl start aircraft-forwarder
sudo systemctl status aircraft-forwarder
```
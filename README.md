# WiCAN Data Logger v3 — Auto-Discovery Edition

> **⚠️ SAFETY DISCLAIMER**
>
> **DO NOT operate this software alone as a driver in your car.** This tool requires active monitoring of a laptop or mobile device screen, which is incompatible with safe vehicle operation. Always have a dedicated passenger handle the data logging while the driver focuses entirely on the road.
>
> Running diagnostic software while driving demands continuous attention to the logging interface. Distracted driving is dangerous and illegal in many jurisdictions. If you must log data during a drive, ensure a second person is present to manage the equipment.
>
> *The authors of this software accept no liability for accidents, injuries, or damages resulting from improper use of this tool while operating a vehicle.*

---

## Overview

WiCAN Data Logger v3 is a standalone Python 3 script that automatically discovers a [WiCAN Pro](https://github.com/meatpiHQ/wican-fw) device on the local network, polls its AutoPID data endpoint at configurable intervals, and writes all received parameters to a timestamped CSV file.

The script uses **zero external dependencies** — only the Python standard library (`urllib`, `ssl`, `csv`, `json`, `socket`, `concurrent.futures`).

Primary use case: real-time logging of OBD-II diagnostic data from electric vehicles (tested with the **Hyundai Ioniq Electric 2021 38 kWh**) via the WiCAN Pro's HTTP API.

## Features

- **Three-phase auto-discovery** — mDNS hostnames → common IPs → full subnet scan
- **Dynamic field handling** — new parameters appearing mid-session are seamlessly added to the CSV
- **Three display modes** — full grouped view, compact single-line, or minimal key output
- **Error recovery** — automatic reconnection on network interruptions
- **No dependencies** — runs on any Python 3.6+ installation out of the box

## Requirements

- Python 3.6+
- Network access to the WiCAN Pro device (same Wi-Fi or WiCAN AP mode)
- WiCAN Pro with an AutoPID configuration loaded and active

## Installation

No installation required. Clone or download the script:

```bash
git clone https://github.com/sbaliko/wican-data-logger.git
cd wican-data-logger
```

## Usage

```bash
python3 wican_logger_v3.py
```

The script will auto-discover the WiCAN device and begin logging. Press `Ctrl+C` to stop — a summary of all captured fields and the output file path will be printed on exit.

## Configuration

All configuration is done via constants at the top of the script. No command-line arguments needed.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `WICAN_IP` | `""` | Manual IP of WiCAN device. Leave empty for auto-discovery. |
| `WICAN_HOSTNAMES` | `["wican.local", "wican"]` | mDNS/hostname list for discovery phase 1. |
| `SCAN_SUBNETS` | `[]` | Subnets to scan. Auto-detected from local IP if empty. |
| `WICAN_PORT` | `80` | HTTP port used by the WiCAN device. |
| `OUTPUT_FILE` | `wican_log_YYYYMMDD_HHMMSS.csv` | Output CSV filename with auto-generated timestamp. |
| `INTERVAL` | `1` | Polling interval in seconds. |
| `DISPLAY_MODE` | `"all"` | Console output: `"all"`, `"compact"`, or `"key"`. |

## Network Auto-Discovery

When `WICAN_IP` is left empty, the script runs a three-phase discovery:

1. **mDNS Hostname Resolution** — Resolves `wican.local` and `wican` via DNS, then verifies the `/autopid_data` endpoint.
2. **Common IP Probing** — Probes known WiCAN/ESP32 default IPs (e.g., `192.168.8.102`) in parallel with 10 threads.
3. **Full Subnet Scan** — Scans all 254 addresses on the local subnet using 50 threads with 0.5s timeout per host. Typically completes in 1–3 seconds.
4. **Interactive Fallback** — If all phases fail, prompts the user to enter the IP address manually. Validates format and probes the address before proceeding. Type `q` to quit.

## Display Modes

| Mode | Behavior |
|------|----------|
| `all` | Full grouped display with parameters organized by category (Cells, BMS, VMCU, Temps, Drive, TPMS, Other). Cell voltages shown in rows of 16. |
| `compact` | Single-line: SOC, HV voltage, current, power, and parameter count. |
| `key` | Minimal: timestamp, row number, SOC %, and parameter count. |

## Output Format

The output is a standard CSV file (`wican_log_YYYYMMDD_HHMMSS.csv`):

- First column: `timestamp` in ISO 8601 format
- Subsequent columns: parameter names from the WiCAN AutoPID configuration
- Columns are added dynamically as new parameters appear

Example columns for a Hyundai Ioniq Electric: `SOC_pct`, `HV_Voltage_V`, `HV_Current_A`, `HV_Power_kW`, `Cell_V_01`–`Cell_V_96`, `BMS_Batt_Temp_C`, etc.

## Function Reference

| Function | Description |
|----------|-------------|
| `get_local_ip()` | Determines local IP via UDP socket to infer the subnet for scanning. |
| `get_subnets_to_scan()` | Returns configured or auto-detected subnets. Falls back to common home network ranges. |
| `check_wican(ip, timeout)` | Probes a single IP via `/autopid_data` and verifies valid JSON response. |
| `scan_subnet(subnet, start, end)` | Parallel scan with 50-thread pool and 0.5s timeout per host. |
| `discover_wican()` | Orchestrates the three-phase discovery process. |
| `fetch_data()` | HTTP GET to `/autopid_data` with 5s timeout. Returns parsed JSON or `None`. |
| `rewrite_csv(filepath, fieldnames, all_rows)` | Rewrites CSV when new fields appear to maintain consistent column structure. |
| `format_value(key, value)` | Context-aware formatting (°, %, V, A, kW) based on parameter name. |
| `print_all_data(...)` | Grouped categorized console output with cell voltage grid. |
| `print_compact_data(...)` | Single-line summary with key HV battery parameters. |
| `main()` | Entry point: discovery → manual IP prompt if needed → CSV init → polling loop → Ctrl+C shutdown. |

## Troubleshooting

**Device not found:**
- Verify the WiCAN Pro is powered on with LED indicating network connectivity
- Ensure your computer is on the same Wi-Fi network or connected to the WiCAN's AP (default SSID: `WiCAN_XXXXXX`)
- If auto-discovery fails, the script will prompt you to enter the IP manually. You can also pre-set `WICAN_IP` in the script
- Check for firewall rules blocking HTTP on port 80

**Empty or missing data:**
- Confirm an AutoPID profile is loaded and active on the device
- Verify the vehicle's ignition is on (some ECUs only respond when awake)
- Check the WiCAN web interface at `http://<device-ip>` to confirm data flow

**CSV has inconsistent columns:**
- This is expected — the script rewrites headers when new fields appear
- For a fixed column set, post-process the CSV or keep the vehicle in a consistent state

## License

Provided as-is for personal and educational use in automotive diagnostics research.

## Credits

Script and documentation created with the assistance of [Claude by Anthropic](https://claude.ai).

---

> **Reminder:** Never operate this logger alone while driving. Always have a dedicated passenger manage the diagnostic equipment. Your safety and the safety of others on the road must always come first.

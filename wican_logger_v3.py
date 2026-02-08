#!/usr/bin/env python3
"""
WiCAN Data Logger v3 (No external dependencies)
Auto-discovers WiCAN on local network!
Downloads data from WiCAN autopid endpoint and saves to CSV every second.

Created with the assistance of Claude by Anthropic (claude.ai)
"""

import urllib.request
import ssl
import csv
import time
import json
import os
import socket
import concurrent.futures
from datetime import datetime

# ============== CONFIGURATION ==============
# Leave empty for auto-discovery, or set manually:
WICAN_IP = ""  # e.g., "192.168.8.102"

# Common WiCAN hostnames to try first
WICAN_HOSTNAMES = [
    "wican.local",
    "wican",
]

# Subnets to scan (auto-detected if empty)
SCAN_SUBNETS = []  # e.g., ["192.168.1", "192.168.8"]

# Port WiCAN uses
WICAN_PORT = 80

OUTPUT_FILE = f"wican_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
INTERVAL = 1  # seconds

# Display mode: "all", "compact", or "key"
DISPLAY_MODE = "all"
# ===========================================

# Create SSL context that ignores certificate verification
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

working_url = None

def get_local_ip():
    """Get local IP address to determine subnet"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return None

def get_subnets_to_scan():
    """Get list of subnets to scan"""
    if SCAN_SUBNETS:
        return SCAN_SUBNETS
    
    local_ip = get_local_ip()
    if local_ip:
        # Extract subnet (first 3 octets)
        parts = local_ip.split('.')
        subnet = '.'.join(parts[:3])
        return [subnet]
    
    # Fallback to common subnets
    return ["192.168.1", "192.168.0", "192.168.8", "10.0.0"]

def check_wican(ip, timeout=1):
    """Check if IP is a WiCAN device"""
    url = f"http://{ip}/autopid_data"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode('utf-8')
            # Verify it's JSON (WiCAN response)
            json.loads(data)
            return ip
    except:
        return None

def scan_subnet(subnet, start=1, end=255):
    """Scan a subnet for WiCAN devices"""
    print(f"  Scanning {subnet}.{start}-{end}...", end=" ", flush=True)
    
    found = []
    ips = [f"{subnet}.{i}" for i in range(start, end + 1)]
    
    # Use thread pool for parallel scanning
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = executor.map(lambda ip: check_wican(ip, timeout=0.5), ips)
        for result in results:
            if result:
                found.append(result)
    
    if found:
        print(f"Found: {found}")
    else:
        print("not found")
    
    return found

def discover_wican():
    """Auto-discover WiCAN on the network"""
    print("=" * 50)
    print("WiCAN Auto-Discovery")
    print("=" * 50)
    
    # 1. Try hostnames first (fastest)
    print("\n[1/3] Trying known hostnames...")
    for hostname in WICAN_HOSTNAMES:
        print(f"  Trying {hostname}...", end=" ", flush=True)
        try:
            ip = socket.gethostbyname(hostname)
            if check_wican(ip):
                print(f"Found! ({ip})")
                return ip
            print("no response")
        except:
            print("not found")
    
    # 2. Try common WiCAN IPs
    print("\n[2/3] Trying common WiCAN IPs...")
    common_ips = [
        "192.168.8.102",  # Default WiCAN AP mode
        "192.168.4.1",    # ESP32 AP default
        "192.168.1.100",
        "192.168.1.102",
        "192.168.0.100",
        "192.168.0.102",
    ]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(check_wican, common_ips))
        for ip, result in zip(common_ips, results):
            if result:
                print(f"  Found WiCAN at: {ip}")
                return ip
    print("  Not found in common IPs")
    
    # 3. Full subnet scan
    print("\n[3/3] Scanning local network...")
    subnets = get_subnets_to_scan()
    
    for subnet in subnets:
        found = scan_subnet(subnet)
        if found:
            return found[0]
    
    return None

def fetch_data():
    """Fetch data from WiCAN endpoint"""
    global working_url
    
    if not working_url:
        return None
    
    try:
        req = urllib.request.Request(working_url)
        ctx = ssl_context if working_url.startswith("https") else None
        with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
            data = response.read().decode('utf-8')
            return json.loads(data)
    except Exception:
        return None

def rewrite_csv(filepath, fieldnames, all_rows):
    """Rewrite the entire CSV with updated fieldnames"""
    with open(filepath, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

def format_value(key, value):
    """Format value for display based on key name"""
    if value is None:
        return "---"
    if isinstance(value, float):
        if 'Temp' in key or '_C' in key:
            return f"{value:.0f}°"
        elif 'pct' in key or 'SOC' in key or 'SOH' in key:
            return f"{value:.1f}%"
        elif 'Voltage' in key or '_V' in key:
            return f"{value:.2f}V"
        elif 'Current' in key or '_A' in key:
            return f"{value:.1f}A"
        elif 'Power' in key or '_kW' in key:
            return f"{value:.1f}kW"
        elif 'psi' in key:
            return f"{value:.1f}"
        else:
            return f"{value:.2f}"
    return str(value)

def print_all_data(data, row_count, timestamp):
    """Print all data in a formatted way"""
    time_str = timestamp[11:19]
    
    print(f"\n{'='*80}")
    print(f"[{time_str}] Row {row_count} | {len(data)} parameters")
    print(f"{'='*80}")
    
    # Group parameters by prefix
    groups = {}
    for key, value in sorted(data.items()):
        if key.startswith('Cell_') and '_V' in key:
            group = 'Cells'
        elif key.startswith('VMCU'):
            group = 'VMCU'
        elif key.startswith('BMS'):
            group = 'BMS'
        elif 'Temp' in key or '_C' in key:
            group = 'Temps'
        elif 'Gear' in key or 'Brake' in key or 'Regen' in key:
            group = 'Drive'
        elif 'psi' in key:
            group = 'TPMS'
        else:
            group = 'Other'
        
        if group not in groups:
            groups[group] = []
        groups[group].append((key, value))
    
    for group_name in ['Other', 'Drive', 'Temps', 'TPMS', 'VMCU', 'BMS', 'Cells']:
        if group_name not in groups:
            continue
        items = groups[group_name]
        
        if group_name == 'Cells':
            print(f"\n[{group_name}] ({len(items)} cells)")
            cells = [f"{format_value(k,v)}" for k, v in items]
            for i in range(0, len(cells), 16):
                row_cells = cells[i:i+16]
                cell_nums = f"{i+1:02d}-{min(i+16, len(cells)):02d}"
                print(f"  {cell_nums}: {' '.join(row_cells)}")
        else:
            print(f"\n[{group_name}]")
            line = "  "
            for key, value in items:
                short_key = key.replace('_pct', '%').replace('_V', 'V').replace('_A', 'A')
                short_key = short_key.replace('_kW', 'kW').replace('_C', '°').replace('_km', 'km')
                short_key = short_key.replace('Batt_', '').replace('Cell_V_', 'Cell')
                
                formatted = f"{short_key}:{format_value(key, value)}"
                
                if len(line) + len(formatted) > 78:
                    print(line)
                    line = "  "
                line += formatted + " "
            if line.strip():
                print(line)

def print_compact_data(data, row_count, timestamp):
    """Print compact single-line output"""
    time_str = timestamp[11:19]
    
    soc = data.get('SOC_pct', data.get('SOC', '---'))
    voltage = data.get('HV_Voltage_V', '---')
    current = data.get('HV_Current_A', '---')
    power = data.get('HV_Power_kW', '---')
    
    if isinstance(soc, (int, float)):
        soc = f"{soc:.1f}%"
    if isinstance(voltage, (int, float)):
        voltage = f"{voltage:.1f}V"
    if isinstance(current, (int, float)):
        current = f"{current:.1f}A"
    if isinstance(power, (int, float)):
        power = f"{power:.1f}kW"
    
    print(f"[{time_str}] #{row_count} | SOC:{soc} | {voltage} | {current} | {power} | {len(data)} params")

def main():
    global working_url
    
    print(f"\n{'#'*50}")
    print(f"#  WiCAN Data Logger v3 - Auto Discovery")
    print(f"{'#'*50}\n")
    
    # Discover or use configured IP
    if WICAN_IP:
        wican_ip = WICAN_IP
        print(f"Using configured IP: {wican_ip}")
    else:
        wican_ip = discover_wican()
        if not wican_ip:
            print("\n" + "!"*50)
            print("WARNING: Could not find WiCAN on network!")
            print("!"*50)
            print("\nTroubleshooting:")
            print("  1. Make sure WiCAN is powered on")
            print("  2. Check that you're on the same network")
            print("  3. Enter the IP address manually below")
            
            while True:
                try:
                    user_input = input("\nEnter WiCAN IP address (or 'q' to quit): ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    return
                
                if user_input.lower() in ('q', 'quit', 'exit', ''):
                    print("Exiting.")
                    return
                
                # Basic IP format validation
                parts = user_input.split('.')
                if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                    print(f"  Invalid IP format: {user_input}")
                    continue
                
                print(f"  Checking {user_input}...", end=" ", flush=True)
                if check_wican(user_input, timeout=3):
                    print("Connected!")
                    wican_ip = user_input
                    break
                else:
                    print("no response.")
                    print("  Device not found at that address. Try again or press 'q' to quit.")
    
    working_url = f"http://{wican_ip}/autopid_data"
    
    print(f"\n{'='*50}")
    print(f"WiCAN found at: {wican_ip}")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Interval: {INTERVAL}s | Display: {DISPLAY_MODE}")
    print(f"{'='*50}")
    print("\nPress Ctrl+C to stop logging\n")
    
    row_count = 0
    error_count = 0
    fieldnames = ["timestamp"]
    all_rows = []
    
    try:
        while True:
            start_time = time.time()
            
            data = fetch_data()
            
            if data:
                error_count = 0
                timestamp = datetime.now().isoformat()
                
                row = {"timestamp": timestamp}
                row.update(data)
                
                current_keys = set(row.keys())
                known_keys = set(fieldnames)
                new_keys = current_keys - known_keys
                
                if new_keys:
                    sorted_new_keys = sorted(new_keys)
                    fieldnames.extend(sorted_new_keys)
                    
                    if row_count == 0:
                        print(f"Initial fields: {len(fieldnames)} parameters\n")
                    else:
                        print(f"\n  [+] New fields: {sorted_new_keys}")
                        rewrite_csv(OUTPUT_FILE, fieldnames, all_rows)
                
                all_rows.append(row)
                
                with open(OUTPUT_FILE, 'a', newline='') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    if row_count == 0 or csvfile.tell() == 0:
                        writer.writeheader()
                    writer.writerow(row)
                
                row_count += 1
                
                if DISPLAY_MODE == "all":
                    print_all_data(data, row_count, timestamp)
                elif DISPLAY_MODE == "compact":
                    print_compact_data(data, row_count, timestamp)
                else:
                    soc = data.get('SOC_pct', data.get('SOC', 'N/A'))
                    print(f"[{timestamp[11:19]}] Row {row_count} | SOC: {soc}% | {len(data)} params")
            else:
                error_count += 1
                if error_count == 1:
                    print(f"Connection lost, reconnecting...")
                elif error_count % 10 == 0:
                    print(f"Still trying... (attempt {error_count})")
            
            elapsed = time.time() - start_time
            sleep_time = max(0, INTERVAL - elapsed)
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print(f"\n\n{'='*50}")
        print(f"Logging stopped.")
        print(f"Total rows: {row_count}")
        print(f"Total fields: {len(fieldnames)}")
        if row_count > 0:
            print(f"Data saved to: {OUTPUT_FILE}")
            print(f"\nAll fields captured:")
            for i, field in enumerate(fieldnames):
                print(f"  {i+1:3d}. {field}")

if __name__ == "__main__":
    main()

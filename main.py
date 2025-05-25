import os
import re
import time
import requests
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import sys

LOG_PATH = 'log.txt'
OUTPUT_PATH = 'output.html'
BANLIST_PATH = 'banlist.xml'
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1376143107933995018/4-A-FkVJbUgm3W2HbNuauxfKr26l_3XZUhKnwNWSu5J9rq1zoTQeDD4J3WOaMMC5_mXf'
LICENSE_KEY = 'Enes'
LICENSE_SERVER_URL = f'http://localhost:5050/verify?license={LICENSE_KEY}'

players = []
lock = threading.Lock()

def check_license():
    try:
        r = requests.get(LICENSE_SERVER_URL)
        if r.status_code == 200:
            data = r.json()
            if data.get("valid"):
                print(f"✅ Lisans doğrulandı. Kullanıcı: {data.get('user')}")
            else:
                print("❌ Geçersiz lisans. Sistem iptal ediliyor.")
                sys.exit(1)
        else:
            print(f"❌ Lisans sunucusundan geçersiz yanıt: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Lisans sunucusuna erişilemedi: {e}")
        sys.exit(1)

def parse_log_line(line):
    time_match = re.match(r'\[(.*?)\]', line)
    timestamp = time_match.group(1) if time_match else "Bilinmeyen Zaman"

    cheat_match = re.search(r'\] ([A-Za-z]+) tespit edildi!', line)
    cheat_type = cheat_match.group(1) if cheat_match else "Bilinmeyen Hile"

    player_match = re.search(r'Oyuncu: ([^,]+)', line)
    player_name = player_match.group(1) if player_match else "Bilinmeyen Oyuncu"

    serial_match = re.search(r'Serial: ([^,]+)', line)
    serial = serial_match.group(1) if serial_match else "-"

    ip_match = re.search(r'IP: ([^,]+)', line)
    ip = ip_match.group(1) if ip_match else "Bilinmeyen IP"

    details_match = re.search(r'IP: [^,]+,(.*)$', line)
    if not details_match:
        details_match = re.search(r'Serial: [^,]+,(.*)$', line)
    details = details_match.group(1).strip() if details_match else "Detay yok"

    return {
        "timestamp": timestamp,
        "timestamp_dt": datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') if timestamp != "Bilinmeyen Zaman" else None,
        "cheat": cheat_type,
        "player": player_name,
        "serial": serial,
        "ip": ip,
        "details": details
    }

def cheat_color_class(cheat):
    mapping = {
        'SpeedHack': 'speedhack',
        'Aimbot': 'aimbot',
        'Wallhack': 'wallhack',
        'Triggerbot': 'triggerbot',
        'Bilinmeyen Hile': 'unknown'
    }
    return mapping.get(cheat, 'unknown')

def generate_player_card(p):
    return f'''
    <div class="player-card {cheat_color_class(p['cheat'])}" data-name="{p['player'].lower()}" data-cheat="{p['cheat'].lower()}">
        <div class="header" onclick="this.nextElementSibling.classList.toggle('show')">
            <span class="player-name">{p['player']}</span>
            <span class="cheat-type">{p['cheat']}</span>
            <span class="timestamp">{p['timestamp']}</span>
        </div>
        <div class="details-content">
            <div>Serial: {p['serial']}</div>
            <div>IP: {p['ip']}</div>
            <div>Detay: {p['details']}</div>
            <button class="ban-btn" onclick="banPlayer(event, '{p['serial']}', '{p['player']}')">Banla</button>
        </div>
    </div>
    '''

def generate_html(players):
    players_sorted = sorted(players, key=lambda p: p['timestamp_dt'] or datetime.min, reverse=True)
    html_head = '''<!DOCTYPE html><html lang="tr"><head><meta charset="UTF-8"><title>MTA:SA Anti-Cheat Panel</title>
<style>
    body {background:#0a0a14; color:#eee; font-family: Arial, sans-serif; max-width: 960px; margin: 20px auto;}
    h1 {text-align:center; margin-bottom: 20px;}
    #searchBox {width: 100%; padding: 10px; font-size: 16px; margin-bottom: 20px; border-radius: 6px; border: none;}
    .player-card {background: #222; border-left: 8px solid #666; margin: 10px 0; padding: 10px; border-radius: 6px;}
    .player-card:hover {background-color: #333;}
    .header {display: flex; flex-wrap: wrap; gap: 10px; font-weight: bold; cursor: pointer;}
    .serial, .cheat-type, .timestamp {font-size: 14px; color: #ccc;}
    .details-content {display: none; padding-top: 10px; color: #ddd;}
    .details-content.show {display: block;}
    button.ban-btn {margin-top: 10px; background-color: red; color: white; border: none; padding: 5px 10px; border-radius: 4px;}
    .player-card.speedhack {border-left-color: #e53935;}
    .player-card.aimbot {border-left-color: #fb8c00;}
    .player-card.wallhack {border-left-color: #43a047;}
    .player-card.triggerbot {border-left-color: #1e88e5;}
    .player-card.unknown {border-left-color: #757575;}
</style>
</head><body>
<h1>MTA:SA Anti-Cheat Panel</h1>
<input type="text" id="searchBox" placeholder="Oyuncu adı veya hile türü ara...">

<script>
function banPlayer(e, serial, name) {
    e.stopPropagation();
    if (confirm(name + " adlı oyuncuyu banlamak istiyor musunuz?")) {
        fetch("/ban?serial=" + encodeURIComponent(serial) + "&name=" + encodeURIComponent(name))
        .then(r => r.json()).then(data => {
            alert(data.success ? name + " banlandı!" : "Hata: " + data.message);
        });
    }
}
document.addEventListener("DOMContentLoaded", function () {
    const searchBox = document.getElementById("searchBox");
    searchBox.addEventListener("input", function () {
        const query = this.value.toLowerCase();
        document.querySelectorAll(".player-card").forEach(card => {
            const name = card.getAttribute("data-name");
            const cheat = card.getAttribute("data-cheat");
            card.style.display = (name.includes(query) || cheat.includes(query)) ? "block" : "none";
        });
    });
});
</script>
'''
    cards = ''.join(generate_player_card(p) for p in players_sorted)
    return html_head + cards + '</body></html>'

def update_output_html():
    global players
    with lock:
        try:
            with open(LOG_PATH, 'r', encoding='utf-8') as f:
                lines = [parse_log_line(line) for line in f if line.strip()]
            players = lines
            with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
                f.write(generate_html(players))
        except Exception as e:
            print(f"HTML Güncelleme Hatası: {e}")

def add_to_banlist(serial, name):
    with lock:
        if not os.path.exists(BANLIST_PATH):
            with open(BANLIST_PATH, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n<bans>\n</bans>')

        with open(BANLIST_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        if serial in content:
            return False, "Zaten banlanmış."

        ban_entry = f'  <ban serial="{serial}" name="{name}" reason="AntiCheat Ban" timestamp="{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}" />\n'
        content = content.replace('</bans>', ban_entry + '</bans>')
        with open(BANLIST_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, None

def send_discord_embed(log_data):
    try:
        dt = datetime.strptime(log_data["timestamp"], '%Y-%m-%d %H:%M:%S')
        iso_timestamp = dt.isoformat()
    except:
        iso_timestamp = None

    embed = {
        "title": f"{log_data['cheat']} tespit edildi!",
        "color": 0xFF0000,
        "fields": [
            {"name": "Oyuncu", "value": log_data["player"], "inline": True},
            {"name": "Serial", "value": log_data["serial"], "inline": True},
            {"name": "IP", "value": log_data["ip"], "inline": True},
            {"name": "Detay", "value": log_data["details"], "inline": False}
        ],
        "footer": {"text": "MTA:SA AntiCheat"},
    }
    if iso_timestamp:
        embed["timestamp"] = iso_timestamp

    response = requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]}, headers={"Content-Type": "application/json"})
    if response.status_code != 204:
        print(f"Discord gönderim hatası: {response.status_code} - {response.text}")

def tail_log_file(path):
    with open(path, "r", encoding="utf-8") as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(1)
                continue
            parsed = parse_log_line(line.strip())
            send_discord_embed(parsed)
            update_output_html()

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ['/', '/output.html']:
            try:
                with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(content.encode())
            except:
                self.send_error(500)
        elif parsed.path == '/ban':
            qs = parse_qs(parsed.query)
            serial = qs.get('serial', [''])[0]
            name = qs.get('name', [''])[0]
            if not serial or not name:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'{"success": false, "message": "Eksik parametre."}')
                return
            success, msg = add_to_banlist(serial, name)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "message": msg}).encode())
        else:
            self.send_error(404)

def run_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, RequestHandler)
    print("Sunucu başlatıldı: http://localhost:8080/")
    httpd.serve_forever()

if __name__ == '__main__':
    check_license()
    update_output_html()
    threading.Thread(target=tail_log_file, args=(LOG_PATH,), daemon=True).start()
    run_server()

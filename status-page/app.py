# /status-page/app.py
#
# Versione aggiornata con la funzionalità di visualizzazione dello spazio disponibile su disco.

from flask import Flask, jsonify, render_template, request
import subprocess
import os
import json
import re
import shutil
from datetime import datetime

app = Flask(__name__)

CONTAINER_NAMES = ["ftp_server", "sftp_server", "file_forwarder"]
ADMIN_PASSWORD = "[REDACTED]"

FTP_USERS_TXT = "/ftp_config/virtual_users.txt"
FTP_USER_CONF_DIR = "/ftp_config/user_conf/"
SFTP_USERS_JSON = "/sftp_config/sftp.json"
FTP_LOG_FILE = "/var/log/vsftpd/vsftpd.log"

# --- Funzioni Helper ---

def run_docker_command(command):
    """Esegue un comando Docker e restituisce l'output o l'errore."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return {"message": f"Comando '{' '.join(command)}' eseguito con successo.", "output": result.stdout}, 200
    except subprocess.CalledProcessError as e:
        error_message = f"Errore durante l'esecuzione del comando: {e.stderr}"
        print(error_message)
        return {"error": error_message}, 500
    except Exception as e:
        error_message = f"Errore imprevisto: {e}"
        print(error_message)
        return {"error": error_message}, 500

def read_ftp_users():
    """Legge e analizza il file degli utenti FTP."""
    users = []
    try:
        with open(FTP_USERS_TXT, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        it = iter(lines)
        for username in it:
            password = next(it, None)
            if password:
                user_data = {"username": username, "password": password, "type": "ftp"}
                try:
                    with open(os.path.join(FTP_USER_CONF_DIR, username), 'r') as conf_f:
                        for line in conf_f:
                            if line.startswith('local_root='):
                                user_data['homedir'] = line.strip().split('=')[1]
                except FileNotFoundError:
                    user_data['homedir'] = 'N/A'
                users.append(user_data)
    except Exception as e:
        print(f"Errore lettura utenti FTP: {e}")
    return users

def read_sftp_users():
    """Legge e analizza il file di configurazione SFTP."""
    users = []
    try:
        with open(SFTP_USERS_JSON, 'r') as f:
            data = json.load(f)
        for user in data.get("Users", []):
            users.append({
                "username": user.get("Username"),
                "password": user.get("Password"),
                "homedir": f"{user.get('Chroot', {}).get('Directory', '')}/{user.get('Chroot', {}).get('StartPath', '')}",
                "type": "sftp"
            })
    except Exception as e:
        print(f"Errore lettura utenti SFTP: {e}")
    return users

# --- Route Principali e API ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    statuses = {name: 'not_found' for name in CONTAINER_NAMES}
    try:
        cmd = ["docker", "ps", "--all", "--format", "{{.Names}}|{{.Status}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                name, status_text = line.split('|', 1)
                if name in CONTAINER_NAMES:
                    if 'Up' in status_text: statuses[name] = 'running'
                    elif 'Exited' in status_text: statuses[name] = 'exited'
                    elif 'Restarting' in status_text: statuses[name] = 'restarting'
                    else: statuses[name] = 'unknown'
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify(statuses)

@app.route('/api/logs/<container_name>')
def get_logs(container_name):
    if container_name not in CONTAINER_NAMES:
        return jsonify({"error": "Nome container non valido"}), 400
    try:
        cmd = ["docker", "logs", "--tail", "50", container_name]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        logs = stdout.decode('utf-8', errors='ignore') + stderr.decode('utf-8', errors='ignore')
        return jsonify({"name": container_name, "logs": logs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/users', methods=['GET'])
def get_users():
    # Assicura che gli utenti predefiniti siano presenti
    ensure_default_users()
    
    all_users = read_ftp_users() + read_sftp_users()
    return jsonify(all_users)

def ensure_default_users():
    """Assicura che gli utenti predefiniti siano sempre presenti."""
    # Utenti FTP predefiniti
    default_ftp_users = [
        {"username": "ftpuser", "password": "[REDACTED]", "homedir": "/home/vsftpd/ftpuser"},
        {"username": "hlagt", "password": "[REDACTED]", "homedir": "/home/vsftpd/hlagt"}
    ]
    
    # Utente SFTP predefinito
    default_sftp_users = [
        {
            "Username": "customer1",
            "Password": "[REDACTED]",
            "Chroot": {"Directory": "/home/customer1", "StartPath": "filescma"},
            "Directories": ["filescma"]
        }
    ]
    
    # Verifica e aggiorna gli utenti FTP
    current_ftp_users = read_ftp_users()
    current_ftp_usernames = [user["username"] for user in current_ftp_users]
    
    # Aggiungi utenti FTP mancanti
    ftp_users_to_add = []
    for default_user in default_ftp_users:
        if default_user["username"] not in current_ftp_usernames:
            ftp_users_to_add.append(default_user)
    
    if ftp_users_to_add:
        # Leggi gli utenti esistenti
        existing_users = []
        try:
            with open(FTP_USERS_TXT, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            it = iter(lines)
            for username in it:
                password = next(it, None)
                if password:
                    existing_users.append({"username": username, "password": password})
        except Exception:
            pass
        
        # Aggiungi gli utenti mancanti
        with open(FTP_USERS_TXT, 'w') as f:
            for user in existing_users:
                f.write(f"{user['username']}\n")
                f.write(f"{user['password']}\n")
            
            for user in ftp_users_to_add:
                f.write(f"{user['username']}\n")
                f.write(f"{user['password']}\n")
        
        # Crea i file di configurazione per gli utenti mancanti
        for user in ftp_users_to_add:
            with open(os.path.join(FTP_USER_CONF_DIR, user['username']), 'w') as f:
                f.write(f"local_root={user['homedir']}\n")
        
        # Riavvia il server FTP
        run_docker_command(["docker", "restart", "ftp_server"])
    
    # Verifica e aggiorna gli utenti SFTP
    try:
        with open(SFTP_USERS_JSON, 'r') as f:
            sftp_config = json.load(f)
        
        current_sftp_usernames = [user.get("Username") for user in sftp_config.get("Users", [])]
        
        # Aggiungi utenti SFTP mancanti
        sftp_users_to_add = []
        for default_user in default_sftp_users:
            if default_user["Username"] not in current_sftp_usernames:
                sftp_users_to_add.append(default_user)
        
        if sftp_users_to_add:
            sftp_config["Users"].extend(sftp_users_to_add)
            
            with open(SFTP_USERS_JSON, 'w') as f:
                json.dump(sftp_config, f, indent=4)
            
            # Riavvia il server SFTP
            run_docker_command(["docker", "restart", "sftp_server"])
    except Exception as e:
        print(f"Errore aggiornamento utenti SFTP: {e}")

@app.route('/api/admin-action', methods=['POST'])
def admin_action():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Richiesta non valida"}), 400
        
    password = data.get('password')
    action = data.get('action')
    # **FIX**: Accetta i dati sia dalla chiave 'payload' che 'target' per essere
    # compatibile con tutte le chiamate JavaScript.
    payload = data.get('payload') or data.get('target')

    if not password or password != ADMIN_PASSWORD:
        return jsonify({"error": "Password non valida"}), 401

    # Azioni sui servizi
    if action == 'restart_service' and payload in CONTAINER_NAMES:
        response, status_code = run_docker_command(["docker", "restart", payload])
        return jsonify(response), status_code
    
    elif action == 'toggle_forwarder' and payload in ['start', 'stop']:
        response, status_code = run_docker_command(["docker", payload, "file_forwarder"])
        return jsonify(response), status_code

    elif action == 'clear_files':
        target_path = '/data'
        if not os.path.isdir(target_path):
            return jsonify({"error": f"La directory target '{target_path}' non esiste."}), 500
        response, status_code = run_docker_command(["find", target_path, "-type", "f", "-delete"])
        return jsonify(response), status_code

    elif action == 'get_full_logs' and payload in CONTAINER_NAMES:
        try:
            cmd = ["docker", "logs", payload]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            logs = stdout.decode('utf-8', errors='ignore') + stderr.decode('utf-8', errors='ignore')
            return jsonify({"logs": logs}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    # Azioni sugli utenti
    elif action == 'update_ftp_users':
        try:
            if payload is None:
                return jsonify({"error": "Payload mancante per l'aggiornamento degli utenti FTP"}), 400
            users = payload.get('users', [])
            
            for filename in os.listdir(FTP_USER_CONF_DIR):
                file_path = os.path.join(FTP_USER_CONF_DIR, filename)
                if os.path.isfile(file_path):
                    os.unlink(file_path)

            with open(FTP_USERS_TXT, 'w') as f:
                for user in users:
                    f.write(f"{user['username']}\n")
                    f.write(f"{user['password']}\n")
            
            for user in users:
                # Assicurati che la home directory esista
                homedir = user['homedir']
                if homedir.startswith('/home/vsftpd/'):
                    # Estrai il nome della directory dall'homedir
                    dir_name = homedir.split('/')[-1]
                    # Crea la directory se non esiste
                    os.makedirs(f"/data/{dir_name}", exist_ok=True)
                
                with open(os.path.join(FTP_USER_CONF_DIR, user['username']), 'w') as f:
                    f.write(f"local_root={user['homedir']}\n")
            
            run_docker_command(["docker", "restart", "ftp_server"])
            return jsonify({"message": "Utenti FTP aggiornati con successo."}), 200
        except Exception as e:
            return jsonify({"error": f"Errore scrittura utenti FTP: {e}"}), 500

    elif action == 'update_sftp_users':
        try:
            if payload is None:
                return jsonify({"error": "Payload mancante per l'aggiornamento degli utenti SFTP"}), 400
            users = payload.get('users', [])
            sftp_config = {"Users": []}
            for user in users:
                parts = user['homedir'].rsplit('/', 1)
                chroot_dir = parts[0] if len(parts) > 1 else f"/home/{user['username']}"
                start_path = parts[1] if len(parts) > 1 else ""
                sftp_config["Users"].append({
                    "Username": user['username'],
                    "Password": user['password'],
                    "Chroot": {"Directory": chroot_dir, "StartPath": start_path},
                    "Directories": [start_path] if start_path else []
                })
            with open(SFTP_USERS_JSON, 'w') as f:
                json.dump(sftp_config, f, indent=4)
            run_docker_command(["docker", "restart", "sftp_server"])
            return jsonify({"message": "Utenti SFTP aggiornati con successo."}), 200
        except Exception as e:
            return jsonify({"error": f"Errore scrittura utenti SFTP: {e}"}), 500

    else:
        return jsonify({"error": "Azione non valida o target non specificato"}), 400

@app.route('/api/disk-space')
def get_disk_space():
    """Restituisce informazioni sullo spazio disponibile su disco."""
    try:
        # Ottieni lo spazio disponibile per la directory /data
        total, used, free = shutil.disk_usage('/data')
        
        # Converti in GB per una visualizzazione più leggibile
        total_gb = round(total / (1024**3), 2)
        used_gb = round(used / (1024**3), 2)
        free_gb = round(free / (1024**3), 2)
        
        # Calcola la percentuale di utilizzo
        usage_percent = round((used / total) * 100, 1)
        
        return jsonify({
            "total_gb": total_gb,
            "used_gb": used_gb,
            "free_gb": free_gb,
            "usage_percent": usage_percent
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

#!/bin/sh
# forwarder.sh

# This script handles automatic file forwarding based on user-specific rules.

# --- Configuration ---
# Credentials are read from environment variables defined in docker-compose.yml
FTP_HOST="$DEST_FTP_HOST"
FTP_USER="$DEST_FTP_USER"
# FTP_PASS is intentionally not set here for security reasons.

# Local folders to monitor
FTP_USER_WATCH_DIR="/data/"
CUSTOMER1_WATCH_DIR="/data/customer1/filescma"

echo "✅ File Forwarder started with specific rules."
echo "Watching $FTP_USER_WATCH_DIR (for ftpuser)"
echo "Watching $CUSTOMER1_WATCH_DIR (for customer1)"

# --- Watcher for ftpuser (Use Case 2) ---
# Monitors ONLY the main /data/ folder (NOT recursive).
# Forwards files to the main folder of the destination server.
inotifywait -m -e create --format '%f' "$FTP_USER_WATCH_DIR" | while read FILENAME
do
  # Check if the created item is a file and is directly in /data/
  if [ -f "${FTP_USER_WATCH_DIR}${FILENAME}" ]; then
    echo "ftpuser watcher: Detected new file in root: $FILENAME. Forwarding..."
    # FTP_PASS is not used directly here for security. Set it via environment variable when running the container.
    lftp -e "set ftp:ssl-allow no; put \"${FTP_USER_WATCH_DIR}${FILENAME}\"; bye" -u "$FTP_USER,$FTP_PASS" "$FTP_HOST"
    if [ $? -eq 0 ]; then
      echo "ftpuser watcher: Successfully forwarded $FILENAME."
    else
      echo "ftpuser watcher: Error forwarding $FILENAME."
    fi
  fi
done &

# --- Watcher for customer1 (Use Case 3) ---
# Monitors the /data/customer1/filescma folder and its subfolders (recursive).
# Forwards files to the /filescma folder on the destination server.
inotifywait -r -m -e create --format '%w%f' "$CUSTOMER1_WATCH_DIR" | while read FULL_PATH
do
  # Check if the created item is a file
  if [ -f "$FULL_PATH" ]; then
    DEST_DIR="/filescma"

    echo "customer1 watcher: Detected new file: $FULL_PATH. Forwarding to $DEST_DIR..."
    # FTP_PASS is not used directly here for security. Set it via environment variable when running the container.
    lftp -e "set ftp:ssl-allow no; put -O \"$DEST_DIR/\" \"$FULL_PATH\"; bye" -u "$FTP_USER,$FTP_PASS" "$FTP_HOST"
    if [ $? -eq 0 ]; then
      echo "customer1 watcher: Successfully forwarded $FULL_PATH to $DEST_DIR."
    else
      echo "customer1 watcher: Error forwarding $FULL_PATH."
    fi
  fi
done &

# Keeps the script running to allow background processes to continue
wait
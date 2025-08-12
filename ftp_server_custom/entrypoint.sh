#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# This allows the 'vsftpd' user to create files and directories.
echo "Setting ownership of /home/vsftpd..."
chown -R vsftpd:vsftpd /home/vsftpd
echo "Ownership set."

# Define paths for the virtual user text file and the database file.
VIRTUAL_USERS_FILE="/etc/vsftpd/virtual_users.txt"
VIRTUAL_USERS_DB="/etc/vsftpd/virtual_users.db"
TEMP_USERS_FILE="/tmp/virtual_users_sanitized.txt"

# Check if the virtual users list exists before trying to create the database.
if [ -f "$VIRTUAL_USERS_FILE" ]; then
  echo "Found virtual users file. Sanitizing and creating database..."

  # Sanitize the user file by removing comments and blank lines,
  # then copy it to a temporary location inside the container.
  grep -v '^#' "$VIRTUAL_USERS_FILE" | grep -v '^$' > "$TEMP_USERS_FILE"

  # Convert the sanitized, temporary file from Windows (CRLF) to Unix (LF) line endings.
  dos2unix "$TEMP_USERS_FILE"

  # Remove the old database file if it exists to prevent corruption.
  rm -f "$VIRTUAL_USERS_DB"

  # Create the Berkeley DB file from the sanitized, temporary text file.
  db_load -T -t hash -f "$TEMP_USERS_FILE" "$VIRTUAL_USERS_DB"

  # Set secure permissions on the new database file.
  chmod 600 "$VIRTUAL_USERS_DB"

  echo "User database created successfully."
else
  echo "WARNING: Virtual users file not found at $VIRTUAL_USERS_FILE. No virtual users will be loaded."
fi

echo "Starting vsftpd server..."

# Execute the main vsftpd server process in the foreground.
exec /usr/sbin/vsftpd /etc/vsftpd/vsftpd.conf

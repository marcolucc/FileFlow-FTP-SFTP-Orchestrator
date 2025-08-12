#!/bin/bash

# ==============================================================================
# Comprehensive Test Script for FTP/SFTP Docker Compose Setup
# ==============================================================================
# This script will test the three main use cases defined in the docker-compose:
# 1. 'hlagt' FTP user with chroot and IP whitelisting.
# 2. 'ftpuser' FTP user with file forwarding from the root directory.
# 3. 'customer1' SFTP user with file forwarding from a specific directory.
#
# Requirements: lftp, sshpass, sftp
# On Debian/Ubuntu: sudo apt-get install lftp sshpass openssh-client
# On macOS (Homebrew): brew install lftp sshpass
# ==============================================================================

# --- Configuration ---
FTP_HOST="localhost"
FTP_PORT="21"
SFTP_HOST="localhost"
SFTP_PORT="2222"

# --- Test Files ---
FTPUSER_TEST_FILE="ftpuser_upload_$(date +%s).txt"
CUSTOMER1_TEST_FILE="customer1_upload_$(date +%s).txt"
HLAGT_TEST_FILE="hlagt_write_test_$(date +%s).txt"

# --- Helper Functions for Colored Output ---
print_info() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

# ==============================================================================
# TEST 1: HLAGT FTP USER (Read/Write in 'codeco', IP Whitelisted)
# ==============================================================================
print_info "--- STARTING TEST 1: User 'hlagt' ---"
print_warning "This test will only succeed if run from a whitelisted IP."

# Create a test file to upload
echo "Test content for hlagt" > "$HLAGT_TEST_FILE"

# Use lftp to connect, change directory, put a file, and list contents
lftp -u hlagt,[REMOVED] -p $FTP_PORT $FTP_HOST <<EOF
set ftp:ssl-allow no
set net:timeout 10
cd codeco
put "$HLAGT_TEST_FILE"
ls
bye
EOF

# Check the exit code of the lftp command
if [ $? -eq 0 ]; then
    print_success "User 'hlagt' successfully connected, uploaded, and listed files in '/codeco'."
    # Clean up the local test file
    rm "$HLAGT_TEST_FILE"
    # Optional: Clean up the remote file
    lftp -u hlagt,[REMOVED] -p $FTP_PORT $FTP_HOST -e "set ftp:ssl-allow no; rm /codeco/$HLAGT_TEST_FILE; bye" > /dev/null 2>&1
else
    print_error "Test for user 'hlagt' failed. This could be due to:"
    print_error "1. Not running the script from a whitelisted IP."
    print_error "2. Incorrect credentials or server configuration."
    print_error "3. The user cannot write to the '/codeco' directory."
fi
echo ""

# ==============================================================================
# TEST 2: FTPUSER (Upload to root, check forwarding)
# ==============================================================================
print_info "--- STARTING TEST 2: User 'ftpuser' with File Forwarding ---"

# Create a test file
echo "This is a test file from ftpuser." > "$FTPUSER_TEST_FILE"

# Upload the file
lftp -u ftpuser,[REMOVED] -p $FTP_PORT $FTP_HOST <<EOF
set ftp:ssl-allow no
put "$FTPUSER_TEST_FILE"
bye
EOF

if [ $? -eq 0 ]; then
    print_success "User 'ftpuser' successfully uploaded '$FTPUSER_TEST_FILE'."
    print_info "Now monitoring 'file-forwarder' logs for the upload confirmation..."
    
    # Monitor the docker logs for 15 seconds for the success message
    if docker-compose logs --since 15s file-forwarder | grep -q "Successfully uploaded $FTPUSER_TEST_FILE"; then
        print_success "File forwarder successfully processed and uploaded '$FTPUSER_TEST_FILE'."
    else
        print_error "File forwarder did NOT process '$FTPUSER_TEST_FILE'. Check 'file-forwarder' logs for errors."
    fi
else
    print_error "Failed to upload file as 'ftpuser'."
fi
# Clean up local file
rm "$FTPUSER_TEST_FILE"
echo ""

# ==============================================================================
# TEST 3: CUSTOMER1 SFTP USER (Upload to 'filescma', check forwarding)
# ==============================================================================
print_info "--- STARTING TEST 3: User 'customer1' (SFTP) with File Forwarding ---"

# Create a test file
echo "This is a test file from SFTP user customer1." > "$CUSTOMER1_TEST_FILE"

# Use sshpass with sftp to perform a non-interactive upload
# The batch file contains the 'put' command
echo "put $CUSTOMER1_TEST_FILE" > sftp_batch
sshpass -p '[REMOVED]' sftp -P $SFTP_PORT -o StrictHostKeyChecking=no -b sftp_batch customer1@$SFTP_HOST

if [ $? -eq 0 ]; then
    print_success "User 'customer1' successfully uploaded '$CUSTOMER1_TEST_FILE' via SFTP."
    print_info "Now monitoring 'file-forwarder' logs for the upload confirmation..."

    # Monitor the docker logs for 15 seconds
    if docker-compose logs --since 15s file-forwarder | grep -q "Successfully uploaded $CUSTOMER1_TEST_FILE"; then
        print_success "File forwarder successfully processed and uploaded '$CUSTOMER1_TEST_FILE'."
    else
        print_error "File forwarder did NOT process '$CUSTOMER1_TEST_FILE'. Check 'file-forwarder' logs for errors."
    fi
else
    print_error "Failed to upload file as 'customer1' via SFTP."
fi

# Clean up local files
rm "$CUSTOMER1_TEST_FILE"
rm sftp_batch
echo ""

print_info "--- ALL TESTS COMPLETED ---"


# This Dockerfile creates a custom, stable FTP server image from scratch
# using the official Debian base image. This provides maximum control and reliability.

# Use a stable, slim Debian base image.
FROM debian:bullseye-slim

# Install vsftpd, the Berkeley DB utilities, the required PAM library,
# and the dos2unix utility to fix line-ending issues with config files.
# -y: Assume yes to all prompts
# --no-install-recommends: Don't install optional packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends vsftpd db-util libpam-modules dos2unix && \
    rm -rf /var/lib/apt/lists/*

# Create the non-login system user that all virtual users will be mapped to.
# This is the user specified by 'guest_username' in vsftpd.conf.
# -r: Create a system user
# -M: Don't create a home directory (we will create it manually)
# -d /home/vsftpd: Set the home directory path
RUN useradd -r -M -d /home/vsftpd vsftpd

# Create the home directory for the vsftpd user and the directory for user configs.
# Also, ensure the vsftpd user owns its home directory.
RUN mkdir -p /home/vsftpd && \
    mkdir -p /etc/vsftpd/user_conf && \
    chown vsftpd:vsftpd /home/vsftpd

# Create the secure chroot directory that vsftpd requires to run.
# This directory must be empty and not writable by the ftp user.
RUN mkdir -p /var/run/vsftpd/empty

# Copy the new PAM authentication configuration into the system.
# This tells the server how to use our virtual user database for logins.
COPY vsftpd.pam /etc/pam.d/vsftpd

# Copy the new entrypoint script into a standard location in the image.
COPY entrypoint.sh /usr/local/bin/
# Make the entrypoint script executable so it can be run.
RUN chmod +x /usr/local/bin/entrypoint.sh

# Expose the standard FTP command port and the passive port range.
EXPOSE 21 30000-30009

# Set the entrypoint script to be executed when the container starts.
ENTRYPOINT ["entrypoint.sh"]

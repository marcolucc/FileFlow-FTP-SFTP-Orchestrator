
FROM alpine:latest

RUN apk add --no-cache lftp inotify-tools

COPY forwarder.sh /forwarder.sh

RUN chmod +x /forwarder.sh

CMD ["/forwarder.sh"]

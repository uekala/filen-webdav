# Offizielles rclone-Image (Alpine, Multi-Arch). Filen ist ab rclone 1.73 ein eigenes Backend.
ARG RCLONE_VERSION=1.76.0
FROM rclone/rclone:${RCLONE_VERSION}

# python3 + exiftool für die Fotosortierung, tzdata für die Ortszeit
RUN apk add --no-cache jq python3 exiftool tzdata

COPY run.sh fotosortierer.py onedrive.py /
RUN chmod +x /run.sh /fotosortierer.py /onedrive.py

LABEL io.hass.type="addon" \
      io.hass.name="Filen WebDAV"

ENTRYPOINT []
CMD ["/run.sh"]

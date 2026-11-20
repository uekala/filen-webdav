# Offizielles rclone-Image (Alpine, Multi-Arch). Filen ist ab rclone 1.73 ein eigenes Backend.
ARG RCLONE_VERSION=1.76.0
FROM rclone/rclone:${RCLONE_VERSION}

RUN apk add --no-cache jq

COPY run.sh /run.sh
RUN chmod +x /run.sh

LABEL io.hass.type="addon" \
      io.hass.name="Filen WebDAV"

ENTRYPOINT []
CMD ["/run.sh"]

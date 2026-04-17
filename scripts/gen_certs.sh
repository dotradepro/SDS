#!/bin/bash
# Generate self-signed TLS certificates for MQTT over TLS
set -e

CERT_DIR_REL="$(dirname "$0")/../certs"
mkdir -p "$CERT_DIR_REL"
CERT_DIR="$(cd "$CERT_DIR_REL" && pwd)"

# Skip if certs already exist
if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
    echo "Certificates already exist in $CERT_DIR, skipping generation."
    exit 0
fi

echo "Generating self-signed TLS certificates..."

# CA
openssl req -new -x509 -days 3650 -extensions v3_ca \
    -keyout "$CERT_DIR/ca.key" -out "$CERT_DIR/ca.crt" \
    -subj "/CN=SDS-CA" -nodes 2>/dev/null

# Server key
openssl genrsa -out "$CERT_DIR/server.key" 2048 2>/dev/null

# Server CSR
openssl req -new -key "$CERT_DIR/server.key" -out "$CERT_DIR/server.csr" \
    -subj "/CN=sds-mosquitto" 2>/dev/null

# Server cert
openssl x509 -req -days 3650 -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" -CAcreateserial \
    -out "$CERT_DIR/server.crt" 2>/dev/null

# Cleanup CSR
rm -f "$CERT_DIR/server.csr" "$CERT_DIR/ca.srl"

echo "Certificates generated successfully in $CERT_DIR"
echo "  CA:   $CERT_DIR/ca.crt"
echo "  Cert: $CERT_DIR/server.crt"
echo "  Key:  $CERT_DIR/server.key"

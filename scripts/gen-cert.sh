#!/usr/bin/env bash
set -euo pipefail
umask 077
cert_dir=certs
force=false
while (($#)); do
    case "$1" in
        --dir) [[ $# -ge 2 && -n $2 ]] || exit 2; cert_dir=$2; shift 2 ;;
        --force) force=true; shift ;;
        *) echo "Usage: $0 [--dir DIR] [--force]" >&2; exit 2 ;;
    esac
done
mkdir -p -- "$cert_dir"
if ! mkdir -- "$cert_dir/.gen-cert.lock" 2>/dev/null; then
    echo 'Certificate generation already locked; inspect before removing stale lock.' >&2; exit 1
fi
temp_dir=
cleanup() {
    [[ -z $temp_dir ]] || rm -rf -- "$temp_dir"
    rmdir -- "$cert_dir/.gen-cert.lock"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
if [[ -e $cert_dir/server.key || -L $cert_dir/server.key || -e $cert_dir/server.crt || -L $cert_dir/server.crt ]]; then
    if [[ $force != true ]]; then
        echo 'Certificate/key already exists; refusing overwrite. Use --force explicitly.' >&2; exit 2
    fi
fi
temp_dir=$(mktemp -d "$cert_dir/.generate.XXXXXXXX")
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -sha256 -days 30 \
    -subj '/CN=QUIC Performance Lab local demo' \
    -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1,IP:10.10.0.2' \
    -addext 'basicConstraints=critical,CA:TRUE' \
    -addext 'keyUsage=critical,digitalSignature,keyCertSign' \
    -addext 'extendedKeyUsage=serverAuth' \
    -keyout "$temp_dir/server.key" -out "$temp_dir/server.crt"
openssl verify -CAfile "$temp_dir/server.crt" -verify_hostname localhost "$temp_dir/server.crt"
mv -f -- "$temp_dir/server.key" "$cert_dir/server.key"
mv -f -- "$temp_dir/server.crt" "$cert_dir/server.crt"
echo "Created local demo certificate/key in $cert_dir (0600); SAN localhost, 127.0.0.1, 10.10.0.2"

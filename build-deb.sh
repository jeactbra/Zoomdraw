#!/bin/sh
# Gera o pacote .deb a partir de zoomdraw.py e da pasta packaging/.
# Uso: ./build-deb.sh   (a versão vem de packaging/DEBIAN/control)
set -e
cd "$(dirname "$0")"
VERSAO=$(sed -n 's/^Version: //p' packaging/DEBIAN/control)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp -a packaging/. "$TMP/"
install -D -m 755 zoomdraw.py "$TMP/usr/bin/zoomdraw"
find "$TMP" -type d -exec chmod 755 {} +
find "$TMP" -type f -exec chmod 644 {} +
chmod 755 "$TMP/DEBIAN/postinst" "$TMP/usr/bin/zoomdraw"
dpkg-deb --root-owner-group -b "$TMP" "zoomdraw_${VERSAO}_all.deb"

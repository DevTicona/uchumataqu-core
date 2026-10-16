#!/usr/bin/env bash
# ==============================================================================
# Script de inicio rápido para el Servidor Web ASR INT8
# ==============================================================================

DIR_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUERTO=8080

echo "------------------------------------------------------------------"
echo "  🎙️  INICIANDO PLATAFORMA DE PRUEBAS ASR INT8 EN TIEMPO REAL"
echo "------------------------------------------------------------------"

IP_LOCAL=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$IP_LOCAL" ]; then
  IP_LOCAL="127.0.0.1"
fi

echo "  🖥️  Acceso en PC:        http://localhost:${PUERTO}"
echo "  📱 Acceso en Celular:   http://${IP_LOCAL}:${PUERTO}"
echo "------------------------------------------------------------------"
echo "  Presiona Ctrl + C para detener el servidor."
echo "------------------------------------------------------------------"

# Liberar el puerto si ya había una instancia previa
PID_OCUPADO=$(fuser "${PUERTO}/tcp" 2>/dev/null | awk '{print $1}')
if [ -n "$PID_OCUPADO" ]; then
  echo "  ⚠️  Puerto ${PUERTO} ya estaba en uso por la instancia previa (${PID_OCUPADO}). Reiniciando..."
  fuser -k "${PUERTO}/tcp" >/dev/null 2>&1
  sleep 1
fi

python3 "${DIR_SCRIPT}/server.py" --host 0.0.0.0 --port "${PUERTO}"

#!/usr/bin/env bash
# ==============================================================================
# Script de entrada para ejecutar la siembra de Moodle UTA
# ==============================================================================
set -e

echo "[EduMonitor AI] Esperando a que Moodle LMS esté disponible..."
until php -r 'require_once("/opt/bitnami/moodle/config.php");' 2>/dev/null; do
    echo "  Moodle inicializando... esperando 5 segundos"
    sleep 5
done

echo "[EduMonitor AI] Moodle config.php detectado. Ejecutando siembra..."
php /opt/bitnami/moodle/custom_seed/seed.php

echo "[EduMonitor AI] Siembra completada con éxito."

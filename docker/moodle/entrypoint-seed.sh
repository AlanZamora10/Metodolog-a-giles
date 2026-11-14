#!/usr/bin/env bash
# ==============================================================================
# Entrypoint de Moodle UTA con siembra automática (EduMonitor AI)
#
# 1. Lanza en segundo plano la siembra idempotente (seed.php), que espera a que
#    Apache/Moodle respondan (es decir, a que termine la instalación de Bitnami).
# 2. Ejecuta el entrypoint original de Bitnami con run.sh como primer argumento,
#    condición que Bitnami exige para correr su instalación/actualización.
#
# Uso manual (contenedor ya levantado):
#   docker exec moodle_lms bash /opt/edumonitor_seed/entrypoint-seed.sh --seed-only
# ==============================================================================
set -u

SEED_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHP_BIN="$(command -v php || echo /opt/bitnami/php/bin/php)"
MOODLE_DIR="/opt/bitnami/moodle"
MOODLEDATA_DIR="/bitnami/moodledata"

# Instala/actualiza el plugin local_edumonitor (Web Service local_edumonitor_crear_tarea).
# El código de Moodle vive en el volumen persistente, así que la copia sobrevive a reinicios.
install_plugin() {
    local origen="$SEED_DIR/local_edumonitor" destino="$MOODLE_DIR/local/edumonitor"
    [[ -d "$origen" ]] || return 0
    echo "[EduMonitor AI] Instalando plugin local_edumonitor..."
    rm -rf "$destino"
    cp -r "$origen" "$destino"
    chown -R daemon:root "$destino" 2>/dev/null || true
    if "$PHP_BIN" "$MOODLE_DIR/admin/cli/upgrade.php" --non-interactive >/tmp/edumonitor_upgrade.log 2>&1; then
        echo "[EduMonitor AI] Plugin local_edumonitor instalado/actualizado."
    else
        echo "[EduMonitor AI] ERROR al instalar local_edumonitor:"; tail -20 /tmp/edumonitor_upgrade.log
    fi
    chown -R daemon:root "$MOODLEDATA_DIR" 2>/dev/null || true
}

run_seed() {
    echo "[EduMonitor AI] Esperando a que Moodle LMS responda en el puerto 8080..."
    until "$PHP_BIN" -r 'exit(@file_get_contents("http://127.0.0.1:8080/login/index.php") === false ? 1 : 0);' 2>/dev/null; do
        sleep 5
    done

    install_plugin

    echo "[EduMonitor AI] Moodle disponible. Ejecutando siembra idempotente..."
    if "$PHP_BIN" "$SEED_DIR/seed.php"; then
        echo "[EduMonitor AI] Siembra completada con éxito."
    else
        echo "[EduMonitor AI] ERROR: la siembra falló (ver salida anterior)."
    fi

    # La siembra corre como root: devolver cachés y archivos al usuario de Apache.
    chown -R daemon:root "$MOODLEDATA_DIR" 2>/dev/null || true
    "$PHP_BIN" "$MOODLE_DIR/admin/cli/purge_caches.php" >/dev/null 2>&1 || true
    chown -R daemon:root "$MOODLEDATA_DIR" 2>/dev/null || true
}

if [[ "${1:-}" == "--seed-only" ]]; then
    run_seed
    exit 0
fi

run_seed &

exec /opt/bitnami/scripts/moodle/entrypoint.sh /opt/bitnami/scripts/moodle/run.sh

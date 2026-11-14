<?php
/**
 * Aplica (o reaplica) la identidad visual UTA · FISEI a Moodle UTA SIN re-sembrar datos:
 *   - CSS institucional (tema_uta.css) en $CFG->additionalhtmlhead: login con tarjeta institucional y
 *     fondo geométrico, barra superior azul UTA y estilos de curso.
 *   - Purga de cachés para que el cambio se vea de inmediato.
 * No toca cursos, usuarios, calificaciones ni las tareas de refuerzo publicadas.
 *
 * Uso (contenedor levantado):
 *   docker exec moodle_lms bash /opt/edumonitor_seed/entrypoint-seed.sh --tema-only
 * seed.php reutiliza edumonitor_css_tema_uta() en instalaciones nuevas.
 */

if (!function_exists('edumonitor_css_tema_uta')) {
    /** Bloque <style> listo para additionalhtmlhead. */
    function edumonitor_css_tema_uta(): string {
        $css = file_get_contents(__DIR__ . '/tema_uta.css');
        if ($css === false) {
            throw new RuntimeException('No se pudo leer tema_uta.css');
        }
        return "<style id=\"uta-theme\">\n" . trim($css) . "\n</style>";
    }
}

// Ejecución directa por CLI (no cuando seed.php lo incluye)
if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === realpath(__FILE__)) {
    define('CLI_SCRIPT', true);
    foreach (['/opt/bitnami/moodle/config.php', '/var/www/html/config.php', __DIR__ . '/../../config.php'] as $path) {
        if (file_exists($path)) {
            require_once($path);
            break;
        }
    }
    if (!isset($CFG)) {
        echo "[ERROR] No se pudo localizar config.php de Moodle.\n";
        exit(1);
    }
    set_config('additionalhtmlhead', edumonitor_css_tema_uta());
    purge_all_caches();
    echo "[EduMonitor AI] Identidad visual UTA · FISEI aplicada (login, barra superior y cursos).\n";
}

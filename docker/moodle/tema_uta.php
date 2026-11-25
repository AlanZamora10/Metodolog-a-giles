<?php
/**
 * Aplica (o reaplica) la identidad visual UTA · FISEI a Moodle UTA SIN re-sembrar datos:
 *   - CSS institucional (tema_uta.css) en $CFG->additionalhtmlhead: login con tarjeta institucional y
 *     fondo geométrico, barra superior azul UTA y estilos de curso.
 *   - Script del acceso con el flujo «Microsoft Office 365» (tema_uta_login.js): mejora progresiva del
 *     formulario nativo de Moodle (no cambia #login, #username, #password ni #loginbtn).
 *   - Purga de cachés para que el cambio se vea de inmediato.
 * No toca cursos, usuarios, calificaciones ni las tareas de refuerzo publicadas.
 *
 * Uso (contenedor levantado):
 *   docker exec moodle_lms bash /opt/edumonitor_seed/entrypoint-seed.sh --tema-only
 * seed.php reutiliza edumonitor_css_tema_uta() en instalaciones nuevas.
 */

if (!function_exists('edumonitor_fondo_login')) {
    /**
     * Fondo opcional del login: si existe docker/moodle/login-bg/login-bg.(jpg|jpeg|png|webp), se copia a
     * local/edumonitor/pix/ (servido por Apache) y se devuelve el CSS que lo usa SÓLO en /login/index.php,
     * con un velo azul UTA para que la tarjeta institucional blanca conserve el contraste.
     * Sin imagen, se eliminan copias anteriores y el login conserva su fondo geométrico actual.
     */
    function edumonitor_fondo_login(): string {
        global $CFG;
        if (empty($CFG->dirroot)) {
            return '';
        }
        $destino = $CFG->dirroot . '/local/edumonitor/pix';
        foreach (glob($destino . '/login-bg.*') ?: [] as $anterior) {
            @unlink($anterior);
        }
        foreach (['jpg', 'jpeg', 'png', 'webp'] as $ext) {
            $origen = __DIR__ . "/login-bg/login-bg.$ext";
            if (!is_file($origen)) {
                continue;
            }
            if (!is_dir($destino)) {
                @mkdir($destino, 0755, true);
            }
            if (!@copy($origen, "$destino/login-bg.$ext")) {
                return '';
            }
            @chmod("$destino/login-bg.$ext", 0644);
            $url = "/local/edumonitor/pix/login-bg.$ext?v=" . substr(md5_file($origen), 0, 10);
            return "\n/* Fondo personalizado del login (docker/moodle/login-bg/) */\n"
                . "body#page-login-index {\n"
                . "  background-color: #0B2A5B !important;\n"
                . "  background-image: linear-gradient(160deg, rgba(8, 28, 70, .78) 0%, rgba(11, 42, 91, .55) 55%, "
                . "rgba(6, 18, 48, .72) 100%), url(\"$url\") !important;\n"
                . "  background-size: cover !important; background-position: center !important;\n"
                . "  background-repeat: no-repeat !important; background-attachment: fixed !important;\n"
                . "}\n"
                . "#page-login-index .login-container { box-shadow: 0 30px 80px rgba(0, 0, 0, .35), 0 2px 8px rgba(0, 0, 0, .12) !important; }\n"
                . "#page-login-index #page-footer, #page-login-index #page-footer a { color: rgba(255, 255, 255, .85) !important; }\n";
        }
        return '';
    }
}

if (!function_exists('edumonitor_css_tema_uta')) {
    /** Bloques <style> y <script> listos para additionalhtmlhead. */
    function edumonitor_css_tema_uta(): string {
        $css = file_get_contents(__DIR__ . '/tema_uta.css');
        $js = file_get_contents(__DIR__ . '/tema_uta_login.js');
        if ($css === false || $js === false) {
            throw new RuntimeException('No se pudo leer tema_uta.css o tema_uta_login.js');
        }
        return "<style id=\"uta-theme\">\n" . trim($css) . "\n" . edumonitor_fondo_login() . "</style>\n"
            . "<script id=\"uta-login-o365\">\n" . trim($js) . "\n</script>";
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
    echo "[EduMonitor AI] Identidad visual UTA · FISEI aplicada (login Microsoft Office 365, barra superior y cursos).\n";
}

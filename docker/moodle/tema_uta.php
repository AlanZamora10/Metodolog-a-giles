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

if (!function_exists('edumonitor_color_borde')) {
    /** Color hexadecimal del borde de la imagen (esquina superior izquierda); #3B0D11 si GD no está disponible. */
    function edumonitor_color_borde(string $archivo): string {
        $defecto = '#3B0D11';
        if (!function_exists('imagecreatefromstring')) {
            return $defecto;
        }
        $img = @imagecreatefromstring((string) @file_get_contents($archivo));
        if (!$img) {
            return $defecto;
        }
        $c = imagecolorsforindex($img, imagecolorat($img, 2, 2));
        imagedestroy($img);
        return sprintf('#%02X%02X%02X', $c['red'], $c['green'], $c['blue']);
    }
}

if (!function_exists('edumonitor_fondo_login')) {
    /**
     * Fondo opcional del login: si existe docker/moodle/login-bg/login-bg.(jpg|jpeg|png|webp), se copia a
     * local/edumonitor/pix/ (servido por Apache) y se devuelve el CSS que lo usa SÓLO en /login/index.php,
     * completa, nítida y sin velos; la tarjeta institucional blanca destaca con su sombra.
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
            $relleno = edumonitor_color_borde($origen);
            // Imagen completa y nítida (contain, centrada, sin velos ni filtros); las bandas libres se rellenan
            // con el color del borde de la propia imagen para que el encuadre se vea continuo.
            return "\n/* Fondo personalizado del login (docker/moodle/login-bg/) */\n"
                . "body#page-login-index {\n"
                . "  background-color: $relleno !important;\n"
                . "  background-image: url(\"$url\") !important;\n"
                . "  background-size: contain !important;\n"
                // En portátiles (1280–1700 px) la imagen se escala a 1720 px de ancho para que la tarjeta quepa en
                // el espacio central y no tape los textos laterales; en pantallas mayores equivale a contain.
                . "  background-size: max(100%, 1720px) auto !important; background-position: center center !important;\n"
                . "  background-repeat: no-repeat !important; background-attachment: fixed !important;\n"
                . "  filter: none !important; backdrop-filter: none !important;\n"
                . "}\n"
                . "#page-login-index .login-container { box-shadow: 0 24px 60px rgba(0, 0, 0, .28), 0 2px 6px rgba(0, 0, 0, .10) !important; }\n"
                . "#page-login-index #page-footer, #page-login-index #page-footer a { color: rgba(255, 255, 255, .9) !important; }\n"
                // Paleta armonizada con el fondo institucional: carmesí UTA en la barra de la tarjeta y el botón Acceder
                . "body#page-login-index { border-top-color: #731419 !important; }\n"
                . "#page-login-index .login-container { border-left-color: #E2E8F0 !important; border-right-color: #E2E8F0 !important; border-bottom-color: #E2E8F0 !important; border-top-color: #8F1A20 !important; }\n"
                . "#page-login-index #loginbtn { background: #8F1A20 !important; border-color: #8F1A20 !important; }\n"
                . "#page-login-index #loginbtn:hover, #page-login-index #loginbtn:focus { background: #731419 !important; border-color: #731419 !important; }\n"
                . "#page-login-index .login-form-forgotpassword a { color: #8F1A20 !important; }\n"
                . "#page-login-index .login-form .form-control { background: #FFFFFF; border-color: #D9DEE5; }\n"
                . "#page-login-index .login-form .form-control:focus { border-color: #8F1A20 !important; box-shadow: 0 0 0 .2rem rgba(143, 26, 32, .15) !important; }\n";
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

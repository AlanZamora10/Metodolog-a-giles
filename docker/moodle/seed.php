<?php
/**
 * Siembra idempotente de Moodle UTA (FISEI) para EduMonitor AI.
 *
 *  1. Sitio "Moodle UTA" en español, inicio en "Mis cursos" e identidad visual UTA (CSS en additionalhtmlhead).
 *  2. Categorías FISEI -> SOFTWARE -> Julio a Diciembre 2026.
 *  3. Usuarios: admin, docente titular (rgomez) y 20 estudiantes con nombres ficticios.
 *  4. 4 cursos con nóminas distintas (7 / 10 / 12 / 15 estudiantes); el docente es editingteacher en todos.
 *  5. Estructura del aula virtual UTA: Informativo | Primer Parcial | Segundo Parcial | Supletorio, con
 *     Zona de información, ACD (40%), Tareas (30%) y PAE (30%) por parcial.
 *     Las fechas se calculan desde el día de ejecución: Primer Parcial cerrado (vencimientos en las últimas
 *     semanas, con entregas y notas) y Segundo Parcial en curso (vencimientos en las próximas semanas).
 *  6. Libro de calificaciones ponderado 40/30/30 y notas variadas del Primer Parcial
 *     (aceptables, en riesgo, críticos, nota 0, SIN ENTREGA y PENDIENTE).
 *  7. Web Services REST, servicio EduMonitor_WS y token de integración.
 *
 * Re-ejecutable en cualquier momento: crea lo que falta, actualiza lo existente y
 * desmatricula a los estudiantes que ya no pertenecen a la nómina de un curso.
 */

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

require_once($CFG->libdir . '/clilib.php');
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->dirroot . '/user/lib.php');
require_once($CFG->libdir . '/enrollib.php');
require_once($CFG->libdir . '/gradelib.php');
require_once($CFG->libdir . '/grade/grade_item.php');
require_once($CFG->libdir . '/grade/grade_category.php');
require_once($CFG->dirroot . '/mod/assign/locallib.php');
require_once($CFG->dirroot . '/mod/forum/lib.php');
require_once($CFG->dirroot . '/lib/phpunit/classes/util.php'); // Generadores de datos (igual que tool_generator)

global $DB, $CFG, $USER;

$admin = get_admin();
\core\session\manager::set_user($admin); // Los generadores y el API de assign requieren un usuario actual
$gen = phpunit_util::get_data_generator();

function out($msg) { echo $msg . "\n"; }

echo "====================================================================\n";
echo " SIEMBRA MOODLE UTA (FISEI) - EduMonitor AI\n";
echo "====================================================================\n";

// =============================================================================
// 1. SITIO, IDIOMA E IDENTIDAD VISUAL
// =============================================================================
out("[1/7] Sitio, idioma e identidad visual UTA...");
set_config('sitename', 'Moodle UTA');
set_config('lang', 'es');
$DB->set_field('user', 'lang', 'es', ['id' => $admin->id]); // Bitnami crea el admin con idioma 'en'
set_config('defaulthomepage', defined('HOMEPAGE_MYCOURSES') ? HOMEPAGE_MYCOURSES : 3);
// Hora de Ecuador para todos: los vencimientos se muestran a las 23:59 locales
set_config('timezone', 'America/Guayaquil');
set_config('forcetimezone', 'America/Guayaquil');

$site = get_site();
$site->fullname = 'Moodle UTA';
$site->shortname = 'Moodle UTA';
$DB->update_record('course', $site);

if (!array_key_exists('es', get_string_manager()->get_list_of_translations(true))) {
    try {
        (new \tool_langimport\controller())->install_languagepacks('es');
        out("  + Paquete de idioma 'es' instalado");
    } catch (Throwable $e) {
        out("  ! No se pudo instalar el paquete 'es': " . $e->getMessage());
    }
}

$uta_css = <<<'CSS'
<style id="uta-theme">
/* ---- Identidad visual UTA (sistemaseducaciononline.uta.edu.ec) ---- */
:root { --uta-blue:#11297A; --uta-line:#DEE2E6; }
body { background:#F4F6F8; }
/* Barra superior blanca con filete azul institucional */
.navbar.fixed-top { background:#FFFFFF !important; border-top:3px solid var(--uta-blue); border-bottom:1px solid var(--uta-line); box-shadow:none !important; }
.navbar.fixed-top .navbar-brand, .navbar.fixed-top .primary-navigation .nav-link { color:var(--uta-blue) !important; font-weight:500; }
.navbar.fixed-top .primary-navigation .nav-link.active { border-bottom-color:var(--uta-blue) !important; font-weight:600; }
/* Navegación secundaria del curso: pestañas sobrias con subrayado azul */
.secondary-navigation { border-bottom:1px solid var(--uta-line); margin-bottom:1.25rem; }
.secondary-navigation .nav-tabs { border-bottom:0; }
.secondary-navigation .nav-tabs .nav-link,
.secondary-navigation .moremenu .dropdown-toggle { color:#495057 !important; border:0 !important; background:transparent; }
.secondary-navigation .nav-tabs .nav-link:hover { color:var(--uta-blue) !important; }
.secondary-navigation .nav-tabs .nav-link.active { color:var(--uta-blue) !important; font-weight:600; border-bottom:2px solid var(--uta-blue) !important; background:transparent !important; }
/* Encabezado de página */
#page-header h1, .page-header-headings h1 { color:var(--uta-blue); }
/* Secciones del curso como tarjetas blancas */
.course-content ul.topics > li.section, .course-content li.section.main {
  background:#FFFFFF; border:1px solid var(--uta-line) !important; border-radius:8px;
  padding:1rem 1.25rem !important; margin-bottom:1rem;
}
.course-content .sectionname, .course-content .sectionname a, .course-section-header h3 a { color:var(--uta-blue) !important; font-weight:700; }
/* Encabezados de bloque (etiquetas) e iconos de actividad */
.activity.label .uta-block-title { color:var(--uta-blue); border-left:3px solid var(--uta-blue); padding:.35rem .75rem; margin:.5rem 0 0; font-size:1.05rem; font-weight:700; background:#F8F9FB; }
.block .card-title, .block h5 { color:var(--uta-blue); }
.card, .block.card { border-color:var(--uta-line); }
.btn-primary { background-color:var(--uta-blue); border-color:var(--uta-blue); }
.btn-primary:hover { background-color:#0C1F5E; border-color:#0C1F5E; }
a { color:var(--uta-blue); }
</style>
CSS;
set_config('additionalhtmlhead', $uta_css);
out("  -> 'Moodle UTA', idioma 'es', inicio en Mis cursos, CSS institucional aplicado");

// =============================================================================
// 2. CATEGORÍAS
// =============================================================================
out("[2/7] Jerarquía de categorías...");
function get_or_create_category($name, $idnumber, $parent = 0) {
    global $DB;
    $cat = $DB->get_record('course_categories', ['idnumber' => $idnumber])
        ?: $DB->get_record('course_categories', ['name' => $name, 'parent' => $parent]);
    if ($cat) {
        return $cat->id;
    }
    $created = core_course_category::create((object)[
        'name' => $name, 'idnumber' => $idnumber, 'parent' => $parent,
        'description' => "Categoría académica $name", 'descriptionformat' => FORMAT_HTML,
    ]);
    out("  + Categoría creada: $name");
    return $created->id;
}
$cat_fisei = get_or_create_category('FISEI', 'CAT_FISEI');
$cat_sof = get_or_create_category('SOFTWARE', 'CAT_SOFTWARE', $cat_fisei);
$cat_period = get_or_create_category('Julio a Diciembre 2026', 'CAT_2026_JD', $cat_sof);

// =============================================================================
// 3. USUARIOS
// =============================================================================
out("[3/7] Usuarios (docente titular y 20 estudiantes)...");

/** Busca por idnumber, username o email y sincroniza todos los campos (incluida la contraseña). */
function upsert_user($username, $firstname, $lastname, $email, $idnumber, $password) {
    global $DB, $CFG;
    $base = ['mnethostid' => $CFG->mnet_localhost_id, 'deleted' => 0];
    $user = $DB->get_record('user', $base + ['idnumber' => $idnumber])
        ?: $DB->get_record('user', $base + ['username' => $username])
        ?: $DB->get_record('user', $base + ['email' => $email]);

    $data = [
        'username' => $username, 'firstname' => $firstname, 'lastname' => $lastname,
        'email' => $email, 'idnumber' => $idnumber, 'auth' => 'manual', 'confirmed' => 1,
        'lang' => 'es', 'city' => 'Ambato', 'country' => 'EC', 'institution' => 'Universidad Técnica de Ambato',
        'department' => 'FISEI - Software', 'timemodified' => time(),
    ];
    if ($user) {
        $data['id'] = $user->id;
        $DB->update_record('user', (object)$data);
        $user = $DB->get_record('user', ['id' => $user->id]);
    } else {
        $data += ['mnethostid' => $CFG->mnet_localhost_id, 'timecreated' => time(), 'password' => ''];
        $user = $DB->get_record('user', ['id' => $DB->insert_record('user', (object)$data)]);
        out("  + Usuario creado: $username ($firstname $lastname)");
    }
    update_internal_user_password($user, $password);
    return $user;
}

const DOCENTE_NOMBRE = 'Ing. Roberto Gómez';
$docente = upsert_user('rgomez', 'Ing. Roberto', 'Gómez', 'docente@uta.edu.ec', 'U-01', 'Docente2026!');
out("  = Docente titular: rgomez (" . DOCENTE_NOMBRE . ")");

// idnumber => [username, nombres, apellidos]
$students_def = [
    'U-03' => ['candrade',    'Camila',      'Andrade'],
    'U-04' => ['dcurillo',    'Diego',       'Curillo'],
    'U-05' => ['mparedes',    'Mateo',       'Paredes'],
    'U-06' => ['svillacis',   'Sofía',       'Villacís'],
    'U-07' => ['cmena',       'Carlos',      'Mena'],
    'U-08' => ['vortiz',      'Valeria',     'Ortiz'],
    'U-09' => ['asalazar',    'Andrés',      'Salazar'],
    'U-10' => ['gviteri',     'Gabriela',    'Viteri'],
    'U-11' => ['sromero',     'Sebastián',   'Romero'],
    'U-12' => ['despinoza',   'Daniela',     'Espinoza'],
    'U-13' => ['jchicaiza',   'Joel',        'Chicaiza'],
    'U-14' => ['mlozada',     'María José',  'Lozada'],
    'U-15' => ['ktoapanta',   'Kevin',       'Toapanta'],
    'U-16' => ['pguaman',     'Paula',       'Guamán'],
    'U-17' => ['rsanchez',    'Ricardo',     'Sánchez'],
    'U-18' => ['nbarrera',    'Nicole',      'Barrera'],
    'U-19' => ['jpilco',      'Jonathan',    'Pilco'],
    'U-20' => ['faltamirano', 'Fernanda',    'Altamirano'],
    'U-21' => ['bjacome',     'Bryan',       'Jácome'],
    'U-22' => ['acevallos',   'Alejandra',   'Cevallos'],
];
$students = [];
foreach ($students_def as $idn => [$uname, $fn, $ln]) {
    $students[$idn] = upsert_user($uname, $fn, $ln, "$uname@uta.edu.ec", $idn, 'Estudiante2026!');
}
out("  = " . count($students) . " estudiantes sincronizados (contraseña Estudiante2026!)");

// =============================================================================
// 4. CURSOS Y NÓMINAS
// =============================================================================
out("[4/7] Cursos y nóminas por asignatura...");

// Nómina por curso: idnumber => nota base del Primer Parcial (perfil académico del estudiante en esa materia)
$courses_def = [
    'SOF-POO-A' => [
        'fullname' => '(SOF) PROGRAMACION ORIENTADA A OBJETOS - A',
        'summary'  => 'Programación Orientada a Objetos - Paralelo A',
        'roster'   => ['U-03' => 8.6, 'U-04' => 3.4, 'U-05' => 7.2, 'U-06' => 6.0, 'U-07' => 9.1, 'U-08' => 4.5, 'U-09' => 7.8],
    ],
    'SOF-ED-B' => [
        'fullname' => '(SOF) ESTRUCTURA DE DATOS - B',
        'summary'  => 'Estructura de Datos - Paralelo B',
        'roster'   => ['U-03' => 7.9, 'U-04' => 4.2, 'U-08' => 5.6, 'U-10' => 8.8, 'U-11' => 6.4,
                       'U-12' => 9.3, 'U-13' => 3.1, 'U-14' => 7.1, 'U-15' => 5.2, 'U-16' => 8.2],
    ],
    'SOF-MA-B' => [
        'fullname' => '(SOF) METODOLOGIAS AGILES - B',
        'summary'  => 'Metodologías Ágiles de Desarrollo de Software - Paralelo B',
        'roster'   => ['U-04' => 4.8, 'U-05' => 6.6, 'U-06' => 8.4, 'U-09' => 7.5, 'U-11' => 5.9, 'U-13' => 4.1,
                       'U-15' => 7.0, 'U-17' => 9.0, 'U-18' => 6.3, 'U-19' => 8.1, 'U-20' => 2.9, 'U-21' => 7.7],
    ],
    'SOF-MCS-A' => [
        'fullname' => '(SOF) MANEJO Y CONFIGURACION DEL SOFTWARE - A',
        'summary'  => 'Manejo y Configuración del Software - Paralelo A',
        'roster'   => ['U-03' => 8.0, 'U-04' => 3.8, 'U-05' => 7.3, 'U-07' => 8.9, 'U-08' => 5.4,
                       'U-10' => 9.2, 'U-12' => 7.6, 'U-14' => 6.8, 'U-16' => 4.4, 'U-17' => 8.5,
                       'U-18' => 5.8, 'U-19' => 7.9, 'U-20' => 6.1, 'U-21' => 3.5, 'U-22' => 9.4],
    ],
];

$role_teacher = $DB->get_record('role', ['shortname' => 'editingteacher'], '*', MUST_EXIST);
$role_student = $DB->get_record('role', ['shortname' => 'student'], '*', MUST_EXIST);
$manual = enrol_get_plugin('manual');

$courses = [];
foreach ($courses_def as $short => $def) {
    $course = $DB->get_record('course', ['shortname' => $short]) ?: $DB->get_record('course', ['idnumber' => $short]);
    if (!$course) {
        $course = create_course((object)[
            'category' => $cat_period, 'fullname' => $def['fullname'], 'shortname' => $short, 'idnumber' => $short,
            'summary' => $def['summary'], 'format' => 'topics', 'numsections' => 3, 'visible' => 1,
            'startdate' => strtotime('2026-07-01'),
        ]);
        out("  + Curso creado: {$def['fullname']}");
    }
    $courses[$short] = $course;

    enrol_try_internal_enrol($course->id, $docente->id, $role_teacher->id);
    foreach (array_keys($def['roster']) as $idn) {
        enrol_try_internal_enrol($course->id, $students[$idn]->id, $role_student->id);
    }

    // Desmatricular estudiantes que no pertenecen a la nómina de este curso
    $instance = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual'], '*', MUST_EXIST);
    $sql = "SELECT u.id, u.idnumber FROM {user_enrolments} ue JOIN {user} u ON u.id = ue.userid WHERE ue.enrolid = ?";
    foreach ($DB->get_records_sql($sql, [$instance->id]) as $u) {
        if ($u->id != $docente->id && preg_match('/^U-\d+$/', (string)$u->idnumber) && !isset($def['roster'][$u->idnumber])) {
            $manual->unenrol_user($instance, $u->id);
        }
    }
    // Usuarios de siembras anteriores (Estudiante A..G) que ya no existen en la definición
    $sql = "SELECT u.id FROM {user_enrolments} ue JOIN {user} u ON u.id = ue.userid
             WHERE ue.enrolid = ? AND " . $DB->sql_like('u.username', '?');
    foreach ($DB->get_records_sql($sql, [$instance->id, 'estudiante\_%']) as $u) {
        $manual->unenrol_user($instance, $u->id);
    }
    out("  = $short: docente + " . count($def['roster']) . " estudiantes");
}

// =============================================================================
// 5. ESTRUCTURA DEL AULA VIRTUAL
// =============================================================================
out("[5/7] Estructura de secciones, bloques y actividades...");

/** Genera un PDF mínimo válido (una página) para los recursos de lectura. */
function seed_pdf($title, array $lines) {
    $esc = function ($s) {
        $s = mb_convert_encoding($s, 'Windows-1252', 'UTF-8');
        return str_replace(['\\', '(', ')'], ['\\\\', '\\(', '\\)'], $s);
    };
    $content = "BT /F1 16 Tf 60 780 Td (" . $esc($title) . ") Tj ET\n";
    $y = 745;
    foreach ($lines as $line) {
        $content .= "BT /F1 11 Tf 60 $y Td (" . $esc($line) . ") Tj ET\n";
        $y -= 18;
    }
    $objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        "<< /Length " . strlen($content) . " >>\nstream\n" . $content . "endstream",
    ];
    $pdf = "%PDF-1.4\n";
    $offsets = [];
    foreach ($objs as $i => $obj) {
        $offsets[] = strlen($pdf);
        $pdf .= ($i + 1) . " 0 obj\n$obj\nendobj\n";
    }
    $xref = strlen($pdf);
    $pdf .= "xref\n0 " . (count($objs) + 1) . "\n0000000000 65535 f \n";
    foreach ($offsets as $off) {
        $pdf .= sprintf("%010d 00000 n \n", $off);
    }
    return $pdf . "trailer\n<< /Size " . (count($objs) + 1) . " /Root 1 0 R >>\nstartxref\n$xref\n%%EOF\n";
}

/** Crea un módulo si no existe uno con ese idnumber en el curso. Devuelve el course_module. */
function ensure_module($course, $section, $modname, $idnumber, array $fields) {
    global $DB, $gen, $USER;
    $cm = $DB->get_record('course_modules', ['course' => $course->id, 'idnumber' => $idnumber]);
    if ($cm) {
        return $cm;
    }
    $record = ['course' => $course->id, 'section' => $section, 'idnumber' => $idnumber] + $fields;
    if ($modname === 'resource') {
        $draft = file_get_unused_draft_itemid();
        get_file_storage()->create_file_from_string([
            'contextid' => context_user::instance($USER->id)->id, 'component' => 'user', 'filearea' => 'draft',
            'itemid' => $draft, 'filepath' => '/', 'filename' => $fields['filename'],
        ], seed_pdf($fields['name'], $fields['lines']));
        unset($record['filename'], $record['lines']);
        $record['files'] = $draft;
    }
    $instance = $gen->create_module($modname, $record);
    return $DB->get_record('course_modules', ['id' => $instance->cmid]);
}

function block_label($course, $section, $key, $title, $subtitle = '') {
    $html = '<h4 class="uta-block-title">' . s($title) . '</h4>' . ($subtitle ? '<p>' . s($subtitle) . '</p>' : '');
    ensure_module($course, $section, 'label', "LBL-$key", ['intro' => $html, 'introformat' => FORMAT_HTML]);
}

/** Fechas de una tarea: abre 14 días antes del vencimiento y se califica hasta 7 días después. */
function assign_dates($duedate) {
    return ['duedate' => $duedate, 'allowsubmissionsfromdate' => $duedate - 14 * DAYSECS,
            'gradingduedate' => $duedate + 7 * DAYSECS, 'cutoffdate' => 0];
}

function assign_fields($name, $intro, $duedate, $files) {
    return assign_dates($duedate) + [
        'name' => $name, 'intro' => "<p>$intro</p>", 'introformat' => FORMAT_HTML, 'grade' => 10,
        'assignsubmission_file_enabled' => $files ? 1 : 0, 'assignsubmission_file_maxfiles' => 5,
        'assignsubmission_file_maxsizebytes' => 10485760, 'assignsubmission_file_filetypes' => '',
        'assignsubmission_onlinetext_enabled' => $files ? 1 : 0, 'assignsubmission_onlinetext_wordlimit' => 0,
        'assignfeedback_comments_enabled' => 1, 'submissiondrafts' => 0,
    ];
}

/** Crea la tarea si falta y, si ya existe, alinea sus fechas (y eventos de calendario) con las actuales. */
function ensure_assign($course, $section, $idnumber, $name, $intro, $duedate, $files) {
    global $DB;
    $cm = ensure_module($course, $section, 'assign', $idnumber, assign_fields($name, $intro, $duedate, $files));
    $dates = assign_dates($duedate);
    $current = $DB->get_record('assign', ['id' => $cm->instance], implode(',', array_keys($dates)), MUST_EXIST);
    if (array_map('intval', (array)$current) != $dates) {
        $DB->update_record('assign', (object)(['id' => $cm->instance, 'timemodified' => time()] + $dates));
        $cminfo = get_coursemodule_from_id('assign', $cm->id, $course->id, false, MUST_EXIST);
        (new assign(context_module::instance($cm->id), $cminfo, $course))->update_calendar($cm->id);
    }
    return $cm;
}

/** Reemplaza el PDF de un recurso existente (p. ej. el sílabo cuando cambia el docente). */
function refresh_resource_pdf($cm, $filename, $title, array $lines) {
    $fs = get_file_storage();
    $context = context_module::instance($cm->id);
    $content = seed_pdf($title, $lines);
    $files = $fs->get_area_files($context->id, 'mod_resource', 'content', 0, 'id', false);
    $file = reset($files);
    if ($file && $file->get_filename() === $filename && $file->get_contenthash() === sha1($content)) {
        return;
    }
    $fs->delete_area_files($context->id, 'mod_resource', 'content');
    $fs->create_file_from_string(['contextid' => $context->id, 'component' => 'mod_resource', 'filearea' => 'content',
        'itemid' => 0, 'filepath' => '/', 'filename' => $filename, 'sortorder' => 1], $content);
}

// Calendario relativo al día de ejecución (23:59, hora de Ecuador): el Primer Parcial ya terminó
// (vencimientos en las últimas semanas) y el Segundo Parcial está en curso (vencimientos en las próximas).
$hoy = usergetmidnight(time(), 'America/Guayaquil') + DAYSECS - MINSECS;

// Plan de actividades por parcial: [sección, unidades, ACD, Tareas, PAE]
$parciales = [
    1 => ['nombre' => 'Primer Parcial', 'unidades' => [1, 2], 'cerrado' => true,
          'acd' => ['U1-A1' => 'Evaluación Unidad 1', 'U2-A2' => 'Evaluación Unidad 2'],
          'tareas' => ['U1-T1' => 'Tarea 1: Investigación de conceptos', 'U1-T2' => 'Tarea 2: Taller práctico',
                       'U2-T3' => 'Tarea 3: Ejercicios aplicados', 'U2-T4' => 'Tarea 4: Informe de laboratorio'],
          'pae' => ['U1-P1' => 'Práctica 1: Laboratorio guiado', 'U1-P2' => 'Práctica 2: Caso de estudio',
                    'U2-P3' => 'Práctica 3: Proyecto integrador (avance)']],
    2 => ['nombre' => 'Segundo Parcial', 'unidades' => [3, 4], 'cerrado' => false,
          'acd' => ['U3-A3' => 'Evaluación Unidad 3', 'U4-A4' => 'Evaluación Unidad 4'],
          'tareas' => ['U3-T5' => 'Tarea 5: Investigación aplicada', 'U3-T6' => 'Tarea 6: Taller de refuerzo',
                       'U4-T7' => 'Tarea 7: Resolución de problemas', 'U4-T8' => 'Tarea 8: Informe final'],
          'pae' => ['U3-P4' => 'Práctica 4: Laboratorio avanzado', 'U3-P5' => 'Práctica 5: Simulación',
                    'U4-P6' => 'Práctica 6: Proyecto integrador (entrega final)']],
];

$section_names = [0 => 'Informativo', 1 => 'Primer Parcial', 2 => 'Segundo Parcial', 3 => 'Supletorio'];

foreach ($courses as $short => $course) {
    // Exactamente 4 secciones: 0..3
    course_create_sections_if_missing($course, array_keys($section_names));
    $maxsection = (int)$DB->get_field_sql('SELECT MAX(section) FROM {course_sections} WHERE course = ?', [$course->id]);
    for ($s = $maxsection; $s > 3; $s--) {
        course_delete_section($course, $s, true);
    }
    foreach ($section_names as $num => $name) {
        $section = $DB->get_record('course_sections', ['course' => $course->id, 'section' => $num]);
        course_update_section($course, $section, ['name' => $name]);
    }

    // --- Sección 0: Informativo
    $news = forum_get_course_forum($course->id, 'news');
    if (!$DB->record_exists('forum_discussions', ['forum' => $news->id, 'name' => 'Bienvenida al curso'])) {
        $gen->get_plugin_generator('mod_forum')->create_discussion([
            'course' => $course->id, 'forum' => $news->id, 'userid' => $docente->id, 'name' => 'Bienvenida al curso',
            'message' => '<p>Estimados estudiantes, bienvenidos a ' . s($course->fullname) .
                         '. Revisen el sílabo y el programa analítico en la sección Informativo.</p>',
        ]);
    }
    block_label($course, 0, 'S0-AVISOS', 'Avisos importantes',
        'Horario de tutorías: martes y jueves de 14:00 a 15:00. Revise el foro de novedades semanalmente.');
    $silabo = [
        'name' => 'Sílabo de la asignatura', 'filename' => 'Silabo_' . $short . '.pdf',
        'lines' => [$course->fullname, 'Período académico: Julio - Diciembre 2026', 'Docente: ' . DOCENTE_NOMBRE,
                    'Ponderación: ACD 40% | Tareas 30% | PAE 30%'],
    ];
    $cm_silabo = ensure_module($course, 0, 'resource', 'INFO-SILABO', $silabo);
    refresh_resource_pdf($cm_silabo, $silabo['filename'], $silabo['name'], $silabo['lines']);
    ensure_module($course, 0, 'resource', 'INFO-PROGRAMA', [
        'name' => 'Programa Analítico', 'filename' => 'Programa_Analitico_' . $short . '.pdf',
        'lines' => [$course->fullname, 'Unidad 1 y 2: Primer Parcial', 'Unidad 3 y 4: Segundo Parcial', 'Supletorio'],
    ]);
    ensure_module($course, 0, 'url', 'INFO-UTA', [
        'name' => 'Universidad Técnica de Ambato - Portal institucional', 'externalurl' => 'https://www.uta.edu.ec',
    ]);

    // --- Secciones 1 y 2: Parciales
    foreach ($parciales as $sec => $p) {
        block_label($course, $sec, "S$sec-ZI", 'Zona de información', 'Material de lectura y enlaces de apoyo por unidad.');
        foreach ($p['unidades'] as $u) {
            ensure_module($course, $sec, 'resource', "U$u-LECT", [
                'name' => "Unidad $u - Material de clase (PDF)", 'filename' => "Unidad_{$u}_{$short}.pdf",
                'lines' => [$course->fullname, "Unidad $u - Material de clase", 'Lectura obligatoria previa a las actividades.'],
            ]);
            ensure_module($course, $sec, 'url', "U$u-URL", [
                'name' => "Unidad $u - Enlace de apoyo", 'externalurl' => 'https://www.uta.edu.ec/v4.0/index.php/biblioteca',
            ]);
        }
        $blocks = [
            'acd'    => ['ACD', 'Actividades de Aprendizaje en Contacto con el Docente (ACD - 40%)', false],
            'tareas' => ['TAR', 'Actividades de Aprendizaje Autónomo / Tareas (30%)', true],
            'pae'    => ['PAE', 'Actividades Prácticas de Aplicación y Experimentación (PAE - 30%)', true],
        ];
        foreach ($blocks as $key => [$tag, $title, $files]) {
            block_label($course, $sec, "S$sec-$tag", $title);
            $i = 0;
            $n = count($p[$key]);
            foreach ($p[$key] as $idn => $name) {
                $i++;
                // Cerrado: la última actividad venció hace 1 semana. En curso: la primera vence dentro de 1 semana.
                $due = $p['cerrado'] ? $hoy - ($n - $i + 1) * 7 * DAYSECS : $hoy + $i * 7 * DAYSECS;
                $intro = $files ? 'Suba su archivo (PDF, DOCX o ZIP) antes de la fecha límite.' : 'Actividad evaluada en clase con el docente.';
                ensure_assign($course, $sec, $idn, $name, $intro, $due, $files);
            }
        }
    }

    // --- Sección 3: Supletorio
    block_label($course, 3, 'S3-INFO', 'Examen Supletorio', 'Solo para estudiantes que no alcanzaron la nota mínima de aprobación (7.00).');
    ensure_assign($course, 3, 'SUP-1', 'Examen Supletorio', 'Evaluación supletoria de todo el contenido.',
        $hoy + 6 * 7 * DAYSECS, false);

    rebuild_course_cache($course->id, true);
    out("  = $short: 4 secciones y actividades verificadas");
}

// =============================================================================
// 6. LIBRO DE CALIFICACIONES 40/30/30 Y NOTAS
// =============================================================================
out("[6/7] Libro de calificaciones ponderado y notas del Primer Parcial...");

/** Nota determinística alrededor de la base del estudiante (pasos de 0.25, rango 0-10). */
function seed_grade($base, $key) {
    $jitter = ((crc32($key) % 9) - 4) * 0.25;
    return round(max(0, min(10, $base + $jitter)) * 4) / 4;
}

$componentes = [
    'ACD'    => ['Actividades en Contacto con el Docente - ACD (40%)', 40, '/^U\d+-A\d+$/'],
    'TAREAS' => ['Aprendizaje Autónomo / Tareas (30%)', 30, '/^U\d+-T\d+$/'],
    'PAE'    => ['Prácticas de Aplicación y Experimentación - PAE (30%)', 30, '/^U\d+-P\d+$/'],
];

/**
 * Registra la entrega del estudiante (enviada 1-3 días antes del vencimiento) para que Moodle no muestre como
 * atrasadas las tareas ya calificadas. Con SIN ENTREGA no hay envío y la tarea sí figura como atrasada.
 */
function seed_submission(assign $assign, $userid, $entregada, $key) {
    global $DB;
    $submission = $assign->get_user_submission($userid, true);
    $instance = $assign->get_instance();
    $status = $entregada ? ASSIGN_SUBMISSION_STATUS_SUBMITTED : ASSIGN_SUBMISSION_STATUS_NEW;
    $time = $entregada
        ? $instance->duedate - (1 + crc32($key) % 3) * DAYSECS - (crc32("h$key") % 8) * HOURSECS
        : (int)$submission->timemodified;
    if ($submission->status !== $status || (int)$submission->timemodified !== $time) {
        $DB->update_record('assign_submission', (object)[
            'id' => $submission->id, 'status' => $status, 'timemodified' => $time,
            'timecreated' => min($time, (int)$submission->timecreated),
        ]);
    }
    $online = $assign->get_submission_plugin_by_type('onlinetext');
    if (!$entregada) {
        $DB->delete_records('assignsubmission_onlinetext', ['submission' => $submission->id]);
    } else if ($online && $online->is_enabled()
            && !$DB->record_exists('assignsubmission_onlinetext', ['submission' => $submission->id])) {
        $DB->insert_record('assignsubmission_onlinetext', (object)[
            'assignment' => $instance->id, 'submission' => $submission->id, 'onlineformat' => FORMAT_HTML,
            'onlinetext' => '<p>Adjunto el desarrollo de la actividad: ' . s($instance->name) . '.</p>',
        ]);
    }
}

foreach ($courses as $short => $course) {
    // Eliminar ítems manuales de siembras anteriores (esquema AUTONOMO/TAREAS/PAE)
    foreach (['AUTONOMO', 'TAREAS', 'PAE'] as $old) {
        if ($item = grade_item::fetch(['courseid' => $course->id, 'idnumber' => "$short-$old", 'itemtype' => 'manual'])) {
            $item->delete('seed');
        }
    }

    // Categoría del curso: media ponderada
    $coursecat = grade_category::fetch_course_category($course->id);
    $coursecat->aggregation = GRADE_AGGREGATE_WEIGHTED_MEAN;
    $coursecat->update('seed');
    $courseitem = grade_item::fetch_course_item($course->id);
    if ((float)$courseitem->grademax !== 10.0) {
        $courseitem->grademax = 10; // Total del curso sobre 10 (escala UTA)
        $courseitem->update('seed');
    }

    $cats = [];
    foreach ($componentes as $code => [$fullname, $weight]) {
        $cat = grade_category::fetch(['courseid' => $course->id, 'fullname' => $fullname]);
        if (!$cat) {
            $cat = new grade_category(['courseid' => $course->id, 'fullname' => $fullname], false);
            $cat->aggregation = GRADE_AGGREGATE_MEAN;
            $cat->aggregateonlygraded = 1;
            $cat->insert('seed');
        }
        $catitem = $cat->load_grade_item();
        $catitem->idnumber = "CAT-$code";
        $catitem->aggregationcoef = $weight;
        $catitem->grademax = 10;
        $catitem->update('seed');
        $cats[$code] = $cat;
    }

    // Ubicar cada tarea en su categoría según su ID number
    $items = grade_item::fetch_all(['courseid' => $course->id, 'itemtype' => 'mod', 'itemmodule' => 'assign']) ?: [];
    $items_by_idn = [];
    foreach ($items as $gi) {
        $cm = get_coursemodule_from_instance('assign', $gi->iteminstance, $course->id);
        $items_by_idn[$cm->idnumber] = [$gi, $cm];
        foreach ($componentes as $code => [, , $regex]) {
            if (preg_match($regex, $cm->idnumber) && $gi->categoryid != $cats[$code]->id) {
                $gi->set_parent($cats[$code]->id);
            }
        }
        if ($cm->idnumber === 'SUP-1' && (float)$gi->aggregationcoef !== 0.0) {
            $gi->aggregationcoef = 0; // El supletorio no pondera en la nota parcial
            $gi->update('seed');
        }
    }

    // Notas del Primer Parcial
    $roster = array_keys($courses_def[$short]['roster']);
    $pendiente_idn = end($roster);
    $graded = 0;
    foreach ($courses_def[$short]['roster'] as $idn => $base) {
        $user = $students[$idn];
        foreach ($items_by_idn as $itemidn => [$gi, $cm]) {
            if (!preg_match('/^U[12]-[ATP]\d+$/', $itemidn)) {
                continue; // Segundo Parcial y Supletorio aún no evaluados
            }
            $feedback = null;
            $value = seed_grade($base, "$short|$idn|$itemidn");
            if ($idn === 'U-04' && $itemidn === 'U1-T2') {
                $value = 0.0;                                   // Nota 0
            } else if ($idn === 'U-04' && $itemidn === 'U2-T4') {
                $value = 0.0; $feedback = 'SIN ENTREGA';        // No subió la tarea: se califica con 0
            } else if ($idn === $pendiente_idn && $itemidn === 'U2-P3') {
                $value = null; $feedback = 'PENDIENTE DE REVISIÓN';
            }

            // Quitar sobrescrituras manuales de siembras anteriores
            $gg = grade_grade::fetch(['itemid' => $gi->id, 'userid' => $user->id]);
            if ($gg && $gg->overridden) {
                $gg->set_overridden(false);
            }

            $assign = new assign(context_module::instance($cm->id), $cm, $course);
            seed_submission($assign, $user->id, $feedback !== 'SIN ENTREGA', "$short|$idn|$itemidn");
            $grade = $assign->get_user_grade($user->id, true);
            $grade->grade = $value === null ? -1 : $value;
            $grade->grader = $docente->id;
            // Comentario de retroalimentación (se publica en el libro de calificaciones)
            $assign->get_feedback_plugin_by_type('comments')->save($grade, (object)[
                'assignfeedbackcomments_editor' => ['text' => $feedback ?? '', 'format' => FORMAT_PLAIN],
            ]);
            $assign->update_grade($grade);
            $graded++;
        }
    }
    grade_regrade_final_grades($course->id);
    out("  = $short: categorías 40/30/30, $graded calificaciones registradas");
}

// =============================================================================
// 7. WEB SERVICES
// =============================================================================
out("[7/7] Web Services REST y token de integración...");
set_config('enablewebservices', 1);
set_config('webserviceprotocols', 'rest');

$service = $DB->get_record('external_services', ['name' => 'EduMonitor_WS']);
if (!$service) {
    $service = (object)['name' => 'EduMonitor_WS', 'shortname' => 'edumonitor_ws', 'enabled' => 1, 'restrictedusers' => 0,
                        'timecreated' => time(), 'timemodified' => time()];
    $service->id = $DB->insert_record('external_services', $service);
} else if (!$service->enabled) {
    $DB->set_field('external_services', 'enabled', 1, ['id' => $service->id]);
}
foreach (['core_webservice_get_site_info', 'core_course_get_courses', 'core_course_get_courses_by_field',
          'core_enrol_get_enrolled_users', 'gradereport_user_get_grade_items', 'core_grades_get_grades'] as $fn) {
    if ($DB->record_exists('external_functions', ['name' => $fn]) &&
        !$DB->record_exists('external_services_functions', ['externalserviceid' => $service->id, 'functionname' => $fn])) {
        $DB->insert_record('external_services_functions', (object)['externalserviceid' => $service->id, 'functionname' => $fn]);
    }
}

// Moodle limpia el token con PARAM_ALPHANUM: debe ser alfanumérico.
$token = getenv('MOODLE_TOKEN') ?: getenv('MOODLE_WS_TOKEN') ?: 'edumonitorutadevtoken2026fisei01';
$rec = $DB->get_record('external_tokens', ['externalserviceid' => $service->id, 'userid' => $admin->id]);
if ($rec) {
    $DB->update_record('external_tokens', (object)['id' => $rec->id, 'token' => $token, 'timemodified' => time()]);
} else {
    $DB->insert_record('external_tokens', (object)[
        'token' => $token, 'tokentype' => 0, 'userid' => $admin->id, 'externalserviceid' => $service->id,
        'contextid' => context_system::instance()->id, 'creatorid' => $admin->id, 'timecreated' => time(), 'timemodified' => time(),
    ]);
}
out("  = Servicio EduMonitor_WS activo, token configurado (" . substr($token, 0, 4) . "…)");

purge_all_caches();

echo "====================================================================\n";
echo " SIEMBRA COMPLETADA\n";
foreach ($courses_def as $short => $def) {
    printf("  %-10s %2d estudiantes\n", $short, count($def['roster']));
}
echo "  Admin: admin / MoodleAdmin2026!\n";
echo "  Docente: rgomez (docente@uta.edu.ec) / Docente2026!\n";
echo "  Estudiante (caso crítico): dcurillo / Estudiante2026!\n";
echo "====================================================================\n";

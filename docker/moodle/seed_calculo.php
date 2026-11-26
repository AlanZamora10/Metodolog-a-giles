<?php
/**
 * Siembra idempotente del curso CÁLCULO (Carrera de Telecomunicaciones, primer nivel) para EduMonitor AI.
 *
 * Fuente: documento «Unidades curriculares, unidades temáticas y contenidos mínimos» + tabla de APORTES.
 *
 *  - Categorías FISEI -> TELECOMUNICACIONES -> Julio a Diciembre 2026.
 *  - Curso SOF-CAL-A «(TEL) CALCULO - A» (el prefijo SOF- es el del portafolio que sincroniza el middleware,
 *    MOODLE_COURSE_PREFIX), docente titular Ing. Roberto Gómez (rgomez).
 *  - Aula: Informativo (sílabo con las unidades y contenidos mínimos) y Primer Parcial:
 *      U.1 Derivada: Derivada · Reglas de derivación · Derivación implícita · Aplicaciones de la derivada
 *      U.2 Integral Indefinida: Integral indefinida · Métodos de integración · Aplicaciones · Integrales irracionales
 *  - Tareas según los colores del documento:
 *      Tarea 1 (U1-T1): Derivada y Reglas de derivación
 *      Tarea 2 (U1-T2): Derivación implícita, Aplicaciones de la derivada e Integral indefinida
 *                       (la mayor parte de sus temas pertenece a la U.1)
 *      Tarea 3 (U2-T3): Métodos de integración, Aplicaciones e Integrales irracionales
 *  - 10 estudiantes (Estudiante 1..10 del documento, con nombres ficticios) y sus notas de aportes exactas.
 *    El curso sólo tiene Tareas: el middleware pondera sobre los componentes evaluados (nota = promedio de tareas).
 *
 * Re-ejecutable: crea lo que falta, actualiza fechas y notas y no toca los demás cursos.
 *   php seed_calculo.php
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

require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/course/modlib.php');
require_once($CFG->libdir . '/enrollib.php');
require_once($CFG->libdir . '/gradelib.php');
require_once($CFG->libdir . '/grade/grade_item.php');
require_once($CFG->libdir . '/grade/grade_category.php');
require_once($CFG->dirroot . '/mod/assign/locallib.php');
require_once($CFG->dirroot . '/lib/phpunit/classes/util.php');

global $DB, $CFG, $USER;

$admin = get_admin();
\core\session\manager::set_user($admin);
$gen = phpunit_util::get_data_generator();

function cal_out($msg) { echo $msg . "\n"; }

echo "====================================================================\n";
echo " SIEMBRA CURSO CÁLCULO (TELECOMUNICACIONES) - EduMonitor AI\n";
echo "====================================================================\n";

// ----------------------------------------------------------------------------- Categorías
function cal_categoria($name, $idnumber, $parent = 0) {
    global $DB;
    $cat = $DB->get_record('course_categories', ['idnumber' => $idnumber])
        ?: $DB->get_record('course_categories', ['name' => $name, 'parent' => $parent]);
    if ($cat) {
        return $cat->id;
    }
    return core_course_category::create((object)[
        'name' => $name, 'idnumber' => $idnumber, 'parent' => $parent,
        'description' => "Categoría académica $name", 'descriptionformat' => FORMAT_HTML,
    ])->id;
}
$cat_fisei = cal_categoria('FISEI', 'CAT_FISEI');
$cat_tel = cal_categoria('TELECOMUNICACIONES', 'CAT_TELECOM', $cat_fisei);
$cat_periodo = cal_categoria('Julio a Diciembre 2026', 'CAT_TEL_2026_JD', $cat_tel);

// ----------------------------------------------------------------------------- Usuarios
/** Dígito verificador de la cédula ecuatoriana (módulo 10) a partir de los 9 primeros dígitos. */
function cal_cedula($base9) {
    $suma = 0;
    foreach (str_split($base9) as $i => $d) {
        $p = (int)$d * ($i % 2 === 0 ? 2 : 1);
        $suma += $p > 9 ? $p - 9 : $p;
    }
    return $base9 . ((10 - $suma % 10) % 10);
}

function cal_plano($t) {
    return strtolower(preg_replace('/[^A-Za-z]/', '', iconv('UTF-8', 'ASCII//TRANSLIT', $t)));
}

/** Mismas convenciones que seed.php: correo institucional y contraseña PrimerNombrePrimerApellido1!. */
function cal_usuario($idnumber, $username, $nombres, $apellidos, $cedula) {
    global $DB, $CFG;
    $email = substr(cal_plano(explode(' ', $nombres)[0]), 0, 1) . cal_plano(explode(' ', $apellidos)[0])
        . substr($cedula, -4) . '@uta.edu.ec';
    $base = ['mnethostid' => $CFG->mnet_localhost_id, 'deleted' => 0];
    $user = $DB->get_record('user', $base + ['idnumber' => $idnumber])
        ?: $DB->get_record('user', $base + ['username' => $username]);
    $data = [
        'username' => $username, 'firstname' => $nombres, 'lastname' => $apellidos, 'email' => $email,
        'idnumber' => $idnumber, 'auth' => 'manual', 'confirmed' => 1, 'lang' => 'es', 'city' => 'Ambato',
        'country' => 'EC', 'institution' => 'Universidad Técnica de Ambato',
        'department' => 'FISEI - Telecomunicaciones', 'timemodified' => time(),
    ];
    if ($user) {
        $data['id'] = $user->id;
        $DB->update_record('user', (object)$data);
    } else {
        $data += ['mnethostid' => $CFG->mnet_localhost_id, 'timecreated' => time(), 'password' => ''];
        $data['id'] = $DB->insert_record('user', (object)$data);
        cal_out("  + Usuario creado: $username ($nombres $apellidos)");
    }
    $user = $DB->get_record('user', ['id' => $data['id']]);
    $clave = ucfirst(cal_plano(explode(' ', $nombres)[0])) . ucfirst(cal_plano(explode(' ', $apellidos)[0])) . '1!';
    update_internal_user_password($user, $clave);

    // Campo de perfil «cedula» (lo crea seed.php)
    if ($campo = $DB->get_record('user_info_field', ['shortname' => 'cedula'])) {
        if ($fila = $DB->get_record('user_info_data', ['userid' => $user->id, 'fieldid' => $campo->id])) {
            $DB->set_field('user_info_data', 'data', $cedula, ['id' => $fila->id]);
        } else {
            $DB->insert_record('user_info_data', (object)['userid' => $user->id, 'fieldid' => $campo->id,
                'data' => $cedula, 'dataformat' => 0]);
        }
    }
    return $user;
}

$docente = $DB->get_record('user', ['username' => 'rgomez', 'deleted' => 0]);
if (!$docente) {
    echo "[ERROR] No existe el docente rgomez: ejecute primero seed.php.\n";
    exit(1);
}
$docente_nombre = 'Ing. ' . fullname($docente);

// Estudiante N del documento => [idnumber, usuario, nombres, apellidos, cédula (9 dígitos + verificador),
//                                Tarea 1, Tarea 2, Tarea 3]
$aportes = [
    1  => ['U-29', 'dcaiza',     'Diego Fernando',    'Caiza Ortiz',        '180512346', 1.5, 1.5, 4.0],
    2  => ['U-30', 'knunez',     'Karla Estefanía',   'Núñez Silva',        '180633457', 7.0, 1.5, 8.0],
    3  => ['U-31', 'mguevara',   'Mateo Sebastián',   'Guevara Pinto',      '050712894', 1.5, 8.0, 1.5],
    4  => ['U-32', 'vmorales',   'Valentina Isabel',  'Morales Cárdenas',   '180745621', 3.0, 8.0, 9.0],
    5  => ['U-33', 'jandrade',   'Josué David',       'Andrade Villalba',   '060318745', 7.0, 6.0, 8.0],
    6  => ['U-34', 'crobalino',  'Camila Fernanda',   'Robalino Paz',       '180856732', 4.0, 6.0, 5.0],
    7  => ['U-35', 'esailema',   'Erick Alexander',   'Sailema Chicaiza',   '180967843', 1.7, 9.0, 3.0],
    8  => ['U-36', 'dfreire',    'Doménica Paola',    'Freire López',       '050823916', 4.0, 1.5, 1.5],
    9  => ['U-37', 'slascano',   'Santiago Andrés',   'Lascano Mera',       '181078954', 7.0, 9.0, 1.5],
    10 => ['U-38', 'apazmino',   'Ariana Nicole',     'Pazmiño Ríos',       '170934268', 8.7, 8.8, 9.0],
];
$estudiantes = [];
foreach ($aportes as $n => [$idn, $uname, $fn, $ln, $base9]) {
    $estudiantes[$n] = cal_usuario($idn, $uname, $fn, $ln, cal_cedula($base9));
}
cal_out("  = Docente $docente_nombre y " . count($estudiantes) . " estudiantes sincronizados");

// ----------------------------------------------------------------------------- Curso y nómina
$short = 'SOF-CAL-A';
$course = $DB->get_record('course', ['shortname' => $short]);
if (!$course) {
    $course = create_course((object)[
        'category' => $cat_periodo, 'fullname' => '(TEL) CALCULO - A', 'shortname' => $short, 'idnumber' => $short,
        'summary' => 'Cálculo - Carrera de Telecomunicaciones, primer nivel - Paralelo A', 'format' => 'topics',
        'numsections' => 1, 'visible' => 1, 'startdate' => strtotime('2026-07-01'),
    ]);
    cal_out("  + Curso creado: (TEL) CALCULO - A");
}

$rol_docente = $DB->get_record('role', ['shortname' => 'editingteacher'], '*', MUST_EXIST);
$rol_estudiante = $DB->get_record('role', ['shortname' => 'student'], '*', MUST_EXIST);
enrol_try_internal_enrol($course->id, $docente->id, $rol_docente->id);
foreach ($estudiantes as $u) {
    enrol_try_internal_enrol($course->id, $u->id, $rol_estudiante->id);
}
$instancia = $DB->get_record('enrol', ['courseid' => $course->id, 'enrol' => 'manual'], '*', MUST_EXIST);
$validos = array_merge([(int)$docente->id], array_map(fn($u) => (int)$u->id, $estudiantes));
foreach ($DB->get_records('user_enrolments', ['enrolid' => $instancia->id]) as $ue) {
    if (!in_array((int)$ue->userid, $validos, true)) {
        enrol_get_plugin('manual')->unenrol_user($instancia, $ue->userid);
    }
}

// ----------------------------------------------------------------------------- Aula virtual
/** PDF mínimo válido de una página (mismo formato que seed.php). */
function cal_pdf($title, array $lines) {
    $esc = function ($s) {
        $s = mb_convert_encoding($s, 'Windows-1252', 'UTF-8');
        return str_replace(['\\', '(', ')'], ['\\\\', '\\(', '\\)'], $s);
    };
    $content = "BT /F1 16 Tf 60 780 Td (" . $esc($title) . ") Tj ET\n";
    $y = 745;
    foreach ($lines as $line) {
        $content .= "BT /F1 10 Tf 60 $y Td (" . $esc($line) . ") Tj ET\n";
        $y -= 16;
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

function cal_modulo($course, $section, $modname, $idnumber, array $fields) {
    global $DB, $gen, $USER;
    if ($cm = $DB->get_record('course_modules', ['course' => $course->id, 'idnumber' => $idnumber])) {
        return $cm;
    }
    $record = ['course' => $course->id, 'section' => $section, 'idnumber' => $idnumber] + $fields;
    if ($modname === 'resource') {
        $draft = file_get_unused_draft_itemid();
        get_file_storage()->create_file_from_string([
            'contextid' => context_user::instance($USER->id)->id, 'component' => 'user', 'filearea' => 'draft',
            'itemid' => $draft, 'filepath' => '/', 'filename' => $fields['filename'],
        ], cal_pdf($fields['name'], $fields['lines']));
        unset($record['filename'], $record['lines']);
        $record['files'] = $draft;
    }
    $instance = $gen->create_module($modname, $record);
    return $DB->get_record('course_modules', ['id' => $instance->cmid]);
}

function cal_etiqueta($course, $section, $key, $title, $subtitle = '') {
    $html = '<h4 class="uta-block-title">' . s($title) . '</h4>' . ($subtitle ? '<p>' . $subtitle . '</p>' : '');
    cal_modulo($course, $section, 'label', "LBL-$key", ['intro' => $html, 'introformat' => FORMAT_HTML]);
}

// Unidades curriculares, unidades temáticas y contenidos mínimos (documento del curso)
$unidades = [
    1 => ['Derivada', [
        'Derivada' => ['Definición', 'Interpretación geométrica y física', 'Derivabilidad y continuidad'],
        'Reglas de derivación' => ['Derivadas simples y compuestas de funciones reales',
            'Derivadas de funciones trigonométricas',
            'Derivadas de funciones inversas trigonométricas, exponenciales y logarítmicas'],
        'Derivación implícita' => ['Derivada de una función real de una potencia real',
            'Ecuaciones tangente y normal a la curva', 'Ecuaciones paramétricas'],
        'Aplicaciones de la derivada' => ['Gráficos de funciones, puntos críticos',
            'Monotonía de una función, rangos crecientes y decrecientes', 'Máximos y mínimos',
            'Aplicaciones geométricas y mecánicas de la derivada', 'Problemas de optimización'],
    ]],
    2 => ['Integral Indefinida', [
        'Integral Indefinida' => ['Introducción y análisis de la antiderivada', 'Integral indefinida',
            'Fórmulas básicas de integración'],
        'Métodos de Integración' => ['Sustitución (cambio de variable)', 'Contienen trinomios cuadrados perfectos',
            'Trigonométricas', 'Partes', 'Hermite-Ostrogradski', 'Racionales de senos y cosenos'],
        'Aplicaciones' => ['Movimiento rectilíneo', 'Aceleración', 'Movimiento vertical', 'Economía'],
        'Integrales Irracionales' => ['Fórmulas de reducción'],
    ]],
];

// [idnumber, unidad, nombre, temas que evalúa, vencimiento en días respecto de hoy]
$tareas = [
    1 => ['U1-T1', 1, 'Tarea 1: Derivada y reglas de derivación', ['Derivada', 'Reglas de derivación'], -42],
    2 => ['U1-T2', 1, 'Tarea 2: Derivación implícita, aplicaciones de la derivada e integral indefinida',
          ['Derivación implícita', 'Aplicaciones de la derivada', 'Integral Indefinida'], -28],
    3 => ['U2-T3', 2, 'Tarea 3: Métodos de integración, aplicaciones e integrales irracionales',
          ['Métodos de Integración', 'Aplicaciones', 'Integrales Irracionales'], -14],
];

course_create_sections_if_missing($course, [0, 1]);
foreach ([0 => 'Informativo', 1 => 'Primer Parcial'] as $num => $nombre) {
    course_update_section($course, $DB->get_record('course_sections', ['course' => $course->id, 'section' => $num]),
        ['name' => $nombre]);
}

cal_etiqueta($course, 0, 'S0-AVISOS', 'Avisos importantes',
    'Carrera de Telecomunicaciones · Primer nivel. Tutorías: martes y jueves de 14:00 a 15:00.');
$silabo = ['Carrera: Telecomunicaciones | Nivel: Primero', 'Período académico: Julio - Diciembre 2026',
           "Docente: $docente_nombre", 'Unidades curriculares, unidades temáticas y contenidos mínimos:'];
foreach ($unidades as $u => [$titulo, $tematicas]) {
    $silabo[] = "U.$u $titulo: " . implode(' | ', array_keys($tematicas));
}
$silabo[] = 'Aportes: Tarea 1, Tarea 2 y Tarea 3 (Primer Parcial).';
cal_modulo($course, 0, 'resource', 'INFO-SILABO', [
    'name' => 'Sílabo de la asignatura', 'filename' => "Silabo_$short.pdf", 'lines' => $silabo,
]);

cal_etiqueta($course, 1, 'S1-ZI', 'Zona de información', 'Material de lectura por unidad.');
foreach ($unidades as $u => [$titulo, $tematicas]) {
    $lista = '';
    $lineas = ["Unidad $u: $titulo", 'Unidades temáticas y contenidos mínimos:'];
    foreach ($tematicas as $tema => $contenidos) {
        $lista .= '<li><strong>' . s($tema) . ':</strong> ' . s(implode('; ', $contenidos)) . '</li>';
        $lineas[] = "- $tema: " . implode('; ', $contenidos);
    }
    cal_etiqueta($course, 1, "S1-U$u", "Unidad $u: $titulo", "<ul>$lista</ul>");
    cal_modulo($course, 1, 'resource', "U$u-LECT", [
        'name' => "Unidad $u - Material de clase (PDF)", 'filename' => "Unidad_{$u}_$short.pdf", 'lines' => $lineas,
    ]);
}

cal_etiqueta($course, 1, 'S1-TAR', 'Tareas (aportes)');
$hoy = usergetmidnight(time(), 'America/Guayaquil') + DAYSECS - MINSECS;
$cms = [];
foreach ($tareas as $n => [$idn, $u, $nombre, $temas, $dias]) {
    $vence = $hoy + $dias * DAYSECS;
    $fechas = ['duedate' => $vence, 'allowsubmissionsfromdate' => $vence - 14 * DAYSECS,
               'gradingduedate' => $vence + 7 * DAYSECS, 'cutoffdate' => 0];
    $intro = '<p>Temas evaluados: ' . s(implode(', ', $temas)) . '.</p><p>Suba el desarrollo (PDF) antes de la fecha límite.</p>';
    $cm = cal_modulo($course, 1, 'assign', $idn, $fechas + [
        'name' => $nombre, 'intro' => $intro, 'introformat' => FORMAT_HTML, 'grade' => 10,
        'assignsubmission_file_enabled' => 1, 'assignsubmission_file_maxfiles' => 5,
        'assignsubmission_file_maxsizebytes' => 10485760, 'assignsubmission_file_filetypes' => '',
        'assignsubmission_onlinetext_enabled' => 1, 'assignsubmission_onlinetext_wordlimit' => 0,
        'assignfeedback_comments_enabled' => 1, 'submissiondrafts' => 0,
    ]);
    $actual = $DB->get_record('assign', ['id' => $cm->instance], implode(',', array_keys($fechas)), MUST_EXIST);
    if (array_map('intval', (array)$actual) != $fechas) {
        $DB->update_record('assign', (object)(['id' => $cm->instance, 'timemodified' => time()] + $fechas));
    }
    $cms[$n] = $cm;
}
rebuild_course_cache($course->id, true);
cal_out("  = Aula: Informativo + Primer Parcial (U.1 Derivada, U.2 Integral Indefinida, 3 tareas)");

// ----------------------------------------------------------------------------- Libro de calificaciones
$catcurso = grade_category::fetch_course_category($course->id);
$catcurso->aggregation = GRADE_AGGREGATE_WEIGHTED_MEAN;
$catcurso->aggregateonlygraded = 1;
$catcurso->update('seed');
$total = grade_item::fetch_course_item($course->id);
if ((float)$total->grademax !== 10.0) {
    $total->grademax = 10;
    $total->update('seed');
}
$item_cat = grade_item::fetch(['courseid' => $course->id, 'itemtype' => 'category', 'idnumber' => 'CAT-TAREAS']);
$cat = $item_cat ? grade_category::fetch(['id' => $item_cat->iteminstance]) : null;
if (!$cat) {
    $cat = new grade_category(['courseid' => $course->id, 'fullname' => 'Tareas (30%)'], false);
    $cat->aggregation = GRADE_AGGREGATE_MEAN;
    $cat->aggregateonlygraded = 1;
    $cat->insert('seed');
}
$catitem = $cat->load_grade_item();
$catitem->idnumber = 'CAT-TAREAS';
$catitem->aggregationcoef = 30;
$catitem->grademax = 10;
$catitem->update('seed');

$calificadas = 0;
foreach ($cms as $n => $cm) {
    $gi = grade_item::fetch(['courseid' => $course->id, 'itemtype' => 'mod', 'itemmodule' => 'assign',
                             'iteminstance' => $cm->instance]);
    if ($gi->categoryid != $cat->id) {
        $gi->set_parent($cat->id);
    }
    $cminfo = get_coursemodule_from_id('assign', $cm->id, $course->id, false, MUST_EXIST);
    $assign = new assign(context_module::instance($cm->id), $cminfo, $course);
    $instancia_assign = $assign->get_instance();
    foreach ($aportes as $e => $fila) {
        $nota = (float)$fila[4 + $n];   // columnas Tarea 1..3 del documento
        $u = $estudiantes[$e];
        // Entrega registrada 2 días antes del vencimiento (no figura como atrasada)
        $sub = $assign->get_user_submission($u->id, true);
        $enviada = (int)$instancia_assign->duedate - 2 * DAYSECS;
        if ($sub->status !== ASSIGN_SUBMISSION_STATUS_SUBMITTED || (int)$sub->timemodified !== $enviada) {
            $DB->update_record('assign_submission', (object)['id' => $sub->id,
                'status' => ASSIGN_SUBMISSION_STATUS_SUBMITTED, 'timemodified' => $enviada,
                'timecreated' => min($enviada, (int)$sub->timecreated)]);
        }
        $grade = $assign->get_user_grade($u->id, true);
        $grade->grade = $nota;
        $grade->grader = $docente->id;
        $assign->update_grade($grade);
        grade_update('mod/assign', $course->id, 'mod', 'assign', $cm->instance, 0, [
            'userid' => $u->id, 'rawgrade' => $nota, 'usermodified' => $docente->id,
            'feedback' => null, 'feedbackformat' => FORMAT_PLAIN,
        ]);
        $calificadas++;
    }
}
grade_regrade_final_grades($course->id);
cal_out("  = Libro de calificaciones: $calificadas notas de aportes registradas");

purge_all_caches();
echo "====================================================================\n";
echo " CURSO CÁLCULO LISTO: $short (docente rgomez)\n";
foreach ($aportes as $n => [$idn, $uname, $fn, $ln, , $t1, $t2, $t3]) {
    printf("  Estudiante %-2d -> %s %s %s  T1 %.1f  T2 %.1f  T3 %.1f\n", $n, $idn, $fn, $ln, $t1, $t2, $t3);
}
echo "====================================================================\n";

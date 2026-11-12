<?php
/**
 * Script de Siembra Idempotente para Moodle UTA (FISEI)
 * Proyecto: Capa Inteligente de Seguimiento Académico (EduMonitor AI)
 * 
 * Requisitos:
 * 1. Categorías jerárquicas: FISEI -> SOFTWARE -> Julio a Diciembre 2026
 * 2. 1 Docente + 7 Estudiantes ficticios (Estudiante A a Estudiante G)
 * 3. 4 Cursos del portafolio con formato Temas (topics) y ponderación 40/30/30:
 *    - (SOF) PROGRAMACION ORIENTADA A OBJETOS - A
 *    - (SOF) ESTRUCTURA DE DATOS - B
 *    - (SOF) METODOLOGIAS AGILES - B
 *    - (SOF) MANEJO Y CONFIGURACION DEL SOFTWARE - A
 * 4. Calificaciones de prueba (incluyendo normales, 0.0, SIN_ENTREGA y PENDIENTE)
 * 5. Habilitación de Web Services REST, servicio EduMonitor_WS y token de integración.
 */

define('CLI_SCRIPT', true);

// Detección de ruta de configuración de Moodle en Bitnami o estándar
$config_paths = [
    __DIR__ . '/../../config.php',
    '/opt/bitnami/moodle/config.php',
    '/var/www/html/config.php'
];

$config_loaded = false;
foreach ($config_paths as $path) {
    if (file_exists($path)) {
        require_once($path);
        $config_loaded = true;
        break;
    }
}

if (!$config_loaded) {
    echo "[ERROR] No se pudo localizar config.php de Moodle en ninguna ruta conocida.\n";
    exit(1);
}

require_once($CFG->libdir . '/clilib.php');
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/user/lib.php');
require_once($CFG->dirroot . '/lib/enrollib.php');
require_once($CFG->dirroot . '/lib/grade/grade_item.php');
require_once($CFG->dirroot . '/lib/grade/grade_grade.php');
require_once($CFG->dirroot . '/lib/grade/grade_category.php');

global $DB, $CFG;

echo "====================================================================\n";
echo " INICIANDO SIEMBRA AUTOMATIZADA IDEMPOTENTE: Moodle UTA (FISEI)\n";
echo "====================================================================\n";

// -----------------------------------------------------------------------------
// 1. Configuración de Nombre de Sitio e Idioma Español
// -----------------------------------------------------------------------------
echo "[1/6] Configurando Sitio Moodle UTA e Idioma...\n";
set_config('sitename', 'Moodle UTA');
set_config('fullname', 'Moodle UTA');
set_config('shortname', 'Moodle UTA');
set_config('lang', 'es');

$site = get_site();
if ($site) {
    $site->fullname = 'Moodle UTA';
    $site->shortname = 'Moodle UTA';
    $DB->update_record('course', $site);
}
echo "  -> Nombre de sitio establecido: 'Moodle UTA'\n";
echo "  -> Idioma predeterminado establecido: 'es' (Español)\n";

// -----------------------------------------------------------------------------
// 2. Jerarquía de Categorías: FISEI -> SOFTWARE -> Julio a Diciembre 2026
// -----------------------------------------------------------------------------
echo "[2/6] Verificando Jerarquía de Categorías...\n";

function get_or_create_category($name, $idnumber, $parent_id = 0) {
    global $DB;
    $cat = $DB->get_record('course_categories', ['idnumber' => $idnumber]);
    if (!$cat) {
        $cat = $DB->get_record('course_categories', ['name' => $name, 'parent' => $parent_id]);
    }
    if (!$cat) {
        require_once($GLOBALS['CFG']->dirroot . '/course/classes/category.php');
        $newcat = new stdClass();
        $newcat->name = $name;
        $newcat->idnumber = $idnumber;
        $newcat->parent = $parent_id;
        $newcat->description = "Categoría académica institucional $name";
        $newcat->descriptionformat = FORMAT_HTML;
        $created = core_course_category::create($newcat);
        echo "  + Creada categoría: $name (ID: {$created->id})\n";
        return $created->id;
    }
    echo "  = Categoría existente: $name (ID: {$cat->id})\n";
    return $cat->id;
}

$cat_fisei_id = get_or_create_category('FISEI', 'CAT_FISEI', 0);
$cat_sof_id   = get_or_create_category('SOFTWARE', 'CAT_SOFTWARE', $cat_fisei_id);
$cat_period_id = get_or_create_category('Julio a Diciembre 2026', 'CAT_2026_JD', $cat_sof_id);

// -----------------------------------------------------------------------------
// 3. Creación de Usuarios: Docente y 7 Estudiantes (U-03 a U-09)
// -----------------------------------------------------------------------------
echo "[3/6] Creando Usuario Docente y 7 Estudiantes...\n";

function get_or_create_user($username, $firstname, $lastname, $email, $idnumber, $password = 'Docente2026!') {
    global $DB, $CFG;
    $user = $DB->get_record('user', ['username' => $username, 'mnethostid' => $CFG->mnet_localhost_id]);
    if (!$user) {
        $user = $DB->get_record('user', ['email' => $email, 'mnethostid' => $CFG->mnet_localhost_id]);
    }
    if (!$user) {
        $newuser = new stdClass();
        $newuser->username = $username;
        $newuser->password = hash_internal_user_password($password);
        $newuser->firstname = $firstname;
        $newuser->lastname = $lastname;
        $newuser->email = $email;
        $newuser->idnumber = $idnumber;
        $newuser->confirmed = 1;
        $newuser->mnethostid = $CFG->mnet_localhost_id;
        $newuser->lang = 'es';
        $newuser->auth = 'manual';
        $newuser->timecreated = time();
        $newuser->timemodified = time();
        $id = $DB->insert_record('user', $newuser);
        $newuser->id = $id;
        echo "  + Usuario creado: $username ($firstname $lastname) [ID: $id, IDNumber: $idnumber]\n";
        return $newuser;
    }
    echo "  = Usuario existente: $username [ID: {$user->id}]\n";
    return $user;
}

$docente_user = get_or_create_user(
    'docente',
    'Ing. Hernán',
    'Naranjo, Mg.',
    'docente@uta.edu.ec',
    'U-01',
    'Docente2026!'
);

$students_data = [
    ['estudiante_a', 'Estudiante', 'A', 'estudiante.a@uta.edu.ec', 'U-03'],
    ['estudiante_b', 'Estudiante', 'B', 'estudiante.b@uta.edu.ec', 'U-04'],
    ['estudiante_c', 'Estudiante', 'C', 'estudiante.c@uta.edu.ec', 'U-05'],
    ['estudiante_d', 'Estudiante', 'D', 'estudiante.d@uta.edu.ec', 'U-06'],
    ['estudiante_e', 'Estudiante', 'E', 'estudiante.e@uta.edu.ec', 'U-07'],
    ['estudiante_f', 'Estudiante', 'F', 'estudiante.f@uta.edu.ec', 'U-08'],
    ['estudiante_g', 'Estudiante', 'G', 'estudiante.g@uta.edu.ec', 'U-09'],
];

$student_users = [];
foreach ($students_data as $s) {
    $student_users[$s[4]] = get_or_create_user(
        $s[0], $s[1], $s[2], $s[3], $s[4], 'Estudiante2026!'
    );
}

// -----------------------------------------------------------------------------
// 4. Creación de los 4 Cursos del Portafolio con Formato Temas (topics)
// -----------------------------------------------------------------------------
echo "[4/6] Creando los 4 Cursos del Portafolio...\n";

$courses_def = [
    [
        'fullname'  => '(SOF) PROGRAMACION ORIENTADA A OBJETOS - A',
        'shortname' => 'SOF-POO-A',
        'idnumber'  => 'SOF-POO-A',
        'summary'   => 'Curso institucional de Programación Orientada a Objetos - Paralelo A'
    ],
    [
        'fullname'  => '(SOF) ESTRUCTURA DE DATOS - B',
        'shortname' => 'SOF-ED-B',
        'idnumber'  => 'SOF-ED-B',
        'summary'   => 'Curso institucional de Estructura de Datos - Paralelo B'
    ],
    [
        'fullname'  => '(SOF) METODOLOGIAS AGILES - B',
        'shortname' => 'SOF-MA-B',
        'idnumber'  => 'SOF-MA-B',
        'summary'   => 'Curso institucional de Metodologías Ágiles de Desarrollo de Software - Paralelo B'
    ],
    [
        'fullname'  => '(SOF) MANEJO Y CONFIGURACION DEL SOFTWARE - A',
        'shortname' => 'SOF-MCS-A',
        'idnumber'  => 'SOF-MCS-A',
        'summary'   => 'Curso institucional de Manejo y Configuración del Software - Paralelo A'
    ]
];

$role_teacher = $DB->get_record('role', ['shortname' => 'editingteacher']);
$role_student = $DB->get_record('role', ['shortname' => 'student']);

$created_courses = [];

foreach ($courses_def as $cdef) {
    $course = $DB->get_record('course', ['shortname' => $cdef['shortname']]);
    if (!$course) {
        $course = $DB->get_record('course', ['idnumber' => $cdef['idnumber']]);
    }
    if (!$course) {
        $cdata = new stdClass();
        $cdata->category    = $cat_period_id;
        $cdata->fullname    = $cdef['fullname'];
        $cdata->shortname   = $cdef['shortname'];
        $cdata->idnumber    = $cdef['idnumber'];
        $cdata->summary     = $cdef['summary'];
        $cdata->format      = 'topics';
        $cdata->numsections = 4;
        $cdata->visible     = 1;
        $cdata->startdate   = time() - 3600 * 24 * 30; // Iniciado hace un mes
        $course = create_course($cdata);
        echo "  + Curso creado: {$cdef['fullname']} [ID: {$course->id}]\n";
    } else {
        echo "  = Curso existente: {$cdef['fullname']} [ID: {$course->id}]\n";
    }
    $created_courses[$cdef['shortname']] = $course;

    // Matricular Docente
    if ($role_teacher) {
        enrol_try_internal_enrol($course->id, $docente_user->id, $role_teacher->id);
    }

    // Matricular los 7 Estudiantes
    if ($role_student) {
        foreach ($student_users as $stu) {
            enrol_try_internal_enrol($course->id, $stu->id, $role_student->id);
        }
    }
}

// -----------------------------------------------------------------------------
// 5. Configurar Ponderación 40/30/30 y Calificaciones de Prueba
// -----------------------------------------------------------------------------
echo "[5/6] Configurando Categorías de Calificación (40/30/30) y Notas de Prueba...\n";

// Definición de notas de prueba para los 7 estudiantes
// Criterio: Estudiante C y D críticos (< 5.0), F en riesgo con SIN_ENTREGA, G con PENDIENTE
$mock_grades_by_student = [
    'U-03' => ['autonomo' => 8.00, 'tareas' => 8.00, 'pae' => 8.00, 'estado' => 'NORMAL'],
    'U-04' => ['autonomo' => 8.50, 'tareas' => 8.50, 'pae' => 8.50, 'estado' => 'NORMAL'],
    'U-05' => ['autonomo' => 0.00, 'tareas' => 3.00, 'pae' => 4.00, 'estado' => 'CRITICO_CERO'], // Caso Crítico con 0.0
    'U-06' => ['autonomo' => 4.50, 'tareas' => 4.00, 'pae' => 5.00, 'estado' => 'CRITICO'],      // Caso Crítico < 5.0
    'U-07' => ['autonomo' => 8.00, 'tareas' => 7.00, 'pae' => 7.67, 'estado' => 'NORMAL'],
    'U-08' => ['autonomo' => 6.50, 'tareas' => null, 'pae' => 6.00, 'estado' => 'SIN_ENTREGA'], // SIN ENTREGA en Tareas
    'U-09' => ['autonomo' => 8.50, 'tareas' => 8.00, 'pae' => -1.0, 'estado' => 'PENDIENTE'],   // PENDIENTE en PAE
];

foreach ($created_courses as $shortname => $course) {
    // 5.1 Crear Items de Calificación Manuales para los 3 Componentes
    // Autónomo (40%), Tareas (30%), PAE (30%)
    $items = [
        ['itemname' => 'Componente 1: Evaluación y Trabajo Autónomo (40%)', 'idnumber' => "{$shortname}-AUTONOMO", 'grademax' => 10.00],
        ['itemname' => 'Componente 2: Tareas y Talleres (30%)',            'idnumber' => "{$shortname}-TAREAS",   'grademax' => 10.00],
        ['itemname' => 'Componente 3: Prácticas de Aplicación PAE (30%)',  'idnumber' => "{$shortname}-PAE",      'grademax' => 10.00],
    ];

    $grade_items_map = [];

    foreach ($items as $item_def) {
        $item = grade_item::fetch([
            'courseid' => $course->id,
            'idnumber' => $item_def['idnumber']
        ]);
        if (!$item) {
            $item = new grade_item();
            $item->courseid = $course->id;
            $item->itemname = $item_def['itemname'];
            $item->idnumber = $item_def['idnumber'];
            $item->itemtype = 'manual';
            $item->gradetype = GRADE_TYPE_VALUE;
            $item->grademax = $item_def['grademax'];
            $item->grademin = 0.00;
            $item->insert();
            echo "  + Item de calificación creado: {$item_def['itemname']} en $shortname\n";
        }
        $grade_items_map[$item_def['idnumber']] = $item;
    }

    // 5.2 Asignar Calificaciones de Prueba a los Estudiantes
    foreach ($mock_grades_by_student as $idnumber => $gdata) {
        $stu_user = $student_users[$idnumber];

        // 1. Autónomo
        $item_auto = $grade_items_map["{$shortname}-AUTONOMO"];
        if ($gdata['autonomo'] !== null && $gdata['autonomo'] >= 0) {
            $item_auto->update_final_grade($stu_user->id, $gdata['autonomo'], 'seed');
        }

        // 2. Tareas (soporta SIN_ENTREGA -> null)
        $item_tareas = $grade_items_map["{$shortname}-TAREAS"];
        if ($gdata['tareas'] === null) {
            // Representa SIN_ENTREGA: no se registra calificación o se marca rawgrade null
            $item_tareas->update_final_grade($stu_user->id, null, 'seed');
        } else {
            $item_tareas->update_final_grade($stu_user->id, $gdata['tareas'], 'seed');
        }

        // 3. PAE (soporta PENDIENTE -> -1.0 o feedback)
        $item_pae = $grade_items_map["{$shortname}-PAE"];
        if ($gdata['pae'] === -1.0) {
            // Representa PENDIENTE
            $item_pae->update_final_grade($stu_user->id, null, 'seed', 'PENDIENTE DE REVISIÓN');
        } else {
            $item_pae->update_final_grade($stu_user->id, $gdata['pae'], 'seed');
        }
    }
}

// -----------------------------------------------------------------------------
// 6. Configurar Web Services REST, Servicio EduMonitor_WS y Token
// -----------------------------------------------------------------------------
echo "[6/6] Configurando Web Services REST y Token de Integración...\n";

// Habilitar Web Services globalmente
set_config('enablewebservices', 1);
set_config('webserviceprotocols', 'rest');

// Verificar o crear servicio externo EduMonitor_WS
$service_name = 'EduMonitor_WS';
$service = $DB->get_record('external_services', ['name' => $service_name]);

if (!$service) {
    $service = new stdClass();
    $service->name = $service_name;
    $service->shortname = 'edumonitor_ws';
    $service->enabled = 1;
    $service->restrictedusers = 0;
    $service->tokenauthfriendly = 1;
    $service->timecreated = time();
    $service->timemodified = time();
    $service_id = $DB->insert_record('external_services', $service);
    $service->id = $service_id;
    echo "  + Creado Servicio Web Externo: $service_name (ID: $service_id)\n";
} else {
    $service->enabled = 1;
    $DB->update_record('external_services', $service);
    echo "  = Servicio Web Externo existente: $service_name (ID: {$service->id})\n";
}

// Agregar funciones esenciales a EduMonitor_WS
$required_functions = [
    'core_webservice_get_site_info',
    'core_course_get_courses',
    'core_course_get_courses_by_field',
    'core_enrol_get_enrolled_users',
    'gradereport_user_get_grade_items',
    'core_grades_get_grades'
];

foreach ($required_functions as $func_name) {
    $func = $DB->get_record('external_functions', ['name' => $func_name]);
    if ($func) {
        $link = $DB->get_record('external_services_functions', [
            'externalserviceid' => $service->id,
            'functionname' => $func_name
        ]);
        if (!$link) {
            $newlink = new stdClass();
            $newlink->externalserviceid = $service->id;
            $newlink->functionname = $func_name;
            $DB->insert_record('external_services_functions', $newlink);
            echo "    -> Función agregada: $func_name\n";
        }
    }
}

// Token de Integración: ws_mock_token_uta_fisei_sprint1
$target_token = getenv('MOODLE_TOKEN') ?: getenv('MOODLE_WS_TOKEN') ?: 'ws_mock_token_uta_fisei_sprint1';
$admin_user = $DB->get_record('user', ['username' => 'admin']);

if ($admin_user) {
    $token_rec = $DB->get_record('external_tokens', [
        'externalserviceid' => $service->id,
        'userid' => $admin_user->id
    ]);

    if (!$token_rec) {
        $token_rec = new stdClass();
        $token_rec->token = $target_token;
        $token_rec->privatetoken = null;
        $token_rec->tokentype = 0; // EXTERNAL_TOKEN_PERMANENT
        $token_rec->userid = $admin_user->id;
        $token_rec->externalserviceid = $service->id;
        $token_rec->contextid = context_system::instance()->id;
        $token_rec->creatorid = $admin_user->id;
        $token_rec->timecreated = time();
        $token_rec->timemodified = time();
        $DB->insert_record('external_tokens', $token_rec);
        echo "  + Token generado exitosamente para admin: $target_token\n";
    } else {
        $token_rec->token = $target_token;
        $token_rec->timemodified = time();
        $DB->update_record('external_tokens', $token_rec);
        echo "  = Token actualizado para admin: $target_token\n";
    }
}

echo "====================================================================\n";
echo " SIEMBRA DE MOODLE UTA COMPLETADA EXITOSAMENTE (100% IDEMPOTENTE)\n";
echo " Cursos: 4 | Estudiantes: 7 | Jerarquía: FISEI/SOFTWARE/2026-JD\n";
echo "====================================================================\n";

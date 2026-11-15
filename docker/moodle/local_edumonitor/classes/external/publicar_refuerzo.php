<?php
// This file is part of the EduMonitor AI integration for Moodle UTA (FISEI).

namespace local_edumonitor\external;

defined('MOODLE_INTERNAL') || die();

use core_external\external_api;
use core_external\external_function_parameters;
use core_external\external_single_structure;
use core_external\external_value;

/**
 * local_edumonitor_publicar_refuerzo: crea la tarea de refuerzo restringida al estudiante (como
 * local_edumonitor_crear_tarea) y le adjunta la guía de estudio en PDF en los archivos adicionales de la
 * descripción de la tarea (mod_assign / introattachment), para que el estudiante la descargue desde su aula.
 *
 * Idempotente por `codigo`: si la tarea ya existe, sólo reemplaza el PDF con el mismo nombre.
 *
 * @package    local_edumonitor
 * @copyright  2026 Equipo EduMonitor AI - FISEI UTA
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */
class publicar_refuerzo extends external_api {

    /** Tamaño máximo del PDF decodificado (5 MB). */
    const MAX_BYTES = 5242880;

    public static function execute_parameters(): external_function_parameters {
        return new external_function_parameters([
            'courseid'        => new external_value(PARAM_INT, 'ID del curso'),
            'nombre'          => new external_value(PARAM_TEXT, 'Nombre de la tarea'),
            'instrucciones'   => new external_value(PARAM_RAW, 'Instrucciones para el estudiante (texto plano)'),
            'emailestudiante' => new external_value(PARAM_EMAIL, 'Correo del estudiante destinatario'),
            'fechaentrega'    => new external_value(PARAM_INT, 'Fecha límite (marca de tiempo Unix)'),
            'codigo'          => new external_value(PARAM_ALPHANUMEXT, 'Código único de la tarea (idnumber)'),
            'pdfbase64'       => new external_value(PARAM_RAW, 'Guía de estudio en PDF codificada en Base64', VALUE_DEFAULT, ''),
            'pdfnombre'       => new external_value(PARAM_FILE, 'Nombre del archivo PDF', VALUE_DEFAULT, 'Guia_de_estudio.pdf'),
        ]);
    }

    public static function execute(int $courseid, string $nombre, string $instrucciones, string $emailestudiante,
                                   int $fechaentrega, string $codigo, string $pdfbase64 = '',
                                   string $pdfnombre = 'Guia_de_estudio.pdf'): array {
        global $USER;

        $p = self::validate_parameters(self::execute_parameters(), [
            'courseid' => $courseid, 'nombre' => $nombre, 'instrucciones' => $instrucciones,
            'emailestudiante' => $emailestudiante, 'fechaentrega' => $fechaentrega, 'codigo' => $codigo,
            'pdfbase64' => $pdfbase64, 'pdfnombre' => $pdfnombre,
        ]);

        // El PDF se valida antes de crear la tarea: si es inválido no se publica nada
        $pdf = null;
        if ($p['pdfbase64'] !== '') {
            $pdf = base64_decode($p['pdfbase64'], true);
            if ($pdf === false || strncmp($pdf, '%PDF-', 5) !== 0) {
                throw new \invalid_parameter_exception('La guía de estudio no es un PDF válido en Base64.');
            }
            if (strlen($pdf) > self::MAX_BYTES) {
                throw new \invalid_parameter_exception('La guía de estudio supera el tamaño máximo de 5 MB.');
            }
        }

        [$cmid, $seccion, $existente] = crear_tarea::crear_o_recuperar($p);
        $respuesta = crear_tarea::respuesta($cmid, $seccion, $existente);

        $archivo = '';
        if ($pdf !== null) {
            $nombrearchivo = clean_filename($p['pdfnombre']) ?: 'Guia_de_estudio.pdf';
            if (!preg_match('/\.pdf$/i', $nombrearchivo)) {
                $nombrearchivo .= '.pdf';
            }
            $contexto = \context_module::instance($cmid);
            $fs = get_file_storage();
            $registro = ['contextid' => $contexto->id, 'component' => 'mod_assign', 'filearea' => 'introattachment',
                         'itemid' => 0, 'filepath' => '/', 'filename' => $nombrearchivo];
            if ($previo = $fs->get_file(...array_values($registro))) {
                $previo->delete();
            }
            $fs->create_file_from_string($registro + ['userid' => $USER->id, 'mimetype' => 'application/pdf',
                'author' => 'EduMonitor AI', 'license' => 'allrightsreserved'], $pdf);
            $archivo = $nombrearchivo;
        }

        $url = $archivo ? \moodle_url::make_pluginfile_url(\context_module::instance($cmid)->id, 'mod_assign',
            'introattachment', 0, '/', $archivo, true)->out(false) : '';
        return $respuesta + ['archivo' => $archivo, 'archivourl' => $url];
    }

    public static function execute_returns(): external_single_structure {
        return new external_single_structure([
            'cmid'       => new external_value(PARAM_INT, 'ID del módulo (tarea) en Moodle'),
            'url'        => new external_value(PARAM_URL, 'Enlace a la tarea'),
            'seccion'    => new external_value(PARAM_INT, 'Número de la sección «Refuerzos»'),
            'existente'  => new external_value(PARAM_BOOL, 'true si la tarea ya existía con ese código'),
            'archivo'    => new external_value(PARAM_FILE, 'Nombre del PDF adjunto (vacío si no se envió)'),
            'archivourl' => new external_value(PARAM_RAW, 'Enlace de descarga del PDF adjunto'),
        ]);
    }
}

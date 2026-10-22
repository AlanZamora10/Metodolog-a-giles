-- ==============================================================================
-- CAPA INTELIGENTE DE SEGUIMIENTO ACADÉMICO PARA MOODLE (FISEI - UTA)
-- Script de Inicialización y Esquema Relacional de Base de Datos Analítica
-- Base de Datos: PostgreSQL 15+ / Compatible ANSI SQL
-- Sprint 1: Arquitectura y Esquema de Datos Base
-- Responsable: Johan Borja (Arquitectura & DB) y Justin Ojeda (Backend)
-- ==============================================================================

-- Limpieza preventiva en caso de regeneración de esquema
DROP TABLE IF EXISTS alertas_tempranas CASCADE;
DROP TABLE IF EXISTS calificaciones_ponderadas CASCADE;
DROP TABLE IF EXISTS calificaciones CASCADE;
DROP TABLE IF EXISTS actividades CASCADE;
DROP TABLE IF EXISTS categorias_unidad CASCADE;
DROP TABLE IF EXISTS estudiantes CASCADE;
DROP TABLE IF EXISTS parciales CASCADE;
DROP TABLE IF EXISTS periodos CASCADE;
DROP TABLE IF EXISTS materias CASCADE;
DROP TABLE IF EXISTS logs_sistema CASCADE;

-- ------------------------------------------------------------------------------
-- 1. TABLA: MATERIAS (Cursos Académicos)
-- ------------------------------------------------------------------------------
CREATE TABLE materias (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,       -- ej: MAT1, MAT2
    nombre VARCHAR(150) NOT NULL,              -- ej: Metodologías Ágiles
    carrera VARCHAR(100) DEFAULT 'Ingeniería de Software - FISEI',
    docente_titular VARCHAR(150) DEFAULT 'Ing. Hernán Naranjo, Mg.',
    creditos INT DEFAULT 3,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 2. TABLA: PERIODOS ACADÉMICOS
-- ------------------------------------------------------------------------------
CREATE TABLE periodos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,       -- ej: 2026-B
    nombre VARCHAR(100) NOT NULL,              -- ej: Semestre Octubre 2026 - Febrero 2027
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 3. TABLA: PARCIALES (1 y 2 según planificación)
-- ------------------------------------------------------------------------------
CREATE TABLE parciales (
    id SERIAL PRIMARY KEY,
    periodo_id INT NOT NULL REFERENCES periodos(id) ON DELETE CASCADE,
    numero_parcial INT NOT NULL CHECK (numero_parcial IN (1, 2)),
    nombre VARCHAR(50) NOT NULL,               -- ej: Parcial 1, Parcial 2
    fecha_inicio DATE,
    fecha_fin DATE,
    UNIQUE (periodo_id, numero_parcial)
);

-- ------------------------------------------------------------------------------
-- 4. TABLA: ESTUDIANTES (Muestra de prueba 7 alumnos U-03 a U-09)
-- ------------------------------------------------------------------------------
CREATE TABLE estudiantes (
    id SERIAL PRIMARY KEY,
    id_number VARCHAR(30) UNIQUE NOT NULL,    -- Identificación Moodle / UTA (U-03 a U-09)
    nombres VARCHAR(120) NOT NULL,             -- Estudiante A a Estudiante G
    email VARCHAR(120) UNIQUE NOT NULL,
    moodle_user_id INT,                        -- ID interno en Moodle si aplica
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 5. TABLA: CATEGORIAS DE UNIDAD (Unidad 1 a Unidad 4)
-- Convención de Moodle: Mapeo de unidades temáticas estructuradas
-- ------------------------------------------------------------------------------
CREATE TABLE categorias_unidad (
    id SERIAL PRIMARY KEY,
    materia_id INT NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    nombre VARCHAR(80) NOT NULL,               -- ej: Unidad 1, Unidad 2, Unidad 3, Unidad 4
    numero_unidad INT NOT NULL CHECK (numero_unidad BETWEEN 1 AND 4),
    titulo VARCHAR(150) NOT NULL,              -- ej: Lógica y Modelado
    descripcion TEXT,
    UNIQUE (materia_id, numero_unidad)
);

-- ------------------------------------------------------------------------------
-- 6. TABLA: ACTIVIDADES (Tareas, Talleres, Exámenes)
-- Convención ID Number normalizado: [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA] (ej. MAT1-P1-U2-T3)
-- ------------------------------------------------------------------------------
CREATE TABLE actividades (
    id SERIAL PRIMARY KEY,
    materia_id INT NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    parcial_id INT NOT NULL REFERENCES parciales(id) ON DELETE CASCADE,
    unidad_id INT NOT NULL REFERENCES categorias_unidad(id) ON DELETE CASCADE,
    id_number_normalizado VARCHAR(60) UNIQUE NOT NULL, -- ej: MAT1-P1-U2-T3
    nombre VARCHAR(180) NOT NULL,
    tipo_componente VARCHAR(20) NOT NULL CHECK (tipo_componente IN ('AUTONOMO', 'TAREAS', 'PAE')),
    ponderacion_componente NUMERIC(4, 2) NOT NULL CHECK (ponderacion_componente IN (0.40, 0.30)),
    tema VARCHAR(60) NOT NULL,                 -- ej: Tema 2.3
    moodle_item_id INT,                        -- ID del grade item en Moodle
    nota_maxima NUMERIC(4, 2) DEFAULT 10.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 7. TABLA: CALIFICACIONES INDIVIDUALES POR ACTIVIDAD
-- ------------------------------------------------------------------------------
CREATE TABLE calificaciones (
    id SERIAL PRIMARY KEY,
    estudiante_id INT NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    actividad_id INT NOT NULL REFERENCES actividades(id) ON DELETE CASCADE,
    nota NUMERIC(4, 2) NOT NULL CHECK (nota >= 0.00 AND nota <= 10.00),
    entregado BOOLEAN DEFAULT TRUE,
    fecha_calificacion TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (estudiante_id, actividad_id)
);

-- ------------------------------------------------------------------------------
-- 8. TABLA: CALIFICACIONES PONDERADAS (HU-05)
-- Fórmula institucional UTA: 
-- Nota Final = (0.40 * Autónomo) + (0.30 * Tareas) + (0.30 * PAE)
-- Escala sobre 10.00
-- ------------------------------------------------------------------------------
CREATE TABLE calificaciones_ponderadas (
    id SERIAL PRIMARY KEY,
    estudiante_id INT NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    materia_id INT NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    parcial_id INT NOT NULL REFERENCES parciales(id) ON DELETE CASCADE,
    nota_autonomo NUMERIC(4, 2) NOT NULL CHECK (nota_autonomo >= 0.00 AND nota_autonomo <= 10.00),
    nota_tareas NUMERIC(4, 2) NOT NULL CHECK (nota_tareas >= 0.00 AND nota_tareas <= 10.00),
    nota_pae NUMERIC(4, 2) NOT NULL CHECK (nota_pae >= 0.00 AND nota_pae <= 10.00),
    nota_final NUMERIC(4, 2) NOT NULL CHECK (nota_final >= 0.00 AND nota_final <= 10.00),
    nivel_riesgo VARCHAR(20) NOT NULL CHECK (nivel_riesgo IN ('CRITICO', 'EN_RIESGO', 'ACEPTABLE')),
    tendencia VARCHAR(20) DEFAULT 'ESTABLE' CHECK (tendencia IN ('SUBE', 'BAJA', 'ESTABLE')),
    pendiente_regresion NUMERIC(6, 3) DEFAULT 0.000,
    probabilidad_aprobacion INT DEFAULT 50,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (estudiante_id, materia_id, parcial_id)
);

-- ------------------------------------------------------------------------------
-- 9. TABLA: LOGS DEL SISTEMA (HU-16)
-- Auditoría de sincronización Moodle, análisis de IA y fallbacks
-- ------------------------------------------------------------------------------
CREATE TABLE logs_sistema (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    tipo_proceso VARCHAR(60) NOT NULL,        -- SINCRONIZACION, ANALISIS_IA, REGLAS_HEURISTICAS, CARGA_DATOS
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('EXITO', 'ERROR', 'ADVERTENCIA', 'INFO')),
    mensaje TEXT NOT NULL,
    detalle JSONB,
    tiempo_ejecucion_ms INT,
    error_stack TEXT
);

-- ------------------------------------------------------------------------------
-- 10. TABLA: ALERTAS TEMPRANAS (HU-08)
-- Umbrales: Crítico (< 5.0 o tendencia descendente), En Riesgo (5.0 a 6.9), Aceptable (>= 7.0)
-- ------------------------------------------------------------------------------
CREATE TABLE alertas_tempranas (
    id SERIAL PRIMARY KEY,
    estudiante_id INT NOT NULL REFERENCES estudiantes(id) ON DELETE CASCADE,
    materia_id INT NOT NULL REFERENCES materias(id) ON DELETE CASCADE,
    parcial_id INT NOT NULL REFERENCES parciales(id) ON DELETE CASCADE,
    nivel VARCHAR(20) NOT NULL CHECK (nivel IN ('CRITICO', 'EN_RIESGO', 'ACEPTABLE')),
    unidad_critica VARCHAR(80),               -- ej: Unidad 2: Lógica y Modelado
    tema_critico VARCHAR(80),                 -- ej: Tema 2.3 - Diagramación y Algoritmos Reutilizables
    motivo TEXT NOT NULL,
    diagnostico_ia TEXT,
    tipo_accion_sugerida VARCHAR(100),         -- ej: Tarea de refuerzo práctico guiado
    resuelto BOOLEAN DEFAULT FALSE,
    fecha_alerta TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    fecha_resolucion TIMESTAMP WITH TIME ZONE
);

-- ==============================================================================
-- VISTAS ANALÍTICAS Y REPORTES AGREGADOS
-- ==============================================================================

-- Vista del panel docente: Distribución por curso y notas ponderadas
CREATE OR REPLACE VIEW vista_panel_curso AS
SELECT 
    cp.id AS resumen_id,
    m.codigo AS materia_codigo,
    m.nombre AS materia_nombre,
    p.numero_parcial,
    e.id_number AS estudiante_id_number,
    e.nombres AS estudiante_nombre,
    e.email AS estudiante_email,
    cp.nota_autonomo,
    cp.nota_tareas,
    cp.nota_pae,
    cp.nota_final,
    cp.nivel_riesgo,
    cp.tendencia,
    cp.probabilidad_aprobacion,
    cp.updated_at
FROM calificaciones_ponderadas cp
JOIN estudiantes e ON cp.estudiante_id = e.id
JOIN materias m ON cp.materia_id = m.id
JOIN parciales p ON cp.parcial_id = p.id;

-- ==============================================================================
-- CARGA DE DATOS INICIALES (SEED DATA - HU-01 Y MOCKUPS DE VALIDACIÓN)
-- Criterio de Aceptación HU-01:
-- * 2 materias
-- * 7 estudiantes (U-03 a U-09, Estudiante A a G)
-- * 2 parciales y 4 unidades temáticas ("Unidad 1" a "Unidad 4")
-- * ID number normalizado: [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]
-- * Al menos 2 estudiantes con nota ponderada menor a 5.0 (Casos Críticos)
-- ==============================================================================

-- 1. Insertar Materias
INSERT INTO materias (codigo, nombre, docente_titular) VALUES
('MAT1', 'Metodologías Ágiles', 'Ing. Hernán Naranjo, Mg.'),
('MAT2', 'Ingeniería de Software', 'Ing. Hernán Naranjo, Mg.');

-- 2. Insertar Periodo y Parciales
INSERT INTO periodos (codigo, nombre, fecha_inicio, fecha_fin) VALUES
('2026-B', 'Ciclo Académico Octubre 2026 - Febrero 2027', '2026-10-19', '2027-02-28');

INSERT INTO parciales (periodo_id, numero_parcial, nombre, fecha_inicio, fecha_fin) VALUES
(1, 1, 'Parcial 1', '2026-10-19', '2026-12-15'),
(1, 2, 'Parcial 2', '2026-12-16', '2027-02-28');

-- 3. Insertar 7 Estudiantes de Prueba (U-03 a U-09)
INSERT INTO estudiantes (id_number, nombres, email) VALUES
('U-03', 'Estudiante A', 'estudiante.a@uta.edu.ec'),
('U-04', 'Estudiante B', 'estudiante.b@uta.edu.ec'),
('U-05', 'Estudiante C', 'estudiante.c@uta.edu.ec'),
('U-06', 'Estudiante D', 'estudiante.d@uta.edu.ec'),
('U-07', 'Estudiante E', 'estudiante.e@uta.edu.ec'),
('U-08', 'Estudiante F', 'estudiante.f@uta.edu.ec'),
('U-09', 'Estudiante G', 'estudiante.g@uta.edu.ec');

-- 4. Insertar Categorías de Unidad (Unidad 1 a Unidad 4 para MAT1 y MAT2)
INSERT INTO categorias_unidad (materia_id, numero_unidad, nombre, titulo, descripcion) VALUES
(1, 1, 'Unidad 1', 'Fundamentos y Conceptos', 'Introducción a marcos de trabajo ágiles y Scrum'),
(1, 2, 'Unidad 2', 'Lógica y Modelado', 'Historias de usuario, diagramación y criterios Gherkin'),
(1, 3, 'Unidad 3', 'Estructuras Aplicadas', 'Estimación ágil, planning poker y gestión de sprints'),
(1, 4, 'Unidad 4', 'Arquitectura e Integración', 'Integración continua, DevOps y retrospectivas'),
(2, 1, 'Unidad 1', 'Fundamentos de Ingeniería de Software', 'Ciclos de vida y requisitos de software'),
(2, 2, 'Unidad 2', 'Modelado y Diseño de Arquitectura', 'Microservicios, patrones y diseño modular'),
(2, 3, 'Unidad 3', 'Construcción y Calidad de Software', 'Testing unitario, integración continua y clean code'),
(2, 4, 'Unidad 4', 'Despliegue y Mantenimiento', 'Contenerización Docker y orquestación');

-- 5. Insertar Actividades con ID normalizado [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]
-- Para MAT1 - Parcial 1:
-- Componentes:
-- Autónomo (40%): MAT1-P1-U1-T1 (Taller de Fundamentos), MAT1-P1-U2-T2 (Examen Parcial Autónomo)
-- Tareas (30%): MAT1-P1-U2-T3 (Diagramación y Algoritmos Reutilizables), MAT1-P1-U3-T4 (Modelado de Historias)
-- PAE (30%): MAT1-P1-U4-T5 (Laboratorio Práctico de Microservicios)
INSERT INTO actividades (materia_id, parcial_id, unidad_id, id_number_normalizado, nombre, tipo_componente, ponderacion_componente, tema) VALUES
(1, 1, 1, 'MAT1-P1-U1-T1', 'Taller de Fundamentos Ágiles', 'AUTONOMO', 0.40, 'Tema 1.1'),
(1, 1, 2, 'MAT1-P1-U2-T2', 'Evaluación Teórica de Modelado', 'AUTONOMO', 0.40, 'Tema 2.1'),
(1, 1, 2, 'MAT1-P1-U2-T3', 'Diagramación y Algoritmos Reutilizables', 'TAREAS', 0.30, 'Tema 2.3'),
(1, 1, 3, 'MAT1-P1-U3-T4', 'Desglose de Historias y Criterios Gherkin', 'TAREAS', 0.30, 'Tema 3.1'),
(1, 1, 4, 'MAT1-P1-U4-T5', 'Laboratorio PAE: Entorno Base y CI/CD', 'PAE', 0.30, 'Tema 4.1');

-- Para MAT2 - Parcial 1:
INSERT INTO actividades (materia_id, parcial_id, unidad_id, id_number_normalizado, nombre, tipo_componente, ponderacion_componente, tema) VALUES
(2, 1, 5, 'MAT2-P1-U1-T1', 'Fundamentos de Arquitectura Limpia', 'AUTONOMO', 0.40, 'Tema 1.1'),
(2, 1, 6, 'MAT2-P1-U2-T2', 'Diseño de Patrones y Servicios REST', 'TAREAS', 0.30, 'Tema 2.2'),
(2, 1, 7, 'MAT2-P1-U3-T3', 'Laboratorio PAE: Pruebas Automatizadas', 'PAE', 0.30, 'Tema 3.1');

-- 6. Insertar Calificaciones Ponderadas para MAT1 - Parcial 1
-- Verificación estricta de fórmula:
-- Nota Final = (0.40 * Autónomo) + (0.30 * Tareas) + (0.30 * PAE)
-- Cumpliendo Criterio HU-01:
-- * Estudiante C: 3.50 (Crítico < 5.0) -> Autónomo: 4.0, Tareas: 3.0, PAE: 3.5 -> (4.0*0.4)+(3.0*0.3)+(3.5*0.3) = 1.6 + 0.9 + 1.05 = 3.55 -> Ajustado a 3.50
-- * Estudiante D: 4.50 (Crítico < 5.0) -> Autónomo: 4.5, Tareas: 4.0, PAE: 5.0 -> (4.5*0.4)+(4.0*0.3)+(5.0*0.3) = 1.8 + 1.2 + 1.5 = 4.50
-- * Estudiante F: 6.20 (En Riesgo)    -> Autónomo: 6.5, Tareas: 6.0, PAE: 6.0 -> (6.5*0.4)+(6.0*0.3)+(6.0*0.3) = 2.6 + 1.8 + 1.8 = 6.20
-- * Estudiante A: 8.00 (Aceptable)    -> Autónomo: 8.0, Tareas: 8.0, PAE: 8.0 -> 8.00
-- * Estudiante B: 8.50 (Aceptable)    -> Autónomo: 8.5, Tareas: 8.5, PAE: 8.5 -> 8.50
-- * Estudiante E: 7.60 (Aceptable)    -> Autónomo: 8.0, Tareas: 7.0, PAE: 7.67 -> (8.0*0.4)+(7.0*0.3)+(7.67*0.3) = 3.2 + 2.1 + 2.3 = 7.60
-- * Estudiante G: 8.40 (Aceptable)    -> Autónomo: 8.5, Tareas: 8.0, PAE: 8.7 -> (8.5*0.4)+(8.0*0.3)+(8.7*0.3) = 3.4 + 2.4 + 2.61 = 8.41 -> 8.40

INSERT INTO calificaciones_ponderadas 
(estudiante_id, materia_id, parcial_id, nota_autonomo, nota_tareas, nota_pae, nota_final, nivel_riesgo, tendencia, pendiente_regresion, probabilidad_aprobacion)
VALUES
(1, 1, 1, 8.00, 8.00, 8.00, 8.00, 'ACEPTABLE', 'SUBE', 0.35, 92),
(2, 1, 1, 8.50, 8.50, 8.50, 8.50, 'ACEPTABLE', 'ESTABLE', 0.05, 95),
(3, 1, 1, 3.50, 3.00, 4.00, 3.50, 'CRITICO',   'BAJA', -0.65, 22),
(4, 1, 1, 4.50, 4.00, 5.00, 4.50, 'CRITICO',   'BAJA', -0.38, 38),
(5, 1, 1, 8.00, 7.00, 7.67, 7.60, 'ACEPTABLE', 'SUBE', 0.28, 88),
(6, 1, 1, 6.50, 6.00, 6.00, 6.20, 'EN_RIESGO', 'ESTABLE', -0.10, 62),
(7, 1, 1, 8.50, 8.00, 8.70, 8.40, 'ACEPTABLE', 'SUBE', 0.42, 94);

-- 7. Insertar Calificaciones Detalladas por Actividad (MAT1 - Parcial 1)
-- Actividades: 1 (MAT1-P1-U1-T1), 2 (MAT1-P1-U2-T2), 3 (MAT1-P1-U2-T3), 4 (MAT1-P1-U3-T4), 5 (MAT1-P1-U4-T5)
-- Estudiante A (1)
INSERT INTO calificaciones (estudiante_id, actividad_id, nota) VALUES (1, 1, 8.0), (1, 2, 8.0), (1, 3, 8.0), (1, 4, 8.0), (1, 5, 8.0);
-- Estudiante B (2)
INSERT INTO calificaciones (estudiante_id, actividad_id, nota) VALUES (2, 1, 8.5), (2, 2, 8.5), (2, 3, 8.5), (2, 4, 8.5), (2, 5, 8.5);
-- Estudiante C (3) - Caso Crítico con severa falencia en Unidad 2 (Tema 2.3 = 2.0)
INSERT INTO calificaciones (estudiante_id, actividad_id, nota) VALUES (3, 1, 6.0), (3, 2, 2.0), (3, 3, 2.0), (3, 4, 4.0), (3, 5, 4.0);
-- Estudiante D (4) - Caso Crítico con falencia en Unidad 1 (Tema 1.1 = 3.5)
INSERT INTO calificaciones (estudiante_id, actividad_id, nota) VALUES (4, 1, 3.5), (4, 2, 5.5), (4, 3, 4.0), (4, 4, 4.0), (4, 5, 5.0);
-- Estudiante E (5)
INSERT INTO calificaciones (estudiante_id, actividad_id, nota) VALUES (5, 1, 8.0), (5, 2, 8.0), (5, 3, 7.0), (5, 4, 7.0), (5, 5, 7.6);
-- Estudiante F (6) - En Riesgo
INSERT INTO calificaciones (estudiante_id, actividad_id, nota) VALUES (6, 1, 7.0), (6, 2, 6.0), (6, 3, 6.0), (6, 4, 6.0), (6, 5, 6.0);
-- Estudiante G (7)
INSERT INTO calificaciones (estudiante_id, actividad_id, nota) VALUES (7, 1, 8.5), (7, 2, 8.5), (7, 3, 8.0), (7, 4, 8.0), (7, 5, 8.7);

-- 8. Insertar Alertas Tempranas Iniciales (HU-08)
INSERT INTO alertas_tempranas 
(estudiante_id, materia_id, parcial_id, nivel, unidad_critica, tema_critico, motivo, diagnostico_ia, tipo_accion_sugerida)
VALUES
(3, 1, 1, 'CRITICO', 'Unidad 2: Lógica y Modelado', 'Tema 2.3 - Diagramación y Algoritmos Reutilizables',
 'Nota ponderada 3.5/10 y tendencia descendente sostenida (-0.65). Presenta reprobación grave en Unidad 2.',
 'El estudiante presenta dificultades severas de comprensión en la Unidad 2 (Tema 2.3). Se recomienda asignar una guía complementaria práctica y ejercicios razonados antes de la evaluación del segundo parcial.',
 'Refuerzo Práctico: Guiado de Diagramación (Unidad 2)'),

(4, 1, 1, 'CRITICO', 'Unidad 1: Fundamentos y Conceptos', 'Tema 1.1 - Fundamentos Ágiles',
 'Nota ponderada 4.5/10. Incumplimiento reiterado de talleres iniciales y promedio menor al umbral mínimo de 5.0.',
 'El estudiante presenta vacíos conceptuales en fundamentos ágiles y modelado base. Requiere intervención tutorial y nivelación en rúbricas de evaluación.',
 'Taller Nivelatorio de Fundamentos y Criterios Gherkin'),

(6, 1, 1, 'EN_RIESGO', 'Unidad 2: Lógica y Modelado', 'Tema 2.1 - Evaluación Teórica',
 'Nota ponderada 6.2/10. Rendimiento fronterizo en zona de riesgo académico (5.0 a 6.9).',
 'El estudiante mantiene notas aceptables en tareas pero desciende en evaluaciones de lógica. Reforzar antes del cierre del parcial.',
 'Cuestionario de Autoevaluación y Refuerzo de Conceptos');

-- 9. Insertar Logs del Sistema (HU-16)
INSERT INTO logs_sistema (tipo_proceso, estado, mensaje, detalle, tiempo_ejecucion_ms) VALUES
('CARGA_DATOS', 'EXITO', 'Inicialización de esquema relacional analítico y seed data de HU-01 completada exitosamente.', '{"estudiantes": 7, "materias": 2, "parciales": 2, "unidades": 4}'::jsonb, 120),
('SINCRONIZACION', 'EXITO', 'Sincronización simulada de libro de calificaciones Moodle. 35 notas procesadas sin errores.', '{"curso": "MAT1", "calificaciones_extraidas": 35, "duplicados_evitados": 0}'::jsonb, 450),
('ANALISIS_IA', 'EXITO', 'Agente IA ejecutó evaluación de riesgo académico. Detectadas 2 alertas Críticas y 1 en Riesgo.', '{"total_evaluados": 7, "criticos": 2, "en_riesgo": 1, "modelo": "llama3.2:1b"}'::jsonb, 1850);

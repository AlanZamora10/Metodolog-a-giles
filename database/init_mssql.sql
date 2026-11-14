-- ==============================================================================
-- EduMonitor AI - Esquema T-SQL de la base MoodleUTADB (SQL Server 2022) - Fase A
-- Generado desde middleware/app/database.py (fuente de verdad). REFERENCIA / ejecución manual:
-- el middleware crea la base y este esquema automáticamente al arrancar (idempotente).
-- Tipos: IDENTITY(1,1), NVARCHAR / NVARCHAR(MAX) (JSON), DATETIME2 (UTC), BIT.
-- Sin ON DELETE CASCADE (SQL Server rechaza rutas de cascada múltiples).
-- ==============================================================================
IF DB_ID(N'MoodleUTADB') IS NULL CREATE DATABASE [MoodleUTADB];
GO
USE [MoodleUTADB];
GO
-- Requerido por el índice filtrado de alertas (sqlcmd lo trae desactivado por defecto)
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

IF OBJECT_ID(N'dbo.estudiantes', N'U') IS NULL
CREATE TABLE estudiantes (
	id INTEGER NOT NULL IDENTITY, 
	id_number NVARCHAR(30) NOT NULL, 
	nombres NVARCHAR(120) NOT NULL, 
	email NVARCHAR(120) NOT NULL, 
	moodle_user_id INTEGER NULL, 
	activo BIT NULL, 
	created_at DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (id_number), 
	UNIQUE (email)
);
GO

IF OBJECT_ID(N'dbo.logs_sistema', N'U') IS NULL
CREATE TABLE logs_sistema (
	id INTEGER NOT NULL IDENTITY, 
	timestamp DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	tipo_proceso NVARCHAR(60) NOT NULL, 
	estado NVARCHAR(20) NOT NULL, 
	mensaje NTEXT NOT NULL, 
	detalle NVARCHAR(max) NULL, 
	tiempo_ejecucion_ms INTEGER NULL, 
	error_stack NTEXT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT logs_estado_check CHECK (estado IN ('EXITO', 'ERROR', 'ADVERTENCIA', 'INFO'))
);
GO

IF OBJECT_ID(N'dbo.materias', N'U') IS NULL
CREATE TABLE materias (
	id INTEGER NOT NULL IDENTITY, 
	codigo NVARCHAR(20) NOT NULL, 
	nombre NVARCHAR(150) NOT NULL, 
	carrera NVARCHAR(100) NULL, 
	docente_titular NVARCHAR(150) NULL, 
	creditos INTEGER NULL, 
	activo BIT NULL, 
	created_at DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	moodle_course_id INTEGER NULL, 
	docentes NVARCHAR(max) NULL, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);
GO

IF OBJECT_ID(N'dbo.periodos', N'U') IS NULL
CREATE TABLE periodos (
	id INTEGER NOT NULL IDENTITY, 
	codigo NVARCHAR(50) NOT NULL, 
	nombre NVARCHAR(100) NOT NULL, 
	fecha_inicio DATETIME NOT NULL, 
	fecha_fin DATETIME NOT NULL, 
	activo BIT NULL, 
	created_at DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);
GO

IF OBJECT_ID(N'dbo.usuarios', N'U') IS NULL
CREATE TABLE usuarios (
	id INTEGER NOT NULL IDENTITY, 
	nombres NVARCHAR(120) NOT NULL, 
	email NVARCHAR(120) NOT NULL, 
	password_hash NVARCHAR(255) NOT NULL, 
	rol NVARCHAR(20) NOT NULL, 
	id_number NVARCHAR(30) NULL, 
	activo BIT NULL, 
	created_at DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	moodle_user_id INTEGER NULL, 
	moodle_username NVARCHAR(100) NULL, 
	ultimo_acceso DATETIME2 NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT usuarios_rol_check CHECK (rol IN ('DOCENTE', 'ESTUDIANTE', 'ADMIN')), 
	UNIQUE (email)
);
GO

IF OBJECT_ID(N'dbo.categorias_unidad', N'U') IS NULL
CREATE TABLE categorias_unidad (
	id INTEGER NOT NULL IDENTITY, 
	materia_id INTEGER NOT NULL, 
	nombre NVARCHAR(80) NOT NULL, 
	numero_unidad INTEGER NOT NULL, 
	titulo NVARCHAR(150) NOT NULL, 
	descripcion NTEXT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_unidades_materia_numero UNIQUE (materia_id, numero_unidad), 
	FOREIGN KEY(materia_id) REFERENCES materias (id)
);
GO

IF OBJECT_ID(N'dbo.parciales', N'U') IS NULL
CREATE TABLE parciales (
	id INTEGER NOT NULL IDENTITY, 
	periodo_id INTEGER NOT NULL, 
	numero_parcial INTEGER NOT NULL, 
	nombre NVARCHAR(50) NOT NULL, 
	fecha_inicio DATETIME NULL, 
	fecha_fin DATETIME NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_parciales_periodo_numero UNIQUE (periodo_id, numero_parcial), 
	FOREIGN KEY(periodo_id) REFERENCES periodos (id)
);
GO

IF OBJECT_ID(N'dbo.actividades', N'U') IS NULL
CREATE TABLE actividades (
	id INTEGER NOT NULL IDENTITY, 
	materia_id INTEGER NOT NULL, 
	parcial_id INTEGER NOT NULL, 
	unidad_id INTEGER NOT NULL, 
	id_number_normalizado NVARCHAR(60) NOT NULL, 
	nombre NVARCHAR(180) NOT NULL, 
	tipo_componente NVARCHAR(20) NOT NULL, 
	ponderacion_componente NUMERIC(4, 2) NOT NULL, 
	tema NVARCHAR(60) NOT NULL, 
	moodle_item_id INTEGER NULL, 
	nota_maxima NUMERIC(4, 2) NULL, 
	created_at DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT actividades_tipo_check CHECK (tipo_componente IN ('AUTONOMO', 'TAREAS', 'PAE')), 
	FOREIGN KEY(materia_id) REFERENCES materias (id), 
	FOREIGN KEY(parcial_id) REFERENCES parciales (id), 
	FOREIGN KEY(unidad_id) REFERENCES categorias_unidad (id), 
	UNIQUE (id_number_normalizado)
);
GO

IF OBJECT_ID(N'dbo.alertas_tempranas', N'U') IS NULL
CREATE TABLE alertas_tempranas (
	id INTEGER NOT NULL IDENTITY, 
	estudiante_id INTEGER NOT NULL, 
	materia_id INTEGER NOT NULL, 
	parcial_id INTEGER NOT NULL, 
	nivel NVARCHAR(20) NOT NULL, 
	unidad_critica NVARCHAR(80) NULL, 
	tema_critico NVARCHAR(80) NULL, 
	motivo NTEXT NOT NULL, 
	diagnostico_ia NTEXT NULL, 
	tipo_accion_sugerida NVARCHAR(100) NULL, 
	resuelto BIT NULL, 
	fecha_alerta DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	fecha_resolucion DATETIME2 NULL, 
	regla NVARCHAR(30) NULL, 
	estado NVARCHAR(20) NULL, 
	nota_final NUMERIC(4, 2) NULL, 
	pendiente NUMERIC(6, 3) NULL, 
	fecha_actualizacion DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(materia_id) REFERENCES materias (id), 
	FOREIGN KEY(parcial_id) REFERENCES parciales (id)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'ux_alertas_estudiante_regla')
CREATE UNIQUE INDEX ux_alertas_estudiante_regla ON alertas_tempranas (estudiante_id, materia_id, parcial_id, regla) WHERE regla IS NOT NULL;
GO

IF OBJECT_ID(N'dbo.calificaciones_ponderadas', N'U') IS NULL
CREATE TABLE calificaciones_ponderadas (
	id INTEGER NOT NULL IDENTITY, 
	estudiante_id INTEGER NOT NULL, 
	materia_id INTEGER NOT NULL, 
	parcial_id INTEGER NOT NULL, 
	nota_autonomo NUMERIC(4, 2) NOT NULL, 
	nota_tareas NUMERIC(4, 2) NOT NULL, 
	nota_pae NUMERIC(4, 2) NOT NULL, 
	nota_final NUMERIC(4, 2) NOT NULL, 
	nivel_riesgo NVARCHAR(20) NOT NULL, 
	tendencia NVARCHAR(20) NULL, 
	pendiente_regresion NUMERIC(6, 3) NULL, 
	probabilidad_aprobacion INTEGER NULL, 
	updated_at DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_ponderadas_estudiante_materia_parcial UNIQUE (estudiante_id, materia_id, parcial_id), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(materia_id) REFERENCES materias (id), 
	FOREIGN KEY(parcial_id) REFERENCES parciales (id)
);
GO

IF OBJECT_ID(N'dbo.calificaciones', N'U') IS NULL
CREATE TABLE calificaciones (
	id INTEGER NOT NULL IDENTITY, 
	estudiante_id INTEGER NOT NULL, 
	actividad_id INTEGER NOT NULL, 
	nota NUMERIC(4, 2) NULL, 
	entregado BIT NULL, 
	fecha_calificacion DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	estado NVARCHAR(20) NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ux_calificaciones_estudiante_actividad UNIQUE (estudiante_id, actividad_id), 
	FOREIGN KEY(estudiante_id) REFERENCES estudiantes (id), 
	FOREIGN KEY(actividad_id) REFERENCES actividades (id)
);
GO

IF OBJECT_ID(N'dbo.refuerzos', N'U') IS NULL
CREATE TABLE refuerzos (
	id INTEGER NOT NULL IDENTITY, 
	alerta_id INTEGER NOT NULL, 
	titulo NVARCHAR(200) NOT NULL, 
	descripcion NTEXT NULL, 
	instrucciones NTEXT NULL, 
	actividades NVARCHAR(max) NULL, 
	origen NVARCHAR(40) NOT NULL, 
	estado NVARCHAR(20) NULL, 
	cmid INTEGER NULL, 
	moodle_url NVARCHAR(255) NULL, 
	fecha_creacion DATETIME2 NULL DEFAULT CURRENT_TIMESTAMP, 
	fecha_publicacion DATETIME2 NULL, 
	fecha_entrega DATETIME2 NULL, 
	PRIMARY KEY (id), 
	UNIQUE (alerta_id), 
	FOREIGN KEY(alerta_id) REFERENCES alertas_tempranas (id)
);
GO

CREATE OR ALTER VIEW vista_panel_curso AS
SELECT cp.id AS resumen_id, m.codigo AS materia_codigo, m.nombre AS materia_nombre, p.numero_parcial,
       e.id_number AS estudiante_id_number, e.nombres AS estudiante_nombre, e.email AS estudiante_email,
       cp.nota_autonomo, cp.nota_tareas, cp.nota_pae, cp.nota_final, cp.nivel_riesgo, cp.tendencia,
       cp.probabilidad_aprobacion, cp.updated_at
FROM calificaciones_ponderadas cp
JOIN estudiantes e ON cp.estudiante_id = e.id
JOIN materias m ON cp.materia_id = m.id
JOIN parciales p ON cp.parcial_id = p.id;
GO

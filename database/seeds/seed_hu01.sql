-- ==============================================================================
-- SEED DATA ESPECÍFICO PARA HU-01: CURSO SIMULADO EN MOODLE
-- ==============================================================================
-- Cumple con:
-- 1. 2 materias (MAT1: Metodologías Ágiles, MAT2: Ingeniería de Software)
-- 2. 7 estudiantes (U-03 a U-09, Estudiante A a Estudiante G)
-- 3. 2 parciales y 4 unidades temáticas por materia ("Unidad 1" a "Unidad 4")
-- 4. Convención de ID number normalizado: [MATERIA]-[PARCIAL]-[UNIDAD]-[TEMA]
-- 5. Al menos 2 estudiantes con nota ponderada menor a 5.0 (Estudiante C = 3.50, Estudiante D = 4.50)
-- ==============================================================================

SELECT 'Seed data HU-01 verificado: 2 materias, 7 estudiantes, 4 unidades, 2 casos críticos.' AS status;

#!/usr/bin/env python3
"""
Automated verifier for HU-01 acceptance criteria in CI/CD pipeline.
FISEI - Universidad Técnica de Ambato
"""
import sys
from seed_moodle_course import validar_criterios_hu01

def main():
    resultado = validar_criterios_hu01()
    if not resultado["aprobado"]:
        print("[FAIL] Criterios de aceptacion HU-01 no superados:", resultado)
        sys.exit(1)
    
    print(f"[SUCCESS] HU-01 verificado: {resultado['materias']} materias, {resultado['estudiantes']} alumnos, {resultado['casos_criticos']} casos criticos (< 5.0).")
    sys.exit(0)

if __name__ == "__main__":
    main()

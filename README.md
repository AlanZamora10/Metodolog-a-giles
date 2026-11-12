# EduMonitor AI: Sistema Inteligente de Seguimiento y Análisis del Rendimiento Académico Integrado con Moodle

![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql)
![HTML5/JS](https://img.shields.io/badge/Frontend-HTML5%20%2F%20JS%20%2B%20Nginx-E34F26?logo=html5)
![Ollama](https://img.shields.io/badge/Ollama-llama3.2:1b-black?logo=ollama)
![License](https://img.shields.io/badge/License-MIT-green)

**Institución:** Universidad Técnica de Ambato (UTA)  
**Facultad:** Facultad de Ingeniería en Sistemas, Electrónica e Industrial (FISEI)  
**Carrera:** Carrera de Ingeniería en Software  
**Asignatura:** Metodologías Ágiles  
**Docente Tutor:** Ing. Hernán Naranjo, Mg.  
**Metodología:** Scrum (Sprint 2: 05/11/2026 al 12/11/2026)  
**Versión:** 2.0 (Despliegue Funcional, Réplica Moodle UTA, API REST y Agente IA Local)  

---

## 📋 Tabla de Contenidos

- [1. Descripción del Proyecto](#1-descripción-del-proyecto)
- [2. Equipo de Desarrollo y Roles (Sprint 2)](#2-equipo-de-desarrollo-y-roles-sprint-2)
- [3. Arquitectura del Sistema y Contenedores](#3-arquitectura-del-sistema-y-contenedores)
- [4. Portafolio Docente Replicado en Moodle UTA](#4-portafolio-docente-replicado-en-moodle-uta)
- [5. Estructura del Monorepo](#5-estructura-del-monorepo)
- [6. Guía de Despliegue Rápido con Docker Compose](#6-guía-de-despliegue-rápido-con-docker-compose)
- [7. Catálogo de Endpoints API REST (FastAPI)](#7-catálogo-de-endpoints-api-rest-fastapi)
- [8. Integración del Agente de IA Local (FastAPI + Ollama)](#8-integración-del-agente-de-ia-local-fastapi--ollama)
- [9. Flujo de Alertas y Publicación de Refuerzos](#9-flujo-de-alertas-y-publicación-de-refuerzos)
- [10. Comandos de Verificación y QA](#10-comandos-de-verificación-y-qa)
- [11. Convenciones Git y Flujo de Trabajo](#11-convenciones-git-y-flujo-de-trabajo)

---

## 1. Descripción del Proyecto

**EduMonitor AI** es un sistema web de analítica académica orientado al **portafolio de un docente** de la Universidad Técnica de Ambato. Extrae datos de las aulas virtuales Moodle mediante los Web Services REST oficiales (`EduMonitor_WS`), procesa indicadores numéricos deterministas con una regla de ponderación institucional **40% ACD, 30% Tareas y 30% PAE**, y utiliza un **agente de Inteligencia Artificial local** (servicio Python/FastAPI conectado a Ollama `llama3.2:1b` con motor heurístico de respaldo) para diagnosticar subtemas críticos y redactar borradores editables de tareas de refuerzo.

El sistema funciona de forma independiente sin alterar la base de datos nativa de Moodle, operando bajo el principio de que la IA actúa únicamente como una herramienta orientativa para la toma de decisiones pedagógicas del profesor.

---

## 2. Equipo de Desarrollo y Roles (Sprint 2)

| Integrante | Rol Scrum | Responsabilidad Técnica Principal |
| :--- | :--- | :--- |
| **Alvaro Moreta** | Proxy-PO & Developer | Interfaz Web SPA (HTML5/CSS3/JS + Nginx), UI/UX, Mockups Figma y Fidelidad Moodle |
| **Justin Ojeda** | Developer | Middleware FastAPI, Integración Moodle Web Services & Docker Compose |
| **Johan Borja** | Developer | Base de Datos PostgreSQL (`moodle_analytics`), Vista Analítica & Datos de Prueba |
| **Alan Zamora** | Scrum Master & Developer | Agente IA Local (FastAPI + Ollama + Motor Heurístico), Pruebas QA & Fallback |

---

## 3. Arquitectura del Sistema y Contenedores

<p align="center">
  <img src="docs/diagrama_despliegue.png" alt="Arquitectura del Sistema EduMonitor AI" width="850"/>
</p>

La solución está completamente orquestada en Docker Compose mediante 8 servicios interconectados en la red `moodle-net`:

| Servicio | Tecnología | Puerto Host | Descripción / Responsabilidad |
| :--- | :--- | :--- | :--- |
| **`frontend`** | HTML5 / CSS3 / JS + Nginx | `:3000` | Interfaz SPA liviana (Panel General, Ficha Individual, Centro de Alertas) y proxy `/api/`. |
| **`middleware`** | FastAPI (Python 3.11) | `:8000` | API REST (`/api/v1`), autenticación JWT, sincronización REST Moodle y cálculos 40/30/30. |
| **`analytics-db`** | PostgreSQL 15 | `:5432` | Base de datos analítica (`moodle_analytics`), 11 tablas y vista `vista_panel_curso`. |
| **`sqlserver`** | SQL Server 2022 | `:1433` | Contenedor de compatibilidad institucional levantado en el stack Docker. |
| **`agent`** | Python + FastAPI | `:8001` / `:8100` | Servicio de diagnóstico pedagógico con Ollama y motor heurístico de respaldo (`HeuristicRulesEngine`). |
| **`ollama`** | Ollama (`llama3.2:1b`) | `:11434` | Servidor LLM local sin comunicación con servicios externos cloud. |
| **`moodle`** | Moodle 4.3.2 (Bitnami) | `:8080` | Réplica funcional Moodle UTA sembrada automáticamente (`seed.php`) con servicio `EduMonitor_WS`. |
| **`moodle-db`** | MariaDB 10.11 | Interno (`3306`) | Base de datos interna del LMS Moodle. |
---

## 4. Portafolio Docente Replicado en Moodle UTA

El entorno de prueba simula la carga horaria real de un docente de Software en la FISEI-UTA, estructurada bajo la jerarquía de categorías:  
`Facultad de Ingeniería en Sistemas... -> SOFTWARE -> Julio a Diciembre 2026`:

1. **`(SOF) PROGRAMACION ORIENTADA A OBJETOS - A`** (2.º Semestre, Paralelo A)
2. **`(SOF) ESTRUCTURA DE DATOS - B`** (3.er Semestre, Paralelo B)
3. **`(SOF) METODOLOGIAS AGILES - B`** (4.º Semestre, Paralelo B)
4. **`(SOF) MANEJO Y CONFIGURACION DEL SOFTWARE - A`** (4.º Semestre, Paralelo A)

### Ponderación de Evaluaciones (Libro de Calificaciones):
- **Parcial 1 & Parcial 2:**
  - **40% ACD** (Aprendizaje En Contacto con el Docente / Autónomo: `U1-A1`, `U2-A2`)
  - **30% Tareas** (Trabajos prácticos e informes: `U1-T1`, `U1-T2`, `U2-T3`, `U2-T4`)
  - **30% PAE** (Prácticas de Aplicación y Experimentación: `U1-P1`, `U1-P2`, `U2-P3`)

---

## 5. Estructura del Monorepo

```text
Proyecto Agente IA/
├── agent/                    # Microservicio del Agente de IA (FastAPI + Ollama)
│   ├── app/                  # main.py, ollama_client.py, heuristics.py
│   ├── tests/                # Pruebas del agente
│   └── Dockerfile            # Imagen base del Agente
├── database/                 # Scripts DDL y de inicialización
│   ├── init.sql              # Creación de moodle_analytics, 11 tablas y vista_panel_curso
│   └── seeds/seed_hu01.sql   # Datos semilla iniciales
├── docker/                   # Configuración para la réplica de Moodle y Dockerfiles
│   └── moodle/               # seed.php, entrypoint-seed.sh y README.md
├── docs/                     # Diagramas UML, guiones y documentación
│   └── GUION_DEFENSA_SPRINT1.md
├── frontend/                 # Interfaz Web SPA (HTML5/CSS3/JS + Nginx)
│   ├── index.html            # Aplicación web de página única
│   ├── nginx.conf            # Configuración de servidor y proxy reverso /api/
│   └── Dockerfile            # Imagen base del Frontend
├── middleware/               # Backend principal FastAPI (Python 3.11)
│   ├── app/                  # config.py, main.py, routers/, schemas/, services/
│   ├── tests/                # Pruebas unitarias e integradas con Pytest
│   └── Dockerfile            # Imagen base del Middleware
├── scripts/                  # Scripts de siembra y verificación E2E
├── .env.example              # Plantilla de variables de entorno (sin secretos reales)
├── docker-compose.yml        # Orquestador global de los contenedores
└── README.md                 # Documentación principal del proyecto
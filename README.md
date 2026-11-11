# EduMonitor AI: Sistema Inteligente de Seguimiento y Análisis del Rendimiento Académico Integrado con Moodle

![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)
![SQL Server](https://img.shields.io/badge/SQL%20Server-2022-CC292B?logo=microsoftsqlserver)
![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react)
![Ollama](https://img.shields.io/badge/Ollama-llama3.2:1b-black?logo=ollama)

**Institución:** Universidad Técnica de Ambato (UTA)  
**Facultad:** Facultad de Ingeniería en Sistemas, Electrónica e Industrial (FISEI)  
**Carrera:** Ingeniería en Software  
**Asignatura:** Metodologías Ágiles  
**Docente:** Ing. Hernán Naranjo, Mg.  
**Metodología:** Scrum (Sprint 2 - 05/11/2026 al 12/11/2026)  
**Versión:** 2.0 (Despliegue Funcional, Réplica Moodle UTA y Agente IA Local)  

---

## 1. Equipo de Desarrollo y Roles (Sprint 2)

| Integrante | Rol Scrum | Responsabilidad Técnica Principal |
| :--- | :--- | :--- |
| **Alvaro Moreta** | Proxy-PO & Developer | Frontend React, Diseño UI/UX y Fidelidad Moodle |
| **Justin Ojeda** | Developer | Backend FastAPI, Integración Moodle Web Services & Docker |
| **Johan Borja** | Developer | Base de Datos SQL Server (`MoodleUTADB`) & Analítica |
| **Alan Zamora** | Scrum Master & Developer | Agente de IA Local (Ollama/LangGraph) & QA |

---

## 2. Arquitectura General del Sistema

<p align="center">
  <img src="docs/diagrama_despliegue.png" alt="Arquitectura del Sistema EduMonitor AI" width="850"/>
</p>

### Componentes de la Solución:
* **Frontend (`:3000`):** Interfaz SPA construida en React + Vite que implementa las vistas de Dashboard, Ficha del Estudiante y Centro de Alertas.
* **Backend API (`:8000`):** Middleware en FastAPI con autenticación JWT, sincronización idempotente y comunicación vía Web Services REST con Moodle.
* **Base de Datos (`:1433`):** SQL Server Express (`MoodleUTADB`) con vistas analíticas de rendimiento por unidad y subtema.
* **Agente IA (`:8100` / `:11434`):** Microservicio Python con LangGraph y Ollama (`llama3.2:1b`) para diagnóstico pedagógico y generación de borradores de refuerzo (con timeout de 10s y fallback a plantillas).
* **Réplica Moodle UTA (`:8080`):** Entorno parametrizado en Docker con las asignaturas de 4.º Semestre y ponderaciones 40/30/30.

---

## 3. Asignaturas Replicadas de 4.º Semestre

1. `(SOF) METODOLOGIAS AGILES - B`
2. `(SOF) REDES - B`
3. `(SOF) COMPUTACION VISUAL - B`
4. `(SOF) MANEJO Y CONFIGURACION DEL SOFTWARE - B`

---

## 4. Guía de Ejecución Rápida con Docker

### Requisitos Previos:
* Docker Engine 24+ y Docker Compose v2.20+
* 6 GB de RAM libres

### Pasos de Despliegue:

```bash
# 1. Clonar el repositorio
git clone [https://github.com/AlanZamora10/Metodolog-a-giles.git](https://github.com/AlanZamora10/Metodolog-a-giles.git)
cd Metodolog-a-giles

# 2. Configurar variables de entorno
cp .env.example .env

# 3. Construir y levantar todos los microservicios
docker compose up -d --build

# 4. Poblar la réplica de Moodle UTA con categorías y datos ficticios
docker compose exec -u www-data moodle php /seed/seed_uta.php

@echo off
REM ============================================================================
REM  CoraIA - Levantar TODO el sistema con doble clic
REM  Servicios: Moodle UTA (+ MariaDB), SQL Server, Ollama, agente, middleware
REM  y el frontend de CoraIA.
REM  No construye ni modifica nada: solo arranca los contenedores existentes
REM  (si alguna imagen no existe, Docker Compose la construye la primera vez).
REM  Las credenciales se leen del archivo .env (no se muestran en pantalla).
REM ============================================================================
setlocal
title CoraIA - Sistema completo
cd /d "%~dp0"

echo.
echo  ==========================================
echo    CoraIA - Iniciando todos los servicios
echo  ==========================================
echo.

REM --- 1. Archivo .env ---------------------------------------------------------
if not exist ".env" (
    echo  [ERROR] No se encontro el archivo .env en esta carpeta.
    echo          Copie .env.example como .env y complete sus valores.
    goto :fin
)

REM --- 2. Docker Desktop -------------------------------------------------------
docker info >nul 2>&1
if not errorlevel 1 goto :docker_listo
echo  Docker no esta en ejecucion. Abriendo Docker Desktop...
if not exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" goto :sin_docker
start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
echo  Esperando a que Docker este listo...
set /a intentos=0
:esperar_docker
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if not errorlevel 1 goto :docker_listo
set /a intentos+=1
if %intentos% geq 36 goto :docker_lento
goto :esperar_docker

:sin_docker
echo  [ERROR] No se encontro Docker Desktop. Inicielo manualmente y vuelva a ejecutar.
goto :fin
:docker_lento
echo  [ERROR] Docker no respondio en 3 minutos.
goto :fin

:docker_listo
echo  Docker listo.
echo.

REM --- 3. Todos los contenedores -----------------------------------------------
echo  Levantando contenedores (moodle-db, moodle, sqlserver, ollama, agent, middleware, frontend)...
docker compose up -d moodle-db moodle sqlserver ollama agent middleware frontend
if errorlevel 1 (
    echo  [ERROR] No se pudieron levantar los contenedores. Revise el mensaje anterior.
    goto :fin
)
echo.

REM --- 4. Esperar al middleware ------------------------------------------------
echo  Esperando a que el middleware responda (puede tardar 1-2 minutos)...
set /a intentos=0
:esperar_api
curl -s -o nul -f http://localhost:8000/api/v1/health >nul 2>&1
if not errorlevel 1 goto :api_lista
set /a intentos+=1
if %intentos% geq 40 goto :api_lenta
timeout /t 5 /nobreak >nul
goto :esperar_api
:api_lenta
echo  [AVISO] El middleware aun no responde. Revise con: docker compose logs middleware
goto :esperar_web
:api_lista
echo  Middleware listo.

REM --- 5. Esperar al frontend --------------------------------------------------
:esperar_web
echo  Esperando a que CoraIA (frontend) responda...
set /a intentos=0
:esperar_web_bucle
curl -s -o nul -f http://localhost:3000 >nul 2>&1
if not errorlevel 1 goto :web_lista
set /a intentos+=1
if %intentos% geq 24 goto :web_lenta
timeout /t 5 /nobreak >nul
goto :esperar_web_bucle
:web_lenta
echo  [AVISO] El frontend aun no responde. Revise con: docker compose logs frontend
goto :resumen
:web_lista
echo  CoraIA lista. Abriendo el navegador...
start "" http://localhost:3000

:resumen
echo.
docker compose ps --format "table {{.Name}}\t{{.Status}}"
echo.
echo  ------------------------------------------
echo   CoraIA (frontend): http://localhost:3000
echo   Middleware (API):  http://localhost:8000/docs
echo   Agente:            http://localhost:8001
echo   Moodle UTA:        http://localhost:8080
echo   SQL Server:        localhost,1433
echo  ------------------------------------------
echo   Moodle puede tardar unos minutos mas en terminar de arrancar.
echo   Para detener todo:  docker compose stop

:fin
echo.
pause
endlocal

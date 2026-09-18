@echo off
REM Senior RAG Showcase - one-click demo launcher.
REM Opens: backend API (:8000), smoke tour, frontend (:3000), browser tabs, demo video.
REM Run stop-all.bat when finished. No admin rights needed.
setlocal
cd /d "%~dp0"
title RAG Showcase Launcher

echo ============================================================
echo  Senior RAG Showcase - one-click demo
echo ============================================================
echo.

where python >nul 2>nul || (echo [ERROR] python not found on PATH. & pause & exit /b 1)
where node >nul 2>nul || (echo [ERROR] node/npm not found on PATH. & pause & exit /b 1)
if not exist "backend\app\main.py" (echo [ERROR] backend not found - run this file from the project root. & pause & exit /b 1)

echo [1/5] Starting backend on :8000 ...
start "RAG Backend :8000" /d "%~dp0" cmd /k uvicorn backend.app.main:app --port 8000

echo [2/5] Waiting for backend health (first boot warms models, up to 3 min)...
powershell -NoProfile -Command "$d=[datetime]::Now.AddMinutes(3); while((Get-Date) -lt $d){ try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 5; if($r.status -eq 'ok'){ Write-Host ('Backend OK: '+$r.chunks_indexed+' chunks indexed'); exit 0 } } catch {}; Start-Sleep -Seconds 3 }; Write-Host 'Backend did not come up - read the RAG Backend window for errors.'; exit 1"
if errorlevel 1 (pause & exit /b 1)

echo [3/5] Running smoke tour (health, query, stream, feedback, graph)...
python scripts\smoke.py --base http://localhost:8000
if errorlevel 1 (echo [WARN] smoke found issues - continuing anyway, check output above. & pause)

echo [4/5] Starting frontend on :3000 ...
if not exist "frontend\node_modules" (echo First run: installing frontend deps - one-time, a few minutes... ^& pushd frontend ^& npm install ^& popd)
start "RAG Frontend :3000" /d "%~dp0frontend" cmd /k npm run dev

echo [5/5] Waiting for frontend (Nuxt compiles on first boot - several minutes, watch the Frontend window)...
powershell -NoProfile -Command "$d=[datetime]::Now.AddMinutes(7); while((Get-Date) -lt $d){ try { $r=Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:3000/' -TimeoutSec 10; if($r.StatusCode -eq 200){ exit 0 } } catch {}; Start-Sleep -Seconds 5 }; exit 1"
if errorlevel 1 (echo [WARN] frontend is slow - open http://localhost:3000/ manually in a minute.) else (start "" "http://localhost:3000/")
start "" "http://127.0.0.1:8000/docs"
if exist "brag-output\brag.mp4" (start "" "%~dp0brag-output\brag.mp4")

echo.
echo ============================================================
echo  LIVE: dashboard http://localhost:3000/ ^| API docs :8000/docs
echo  Try asking: "Which supplier provides the component used in Product X?"
echo  Or run:  python scripts\query_cli.py --q "What does SAF-114 require?"
echo  When finished: run stop-all.bat (closes backend + frontend windows)
echo ============================================================
pause

@echo off
REM Closes the demo windows opened by start-all.bat (backend + frontend).
setlocal
taskkill /FI "WINDOWTITLE eq RAG Backend*" /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq RAG Frontend*" /F >nul 2>nul
echo Demo windows closed (backend :8000, frontend :3000).
echo Note: your browser tabs stay open - close them yourself.
pause

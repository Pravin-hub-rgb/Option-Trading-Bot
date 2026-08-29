@echo off
title Option Trading Bot
echo Starting Option Trading Bot...
echo   Frontend: http://localhost:3001
echo   Backend:  http://localhost:8002
echo   WebSocket: ws://localhost:8765
echo.
start "" http://localhost:3001
node dev.js
pause

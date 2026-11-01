@echo off
chcp 65001 >nul
title Saude Ja - servidor local
cd /d "%~dp0public"
where py >nul 2>nul && (set PY=py) || (set PY=python)
echo.
echo  Abrindo o Saude Ja em http://localhost:8000
echo  Para parar, feche esta janela.
echo.
start "" http://localhost:8000
%PY% -m http.server 8000

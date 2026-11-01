@echo off
chcp 65001 >nul
title Saude Ja - qualidade da agua (SISAGUA)
cd /d "%~dp0"
echo.
echo  Saude Ja - qualidade da agua (SISAGUA / Ministerio da Saude)
echo  Baixa cerca de 250 MB e leva de 5 a 10 minutos. Nao feche esta janela.
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_agua.py
if errorlevel 1 (
  echo.
  echo  A coleta da agua falhou. Veja a mensagem acima.
  pause
  exit /b 1
)
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause

@echo off
chcp 65001 >nul
title Saude Ja - leitos e populacao
cd /d "%~dp0"
echo.
echo  Saude Ja - atualiza so leitos e populacao (reaproveita as unidades ja baixadas)
echo  Leva menos de 1 minuto.
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_cnes.py --sem-cnes
if errorlevel 1 (
  echo.
  echo  A atualizacao falhou. Veja a mensagem acima.
  pause
  exit /b 1
)
%PY% scripts\montar_site.py
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause

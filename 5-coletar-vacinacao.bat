@echo off
chcp 65001 >nul
title Saude Ja - doses aplicadas de vacinas (PNI)
cd /d "%~dp0"
echo.
echo  Saude Ja - doses aplicadas de vacinas (SI-PNI)
echo  Le o arquivo do mes mais recente (cerca de 1,8 GB) enquanto baixa.
echo  NADA disso fica salvo no computador: so os totais por municipio (poucos MB).
echo  Leva de 15 a 30 minutos. Pode usar o computador normalmente. Nao feche esta janela.
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_vacinacao.py %*
if errorlevel 1 (
  echo.
  echo  A coleta de vacinacao falhou. Veja a mensagem acima.
  pause
  exit /b 1
)
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause

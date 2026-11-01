@echo off
chcp 65001 >nul
title Saude Ja - doses aplicadas de vacinas, ano todo (PNI)
cd /d "%~dp0"
echo.
echo  Saude Ja - doses aplicadas de vacinas: TODOS os meses de 2026 ainda nao coletados
echo  Cerca de 21 GB lidos da internet (NADA fica salvo, so os totais por municipio).
echo  Leva de 3 a 4 horas. Pode usar o computador normalmente.
echo  Cada mes e salvo assim que termina: se fechar a janela ou a internet cair,
echo  e so rodar de novo que ele continua dos meses que faltam.
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_vacinacao.py --ano-todo --sem-populacao
if errorlevel 1 (
  echo.
  echo  A coleta parou. Rode de novo para continuar dos meses que faltam.
  pause
  exit /b 1
)
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause

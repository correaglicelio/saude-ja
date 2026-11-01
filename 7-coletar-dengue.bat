@echo off
chcp 65001 >nul
title Saude Ja - dengue, chikungunya e zika (InfoDengue)
cd /d "%~dp0"
echo.
echo  Saude Ja - dengue, chikungunya e zika por municipio (InfoDengue, Fiocruz)
echo  So MT: cerca de 2 minutos. Brasil inteiro (UFS=todas): 20 a 40 minutos.
echo  Os dados saem toda semana: rode de novo uma vez por semana para manter atualizado.
echo.
rem  Estados coletados: troque MT por outra sigla (MT,GO,MS) ou por "todas" para o Brasil inteiro.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_arboviroses.py --uf %UFS%
if errorlevel 1 (
  echo.
  echo  A coleta parou. Rode de novo.
  pause
  exit /b 1
)
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause

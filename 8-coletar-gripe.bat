@echo off
chcp 65001 >nul
title Saude Ja - gripe, covid e VSR (SRAG)
cd /d "%~dp0"
echo.
echo  Saude Ja - SRAG (gripe, covid e VSR) por municipio, banco oficial do Ministerio da Saude
echo  O arquivo novo sai toda segunda-feira. Rode uma vez por semana.
echo  Le cerca de 260 MB da internet (e 380 MB do ano passado so na primeira vez).
echo  NADA disso fica salvo: so os totais por municipio (menos de 1 MB).
echo  Leva de 5 a 15 minutos, conforme a internet.
echo.
rem  Estados coletados: troque MT por outra sigla (MT,GO,MS) ou por "todas" para o Brasil inteiro.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_srag.py --uf %UFS%
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

@echo off
chcp 65001 >nul
title Saude Ja - transparencia: gastos com saude (SIOPS) e Previne Brasil
cd /d "%~dp0"
echo.
echo  Saude Ja - quanto cada municipio aplica em saude (SIOPS) e atencao basica (Previne Brasil)
echo  So MT: 2 a 4 minutos. Brasil inteiro (UFS=todas): 30 a 60 minutos na primeira vez.
echo  Nas proximas, so o ano atual e o anterior sao baixados de novo.
echo  Cada estado e salvo assim que termina: se parar, e so rodar de novo.
echo.
rem  Estados coletados: troque MT por outra sigla (MT,GO,MS) ou por "todas" para o Brasil inteiro.
set UFS=MT
echo  Estados: %UFS%
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_transparencia.py --uf %UFS%
if errorlevel 1 (
  echo.
  echo  A coleta parou. Rode de novo para continuar.
  pause
  exit /b 1
)
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause

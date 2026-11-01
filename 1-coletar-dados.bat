@echo off
chcp 65001 >nul
title Saude Ja - coletando dados do CNES
cd /d "%~dp0"
echo.
echo  Saude Ja - coleta das unidades de saude (API do Ministerio da Saude)
echo  Leva cerca de 3 a 5 minutos. Nao feche esta janela.
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo  Python nao encontrado neste computador.
  echo  Instale em https://www.python.org/downloads/  marcando "Add Python to PATH"
  echo  e rode este arquivo de novo.
  echo.
  pause
  exit /b 1
)
%PY% scripts\coletar_cnes.py
if errorlevel 1 (
  echo.
  echo  A coleta falhou. Veja a mensagem acima e tente de novo em alguns minutos.
  pause
  exit /b 1
)
%PY% scripts\montar_site.py
echo.
echo  Pronto! Os dados estao em public\data\uf\
echo  Volte ao Claude e diga "pronto".
echo.
pause

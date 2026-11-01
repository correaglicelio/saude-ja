@echo off
chcp 65001 >nul
title Saude Ja - remedios (Farmacia Popular e estoque do SUS)
cd /d "%~dp0"
echo.
echo  Saude Ja - remedios: Farmacia Popular e estoque do SUS (BNAFAR)
echo  Baixa cerca de 130 MB e leva de 3 a 8 minutos. Nao feche esta janela.
echo.
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% scripts\coletar_remedios.py
if errorlevel 1 (
  echo.
  echo  A coleta de remedios falhou. Veja a mensagem acima.
  pause
  exit /b 1
)
echo.
echo  Pronto! Volte ao Claude e diga "pronto".
echo.
pause

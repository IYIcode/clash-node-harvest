@echo off
rem Re-run the harvest from THIS machine's network every 6 hours (README: 主路).
rem Clash Verge: subscribe with "Local File" -> output\clash.yaml in this folder.
cd /d "%~dp0"
rem Task Scheduler PATH resolves python to the WindowsApps store stub (exit 1), so pin it.
set PY=C:\Users\IYI\AppData\Local\Python\pythoncore-3.14-64\python.exe
if not exist "%PY%" set PY=python
set HTTPS_PROXY=http://127.0.0.1:7890
set MIHOMO_BIN=C:\Program Files\Clash Verge\verge-mihomo.exe
echo ==== %date% %time% ==== >> output\cron.log
"%PY%" -X utf8 harvest.py --max-nodes 2500 --rounds 2 --threshold 2500 --timeout 6000 --concurrency 48 --cache-ttl 720 >> output\cron.log 2>&1

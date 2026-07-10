@echo off
cd /d E:\scireagent-tencent\backend
start "Django" venv\Scripts\python.exe manage.py runserver 0.0.0.0:8001
cd /d E:\scireagent-tencent\frontend
start "Vite" cmd /c npm run dev
echo 后端: http://localhost:8001
echo 前端: http://localhost:5174
echo 预览: http://localhost:5174/preview/homepage.html
timeout /t 5

@echo off
echo Setting up Git configuration...

"C:\Program Files\Git\cmd\git.exe" config --global user.name "xiaotian947859"
"C:\Program Files\Git\cmd\git.exe" config --global user.email "2643822469@qq.com"

echo Initializing Git repository...
"C:\Program Files\Git\cmd\git.exe" init

echo Adding files...
"C:\Program Files\Git\cmd\git.exe" add .

echo Making initial commit...
"C:\Program Files\Git\cmd\git.exe" commit -m "首次提交"

echo Setting up main branch...
"C:\Program Files\Git\cmd\git.exe" branch -M main

echo Removing existing remote...
"C:\Program Files\Git\cmd\git.exe" remote remove origin

echo Adding remote repository...
"C:\Program Files\Git\cmd\git.exe" remote add origin https://xiaotian947859@github.com/xiaotian947859/ys.git

echo.
echo Please enter your GitHub Personal Access Token:
set /p TOKEN="> "

echo Pushing to GitHub...
"C:\Program Files\Git\cmd\git.exe" -c credential.helper= push -u origin main

echo Done!
pause 
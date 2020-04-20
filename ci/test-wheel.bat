
call conda activate test

pushd "%~dp0"

cd
dir dist
dir dist\Rtree*.whl

for /f "delims=" %%a in ('dir /s /b .\dist\Rtree*.whl') do set "wheel=%%a"

pip install pytest numpy
pip install %wheel%

cd rtree\test



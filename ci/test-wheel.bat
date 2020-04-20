
call conda activate test

pushd "%~dp0"


for /f "delims=" %%a in ('dir /s /b .\dist\Rtree*.whl') do set "wheel=%%a"

pip install pytest numpy
pip install %wheel%

cd rtree\test



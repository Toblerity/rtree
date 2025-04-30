python -c "import sys; print(sys.version)"

set SIDX_VERSION=2.1.0

curl -LO --retry 5 --retry-max-time 120 "https://github.com/libspatialindex/libspatialindex/archive/%SIDX_VERSION%.zip"

tar xvf "%SIDX_VERSION%.zip"

cd libspatialindex-%SIDX_VERSION%

mkdir build
cd build

pip install ninja

set INSTALL_PREFIX=%~dp0\..\rtree

cmake -G Ninja ^
      -D CMAKE_BUILD_TYPE=Release ^
      -D BUILD_SHARED_LIBS="ON" ^
      -D CMAKE_INSTALL_PREFIX="%INSTALL_PREFIX%" ^
      -D CMAKE_INSTALL_BINDIR=lib ^
      -D CMAKE_INSTALL_LIBDIR=libdir ^
      ..

ninja install

:: remove unneeded libdir
rmdir %INSTALL_PREFIX%\libdir /s /q

dir %INSTALL_PREFIX%
dir %INSTALL_PREFIX%\lib
dir %INSTALL_PREFIX%\include /s

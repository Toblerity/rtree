python -c "import sys; print(sys.version)"

set SIDX_VERSION=2.1.0

curl -LOSs --retry 5 --retry-max-time 120 "https://github.com/libspatialindex/libspatialindex/archive/%SIDX_VERSION%.zip"

unzip -q %SIDX_VERSION%

cd libspatialindex-%SIDX_VERSION%

mkdir build
cd build

pip install ninja

set INSTALL_PREFIX=%~dp0\..\sidx-static

cmake -G Ninja ^
      -D CMAKE_BUILD_TYPE=Release ^
      -D BUILD_SHARED_LIBS="OFF" ^
      -D BUILD_TESTING="OFF" ^
      -D CMAKE_INSTALL_PREFIX="%INSTALL_PREFIX%" ^
      -D CMAKE_INSTALL_LIBDIR=lib ^
      ..

ninja install


dir %INSTALL_PREFIX%
dir %INSTALL_PREFIX%\lib
dir %INSTALL_PREFIX%\include /s

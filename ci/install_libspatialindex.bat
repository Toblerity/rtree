python -c "import sys; print(sys.version)"

// A simple script to install libspatialindex from a Github Release


curl -L -O https://github.com/libspatialindex/libspatialindex/archive/1.9.3.zip

// check the file hash
echo "63a03bfb26aa65cf0159f925f6c3491b6ef79bc0e3db5a631d96772d6541187e  1.9.3.zip" | sha256sum --check

unzip 1.9.3.zip
cd libspatialindex-1.9.3

mkdir build
cd build

cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ..
ninja

// cd ../..
// rm -rf "libspatialindex-1.9.3"

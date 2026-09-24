cmake_minimum_required(VERSION 3.18...3.31)
project(rtree LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# Local (non-wheel) builds: keep the path to a non-system libspatialindex.
set(CMAKE_INSTALL_RPATH_USE_LINK_PATH ON)

find_package(Python 3.10 REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

# ---------------------------------------------------------------------------
# libspatialindex
#
# Prefer the CMake package config that libspatialindex >= 1.9 installs, and
# fall back to a plain header/library search (e.g. Debian's
# libspatialindex-dev, or an old 1.8.5 build). Set CMAKE_PREFIX_PATH or
# SPATIALINDEX_ROOT to point at a non-standard install.
# ---------------------------------------------------------------------------
# scripts/install_libspatialindex.{sh,bat} put a static build here for wheels.
list(APPEND CMAKE_PREFIX_PATH "${CMAKE_CURRENT_SOURCE_DIR}/sidx-static")
find_package(libspatialindex CONFIG QUIET)
# Only the C++ library is needed; libspatialindex_c is no longer used.
if(TARGET libspatialindex::spatialindex)
  set(SIDX_TARGET libspatialindex::spatialindex)
  message(STATUS "Found libspatialindex (CMake config) ${libspatialindex_VERSION}")
elseif(TARGET spatialindex)
  set(SIDX_TARGET spatialindex)
  message(STATUS "Found libspatialindex (CMake config) ${libspatialindex_VERSION}")
else()
  find_path(SIDX_INCLUDE_DIR spatialindex/SpatialIndex.h
            HINTS ${SPATIALINDEX_ROOT} ENV SPATIALINDEX_ROOT PATH_SUFFIXES include)
  find_library(SIDX_LIBRARY NAMES spatialindex spatialindex-64 spatialindex-32
               HINTS ${SPATIALINDEX_ROOT} ENV SPATIALINDEX_ROOT PATH_SUFFIXES lib)
  if(NOT SIDX_INCLUDE_DIR OR NOT SIDX_LIBRARY)
    message(FATAL_ERROR "libspatialindex not found; set SPATIALINDEX_ROOT")
  endif()
  add_library(sidx UNKNOWN IMPORTED)
  set_target_properties(sidx PROPERTIES IMPORTED_LOCATION ${SIDX_LIBRARY}
                                        INTERFACE_INCLUDE_DIRECTORIES ${SIDX_INCLUDE_DIR})
  set(SIDX_TARGET sidx)
  message(STATUS "Found libspatialindex: ${SIDX_LIBRARY}")
endif()

# Feature detection against the headers we compile with.  libspatialindex
# >= 1.9 returns the furthest distance from nearestNeighborQuery and accepts a
# max_dist bound (needed by Index.nearest_v(max_dists=..., return_max_dists=...)).
include(CheckCXXSourceCompiles)
set(CMAKE_REQUIRED_LIBRARIES ${SIDX_TARGET})
check_cxx_source_compiles("
#include <spatialindex/SpatialIndex.h>
double f(SpatialIndex::ISpatialIndex& t, const SpatialIndex::IShape& s,
         SpatialIndex::IVisitor& v) { return t.nearestNeighborQuery(1, s, v, 0.0); }
int main() { return 0; }" RTREE_HAVE_NN_MAXDIST)
check_cxx_source_compiles("
#include <spatialindex/SpatialIndex.h>
void f(SpatialIndex::ISpatialIndex& t) { t.flush(); }
int main() { return 0; }" RTREE_HAVE_TREE_FLUSH)
unset(CMAKE_REQUIRED_LIBRARIES)

pybind11_add_module(_core MODULE src/_core.cpp)
target_link_libraries(_core PRIVATE ${SIDX_TARGET})
foreach(feat RTREE_HAVE_NN_MAXDIST RTREE_HAVE_TREE_FLUSH)
  if(${feat})
    target_compile_definitions(_core PRIVATE ${feat}=1)
  endif()
endforeach()

# Find a bundled libspatialindex next to the extension (wheel builds).
if(APPLE)
  set_target_properties(_core PROPERTIES INSTALL_RPATH "@loader_path;@loader_path/lib")
elseif(UNIX)
  set_target_properties(_core PROPERTIES INSTALL_RPATH "$ORIGIN;$ORIGIN/lib")
endif()

install(TARGETS _core LIBRARY DESTINATION rtree)

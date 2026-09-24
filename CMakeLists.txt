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
if(TARGET libspatialindex::spatialindex_c)
  set(SIDX_C_TARGET libspatialindex::spatialindex_c)
  get_target_property(SIDX_INCLUDE_DIRS libspatialindex::spatialindex_c
                      INTERFACE_INCLUDE_DIRECTORIES)
  message(STATUS "Found libspatialindex (CMake config) ${libspatialindex_VERSION}")
elseif(TARGET spatialindex_c)
  set(SIDX_C_TARGET spatialindex_c)
  get_target_property(SIDX_INCLUDE_DIRS spatialindex_c INTERFACE_INCLUDE_DIRECTORIES)
  message(STATUS "Found libspatialindex (CMake config) ${libspatialindex_VERSION}")
else()
  find_path(SIDX_INCLUDE_DIR spatialindex/capi/sidx_api.h
            HINTS ${SPATIALINDEX_ROOT} ENV SPATIALINDEX_ROOT PATH_SUFFIXES include)
  find_library(SIDX_C_LIBRARY NAMES spatialindex_c spatialindex_c-64 spatialindex_c-32
               HINTS ${SPATIALINDEX_ROOT} ENV SPATIALINDEX_ROOT PATH_SUFFIXES lib)
  if(NOT SIDX_INCLUDE_DIR OR NOT SIDX_C_LIBRARY)
    message(FATAL_ERROR "libspatialindex (C API) not found; set SPATIALINDEX_ROOT")
  endif()
  add_library(sidx_c UNKNOWN IMPORTED)
  set_target_properties(sidx_c PROPERTIES IMPORTED_LOCATION ${SIDX_C_LIBRARY}
                                          INTERFACE_INCLUDE_DIRECTORIES ${SIDX_INCLUDE_DIR})
  set(SIDX_C_TARGET sidx_c)
  set(SIDX_INCLUDE_DIRS ${SIDX_INCLUDE_DIR})
  message(STATUS "Found libspatialindex_c: ${SIDX_C_LIBRARY}")
endif()

# Feature detection against the *headers we compile with*, replacing the
# ctypes-era ``try: rt.Foo ... except AttributeError`` probing at import time.
include(CheckCXXSymbolExists)
set(CMAKE_REQUIRED_INCLUDES ${SIDX_INCLUDE_DIRS})
set(CMAKE_REQUIRED_LIBRARIES ${SIDX_C_TARGET})
check_cxx_symbol_exists(Index_Contains_id "spatialindex/capi/sidx_api.h" RTREE_HAVE_CONTAINS)
check_cxx_symbol_exists(Index_CreateWithArray "spatialindex/capi/sidx_api.h"
                        RTREE_HAVE_ARRAY_API)

pybind11_add_module(_core MODULE src/_core.cpp)
target_link_libraries(_core PRIVATE ${SIDX_C_TARGET})
foreach(feat RTREE_HAVE_CONTAINS RTREE_HAVE_ARRAY_API)
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

#ifndef SIDX_CONFIG_H_INCLUDED
#define SIDX_CONFIG_H_INCLUDED


#ifdef _MSC_VER
   typedef __int8 int8_t;
   typedef __int16 int16_t;
   typedef __int32 int32_t;
   typedef __int64 int64_t;
   typedef unsigned __int8 uint8_t;
   typedef unsigned __int16 uint16_t;
   typedef unsigned __int32 uint32_t;
   typedef unsigned __int64 uint64_t;
#else
   #include <stdint.h>		
#endif

#include <sys/stat.h>


#ifdef _MSC_VER
#include "SpatialIndex.h"
#include <windows.h>
#else
#include <spatialindex/SpatialIndex.h>
#include <pthread.h>
#define HAVE_PTHREAD_H 1
#endif

class Item;
class Index;

// struct IndexResult {
//     uint64_t id;
//     uint8_t* data;
//     uint32_t length;
//     
// };

typedef enum
{
   RT_None = 0,
   RT_Debug = 1,
   RT_Warning = 2,
   RT_Failure = 3,
   RT_Fatal = 4
} RTError;

typedef enum
{
   RT_RTree = 0,
   RT_MVRTree = 1,
   RT_TPRTree = 2,
   RT_InvalidIndexType = -99
} RTIndexType;

typedef enum
{
   RT_Memory = 0,
   RT_Disk = 1,
   RT_InvalidStorageType = -99
} RTStorageType;

typedef enum
{
   RT_Linear = 0,
   RT_Quadratic = 1,
   RT_Star = 2,
   RT_InvalidIndexVariant = -99
} RTIndexVariant;


#ifdef __cplusplus
#  define IDX_C_START           extern "C" {
#  define IDX_C_END             }
#else
#  define IDX_C_START
#  define IDX_C_END
#endif

typedef Index *IndexH;
typedef Item *IndexItemH;
typedef Tools::PropertySet *IndexPropertyH;
// typedef struct PropertySetHS *IndexPropertyH;

#ifndef SIDX_C_DLL
#if defined(_MSC_VER)
#  define SIDX_C_DLL     __declspec(dllexport)
#else
#  if defined(USE_GCC_VISIBILITY_FLAG)
#    define SIDX_C_DLL     __attribute__ ((visibility("default")))
#  else
#    define SIDX_C_DLL
#  endif
#endif
#endif


#endif
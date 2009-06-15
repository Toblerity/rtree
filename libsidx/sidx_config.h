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
   RT_TPRTree = 2
} RTIndexType;

typedef enum
{
   RT_Memory = 0,
   RT_Disk = 1
} RTStorageType;

typedef enum
{
   RT_Linear = 0,
   RT_Quadratic = 1,
   RT_Star = 2
} RTIndexVariant;


#ifdef __cplusplus
#  define IDX_C_START           extern "C" {
#  define IDX_C_END             }
#else
#  define IDX_C_START
#  define IDX_C_END
#endif

typedef struct IndexHS *IndexH;

typedef struct  {
    RTIndexType type;
    uint32_t dimension;
    RTIndexVariant variant;
    RTStorageType storage;
    uint32_t index_capacity;
    uint32_t leaf_capacity;
    uint32_t pagesize;
    double tpr_horizon;
} IndexProperties;

#endif
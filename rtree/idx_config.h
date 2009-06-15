#ifndef IDXCONFIG_H_INCLUDED
#define IDXCONFIG_H_INCLUDED


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
} RTType;

typedef enum
{
   RT_Linear = 0,
   RT_Quadratic = 1,
   RT_Star = 2
} RTVariant;


#ifdef __cplusplus
#  define IDX_C_START           extern "C" {
#  define IDX_C_END             }
#else
#  define IDX_C_START
#  define IDX_C_END
#endif
   
typedef struct RtreeIndex_t *RtreeIndex;
typedef struct IndexHS *IndexH;

typedef struct  {
    RTType type;
    uint32_t dimension;
    RTVariant variant;
    uint32_t index_capacity;
    uint32_t leaf_capacity;
} IndexProperties;

#endif
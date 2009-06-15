
#include <stack>
#include <string>
#include "sidx_api.h"

static std::stack<std::string> errors;


IDX_C_START

IndexH Index_Create(const char* pszFilename, IndexProperties* properties)
{
    // return (IndexH) new GISPySpatialIndex();    
}

void Index_Delete(IndexH index)
{
    // GISPySpatialIndex* idx = (GISPySpatialIndex*) index;
    // if (idx) delete idx;
}

RTError Index_DeleteData(IndexH index, uint64_t id, double* pdMin, double* pdMax, uint32_t nDimension)
{
    // GISPySpatialIndex* idx = (GISPySpatialIndex*) index;
    // 
    // try {    
    //     idx->index().deleteData(SpatialIndex::Region(pdMin, pdMax, nDimension), id);
    //     return RT_None;
    // }
    // catch (Tools::Exception& e) {
    //     // PyErr_SetString(PyExc_TypeError, e.what().c_str());
    //     return RT_Fatal;
    // }
}
IDX_C_END

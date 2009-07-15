
#include "sidx_impl.hpp"


static std::stack<Error> errors;

#define VALIDATE_POINTER0(ptr, func) \
   do { if( NULL == ptr ) { \
        RTError const ret = RT_Failure; \
        std::ostringstream msg; \
        msg << "Pointer \'" << #ptr << "\' is NULL in \'" << (func) <<"\'."; \
        std::string message(msg.str()); \
        Error_PushError( ret, message.c_str(), (func)); \
        return; \
   }} while(0)

#define VALIDATE_POINTER1(ptr, func, rc) \
   do { if( NULL == ptr ) { \
        RTError const ret = RT_Failure; \
        std::ostringstream msg; \
        msg << "Pointer \'" << #ptr << "\' is NULL in \'" << (func) <<"\'."; \
        std::string message(msg.str()); \
        Error_PushError( ret, message.c_str(), (func)); \
        return (rc); \
   }} while(0)

IDX_C_START

SIDX_DLL void Error_Reset(void) {
    if (errors.empty()) return;
    for (std::size_t i=0;i<errors.size();i++) errors.pop();
}

SIDX_DLL void Error_Pop(void) {
    if (errors.empty()) return;
    errors.pop();
}

SIDX_DLL int Error_GetLastErrorNum(void){
    if (errors.empty())
        return 0;
    else {
        Error err = errors.top();
        return err.GetCode();
    }
}

SIDX_DLL char* Error_GetLastErrorMsg(void){
    if (errors.empty()) 
        return NULL;
    else {
        Error err = errors.top();
        return strdup(err.GetMessage());
    }
}

SIDX_DLL char* Error_GetLastErrorMethod(void){
    if (errors.empty()) 
        return NULL;
    else {
        Error err = errors.top();
        return strdup(err.GetMethod());
    }
}

SIDX_DLL void Error_PushError(int code, const char *message, const char *method) {
    Error err = Error(code, std::string(message), std::string(method));
    errors.push(err);
}

SIDX_DLL int Error_GetErrorCount(void) {
    return static_cast<int>(errors.size());
}

IndexH Index_Create(const char* pszFilename, IndexPropertyH properties)
{
    IndexProperty* poProperty = (IndexProperty*) properties;
    if (poProperty != NULL)
        return (IndexH) new Index(pszFilename, *poProperty);    
    else
        return NULL;
}

void Index_Delete(IndexH index)
{
    Index* idx = (Index*) index;
    if (idx) delete idx;
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
    return RT_None;
}

SIDX_DLL RTError IndexProperty_SetIndexType(IndexPropertyH hProp, RTIndexType value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetIndexType", RT_Failure);    
    IndexProperty* prop = (IndexProperty*) hProp;

    try
    {
        prop->SetIndexType(value);
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, e.what(), "IndexProperty_SetIndexType");
        return RT_Failure;
    }
}

SIDX_DLL RTIndexType IndexProperty_GetIndexType(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetIndexType", RT_InvalidIndexType);
    IndexProperty* prop = (IndexProperty*) hProp;
    return prop->GetIndexType();
}
// 
// RTError IndexProperty_SetDimension(IndexPropertyH iprop, uint32_t value);
// uint32_t IndexProperty_GetDimension(IndexPropertyH iprop);
// 
// RTError IndexProperty_SetIndexVariant(IndexPropertyH iprop, RTIndexVariant value);
// RTIndexVariant IndexProperty_GetIndexVariant(IndexPropertyH iprop);
// 
// RTError IndexProperty_SetIndexStorage(IndexPropertyH iprop, RTStorageType value);
// RTStorageType IndexProperty_GetIndexStorage(IndexPropertyH iprop);
// 
// RTError IndexProperty_SetIndexCapacity(IndexPropertyH iprop, uint32_t value);
// uint32_t IndexProperty_GetIndexCapacity(IndexPropertyH iprop);
// 
// RTError IndexProperty_SetLeafCapacity(IndexPropertyH iprop, uint32_t value);
// uint32_t IndexProperty_GetLeafCapacity(IndexPropertyH iprop);
// 
// RTError IndexProperty_SetPagesize(IndexPropertyH iprop, uint32_t value);
// uint32_t IndexProperty_GetPagesize(IndexPropertyH iprop);
// 
// RTError IndexProperty_SetTPRHorizon(IndexPropertyH iprop, double value);
// double IndexProperty_GetTPRHorizon(IndexPropertyH iprop);
// 
// RTError IndexProperty_SetFillFactor(IndexPropertyH iprop, double value);
// double IndexProperty_GetFillFactor(IndexPropertyH iprop);

IDX_C_END

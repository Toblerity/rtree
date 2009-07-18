
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

SIDX_DLL IndexH Index_Create(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "Index_Create", NULL);   
    Tools::PropertySet* poProperty = dynamic_cast<Tools::PropertySet*>(hProp);
    
    if (poProperty != NULL)
        return (IndexH) new Index(*poProperty);    
    else
        return NULL;
}

SIDX_DLL void Index_Destroy(IndexH index)
{
    VALIDATE_POINTER0(index, "Index_Destroy"); 
    Index* idx = (Index*) index;
    if (idx) delete idx;
}

SIDX_DLL RTError Index_DeleteData(  IndexH index, 
                                    uint64_t id, 
                                    double* pdMin, 
                                    double* pdMax, 
                                    uint32_t nDimension)
{
    VALIDATE_POINTER1(index, "Index_DeleteData", RT_Failure);      

    Index* idx = static_cast<Index*>(index);

    try {    
        idx->index().deleteData(SpatialIndex::Region(pdMin, pdMax, nDimension), id);
        return RT_None;
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "Index_DeleteData");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "Index_DeleteData");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "Index_DeleteData");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL RTError Index_InsertData(  IndexH index, 
                                    uint64_t id, 
                                    double* pdMin, 
                                    double* pdMax, 
                                    uint32_t nDimension,
                                    const uint8_t* pData, 
                                    size_t nDataLength)
{
    VALIDATE_POINTER1(index, "Index_InsertData", RT_Failure);      

    Index* idx = static_cast<Index*>(index);
    
    try {    
        idx->index().insertData(nDataLength, 
                                pData, 
                                SpatialIndex::Region(pdMin, pdMax, nDimension), 
                                id);
        return RT_None;
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "Index_DeleteData");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "Index_DeleteData");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "Index_DeleteData");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL RTError Index_Intersects(  IndexH index, 
                                    double* pdMin, 
                                    double* pdMax, 
                                    uint32_t nDimension, 
                                    IndexItemH* items, 
                                    uint32_t* nResults)
{
    VALIDATE_POINTER1(index, "Index_Intersects", RT_Failure);      
    Index* idx = static_cast<Index*>(index);

    Visitor* visitor = new Visitor;
    try {    
        idx->index().intersectsWithQuery(   SpatialIndex::Region(pdMin, pdMax, nDimension), 
                                            *visitor);
        
        items = (Item**) malloc (visitor->GetResultCount() * sizeof(Item*));
        
        std::vector<Item*>& results = visitor->GetResults();
        
        // copy the Items into the newly allocated item array
        // we need to make sure to copy the actual Item instead 
        // of just the pointers, as the visitor will nuke them 
        // upon ~
        for (size_t i=0; i < visitor->GetResultCount(); ++i)
        {
            *items[i] = *results[i];
        }
        *nResults = visitor->GetResultCount();
        
        delete visitor;
        
        return RT_None;
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "Index_DeleteData");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "Index_DeleteData");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "Index_DeleteData");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL RTError Index_NearestNeighbors(IndexH index, 
                                        double* pdMin, 
                                        double* pdMax, 
                                        uint32_t nDimension, 
                                        IndexItemH* items, 
                                        uint32_t* nResults)
{
    VALIDATE_POINTER1(index, "Index_NearestNeighbors", RT_Failure);  
    Index* idx = static_cast<Index*>(index);

    Visitor* visitor = new Visitor;
    try {    
        idx->index().nearestNeighborQuery(  *nResults,
                                            SpatialIndex::Region(pdMin, pdMax, nDimension), 
                                            *visitor);
        
        items = (Item**) malloc (visitor->GetResultCount() * sizeof(Item*));
        
        std::vector<Item*>& results = visitor->GetResults();
        
        // copy the Items into the newly allocated item array
        // we need to make sure to copy the actual Item instead 
        // of just the pointers, as the visitor will nuke them 
        // upon ~
        for (size_t i=0; i < visitor->GetResultCount(); ++i)
        {
            *items[i] = *results[i];
        }
        *nResults = visitor->GetResultCount();
        
        delete visitor;
        
        return RT_None;
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "Index_DeleteData");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "Index_DeleteData");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "Index_DeleteData");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t Index_IsValid(IndexH index)
{
    VALIDATE_POINTER1(index, "Index_IsValid", 0); 
    Index* idx = static_cast<Index*>(index);
    return static_cast<uint32_t>(idx->index().isIndexValid());    
}

SIDX_DLL IndexPropertyH Index_GetProperties(IndexH index)
{
    VALIDATE_POINTER1(index, "Index_GetProperties", 0); 
    Index* idx = static_cast<Index*>(index);
    Tools::PropertySet* ps = new Tools::PropertySet;
    
    idx->index().getIndexProperties(*ps);
    return dynamic_cast<IndexPropertyH>(ps);
}

SIDX_DLL void IndexItem_Destroy(IndexItemH item)
{
    VALIDATE_POINTER0(item, "IndexItem_Destroy"); 
    Item* it = static_cast<Item*>(item);
    if (it) delete it;
}

SIDX_DLL RTError IndexItem_GetData( IndexItemH item,
                                    uint8_t* data,
                                    uint64_t* length)
{
    VALIDATE_POINTER1(item, "IndexItem_GetData", RT_Failure);  
    Item* it = static_cast<Item*>(item);
    it->GetData(data,length);
    return RT_None;
    
}
SIDX_DLL IndexPropertyH IndexProperty_Create()
{
    Tools::PropertySet* ps = new Tools::PropertySet;
    return dynamic_cast<IndexPropertyH>(ps);
}

SIDX_DLL void IndexProperty_Destroy(IndexPropertyH hProp)
{
    VALIDATE_POINTER0(hProp, "IndexProperty_Destroy");    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);
    if (prop != 0) delete prop;
}

SIDX_DLL RTError IndexProperty_SetIndexType(IndexPropertyH hProp, 
                                            RTIndexType value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetIndexType", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_LONG;
        var.m_val.lVal = value;
        prop->setProperty("IndexType", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetIndexType");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetIndexType");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetIndexType");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL RTIndexType IndexProperty_GetIndexType(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetIndexType", RT_InvalidIndexType);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("IndexType");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_LONG) {
            Error_PushError(RT_Failure, 
                            "Property IndexType must be Tools::VT_LONG", 
                            "IndexProperty_GetIndexType");
            return RT_InvalidIndexType;
        }
        
        return static_cast<RTIndexType>(var.m_val.lVal);
    }

    Error_PushError(RT_Failure, 
                    "Property IndexType was empty", 
                    "IndexProperty_GetIndexType");    
    return RT_InvalidIndexType;

}

SIDX_DLL RTError IndexProperty_SetDimension(IndexPropertyH hProp, uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetDimension", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("Dimension", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetDimension");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetDimension");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetDimension");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetDimension(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetDimension", RT_InvalidIndexType);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("Dimension");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property IndexType must be Tools::VT_ULONG", 
                            "IndexProperty_GetDimension");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // A zero dimension index is invalid.
    Error_PushError(RT_Failure, 
                    "Property Dimension was empty", 
                    "IndexProperty_GetDimension");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetIndexVariant( IndexPropertyH hProp, 
                                                RTIndexVariant value)
{
    using namespace SpatialIndex;

    VALIDATE_POINTER1(hProp, "IndexProperty_SetIndexVariant", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    
    try
    {
        var.m_varType = Tools::VT_LONG;
        RTIndexType type = IndexProperty_GetIndexType(hProp);
        if (type == RT_InvalidIndexType ) {
            Error_PushError(RT_Failure, 
                            "Index type is not properly set", 
                            "IndexProperty_SetIndexVariant");
            return RT_Failure;
        }
        if (type == RT_RTree) {
            var.m_val.lVal = static_cast<RTree::RTreeVariant>(value);
            prop->setProperty("TreeVariant", var);
        } else if (type  == RT_MVRTree) {
            var.m_val.lVal = static_cast<MVRTree::MVRTreeVariant>(value);
            prop->setProperty("TreeVariant", var);   
        } else if (type == RT_TPRTree) {
            var.m_val.lVal = static_cast<TPRTree::TPRTreeVariant>(value);
            prop->setProperty("TreeVariant", var);   
        }
    
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetIndexVariant");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetIndexCapacity");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetIndexCapacity");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL RTIndexVariant IndexProperty_GetIndexVariant(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(  hProp, 
                        "IndexProperty_GetIndexVariant", 
                        RT_InvalidIndexVariant);

    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("TreeVariant");

    
    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_LONG) {
            Error_PushError(RT_Failure, 
                            "Property IndexVariant must be Tools::VT_LONG", 
                            "IndexProperty_GetIndexVariant");
            return RT_InvalidIndexVariant;
        }
        
        return static_cast<RTIndexVariant>(var.m_val.lVal);
    }
    
    // if we didn't get anything, we're returning an error condition
    Error_PushError(RT_Failure, 
                    "Property IndexVariant was empty", 
                    "IndexProperty_GetIndexVariant");
    return RT_InvalidIndexVariant;

}

SIDX_DLL RTError IndexProperty_SetIndexStorage( IndexPropertyH hProp, 
                                                RTStorageType value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetIndexStorage", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("IndexStorageType", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetIndexStorage");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetIndexStorage");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetIndexStorage");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL RTStorageType IndexProperty_GetIndexStorage(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(  hProp, 
                        "IndexProperty_GetIndexStorage", 
                        RT_InvalidStorageType);

    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("IndexStorageType");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property IndexStorage must be Tools::VT_ULONG", 
                            "IndexProperty_GetIndexStorage");
            return RT_InvalidStorageType;
        }
        
        return static_cast<RTStorageType>(var.m_val.ulVal);
    }
    
    // if we didn't get anything, we're returning an error condition
    Error_PushError(RT_Failure, 
                    "Property IndexStorage was empty", 
                    "IndexProperty_GetIndexStorage");
    return RT_InvalidStorageType;

}

SIDX_DLL RTError IndexProperty_SetIndexCapacity(IndexPropertyH hProp, 
                                                uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetIndexCapacity", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("IndexCapacity", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetIndexCapacity");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetIndexCapacity");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetIndexCapacity");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetIndexCapacity(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetIndexCapacity", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("IndexCapacity");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property IndexCapacity must be Tools::VT_ULONG", 
                            "IndexProperty_GetIndexCapacity");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property IndexCapacity was empty", 
                    "IndexProperty_GetIndexCapacity");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetLeafCapacity( IndexPropertyH hProp, 
                                                uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetLeafCapacity", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("LeafCapacity", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetLeafCapacity");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetLeafCapacity");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetLeafCapacity");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetLeafCapacity(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetLeafCapacity", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("LeafCapacity");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property LeafCapacity must be Tools::VT_ULONG", 
                            "IndexProperty_GetLeafCapacity");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property LeafCapacity was empty", 
                    "IndexProperty_GetLeafCapacity");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetPagesize( IndexPropertyH hProp, 
                                            uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetPagesize", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("PageSize", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetPagesize");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetPagesize");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetPagesize");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetPagesize(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetPagesize", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("PageSize");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property PageSize must be Tools::VT_ULONG", 
                            "IndexProperty_GetPagesize");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property PageSize was empty", 
                    "IndexProperty_GetPagesize");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetLeafPoolCapacity( IndexPropertyH hProp, 
                                                    uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetLeafPoolCapacity", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("LeafPoolCapacity", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetLeafPoolCapacity");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetLeafPoolCapacity");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetLeafPoolCapacity");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetLeafPoolCapacity(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetLeafPoolCapacity", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("LeafPoolCapacity");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property LeafPoolCapacity must be Tools::VT_ULONG", 
                            "IndexProperty_GetLeafPoolCapacity");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property LeafPoolCapacity was empty", 
                    "IndexProperty_GetLeafPoolCapacity");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetIndexPoolCapacity(IndexPropertyH hProp, 
                                                    uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetIndexPoolCapacity", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("IndexPoolCapacity", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetIndexPoolCapacity");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetIndexPoolCapacity");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetIndexPoolCapacity");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetIndexPoolCapacity(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetIndexPoolCapacity", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("IndexPoolCapacity");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property IndexPoolCapacity must be Tools::VT_ULONG", 
                            "IndexProperty_GetIndexPoolCapacity");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property IndexPoolCapacity was empty", 
                    "IndexProperty_GetIndexPoolCapacity");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetRegionPoolCapacity(IndexPropertyH hProp, 
                                                    uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetRegionPoolCapacity", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("RegionPoolCapacity", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetRegionPoolCapacity");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetRegionPoolCapacity");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetRegionPoolCapacity");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetRegionPoolCapacity(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetRegionPoolCapacity", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("RegionPoolCapacity");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property RegionPoolCapacity must be Tools::VT_ULONG", 
                            "IndexProperty_GetRegionPoolCapacity");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property RegionPoolCapacity was empty", 
                    "IndexProperty_GetRegionPoolCapacity");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetPointPoolCapacity(IndexPropertyH hProp, 
                                                    uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetPointPoolCapacity", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("PointPoolCapacity", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetPointPoolCapacity");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetPointPoolCapacity");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetPointPoolCapacity");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetPointPoolCapacity(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetPointPoolCapacity", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("PointPoolCapacity");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property PointPoolCapacity must be Tools::VT_ULONG", 
                            "IndexProperty_GetPointPoolCapacity");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property PointPoolCapacity was empty", 
                    "IndexProperty_GetPointPoolCapacity");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetNearMinimumOverlapFactor( IndexPropertyH hProp, 
                                                            uint32_t value)
{
    VALIDATE_POINTER1(  hProp, 
                        "IndexProperty_SetNearMinimumOverlapFactor", 
                        RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("NearMinimumOverlapFactor", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetNearMinimumOverlapFactor");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetNearMinimumOverlapFactor");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetNearMinimumOverlapFactor");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetNearMinimumOverlapFactor(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetNearMinimumOverlapFactor", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("NearMinimumOverlapFactor");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property NearMinimumOverlapFactor must be Tools::VT_ULONG", 
                            "IndexProperty_GetNearMinimumOverlapFactor");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property NearMinimumOverlapFactor was empty", 
                    "IndexProperty_GetNearMinimumOverlapFactor");
    return 0;
}


SIDX_DLL RTError IndexProperty_SetBufferingCapacity(IndexPropertyH hProp, 
                                                uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetBufferingCapacity", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_ULONG;
        var.m_val.ulVal = value;
        prop->setProperty("Capacity", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetBufferingCapacity");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetBufferingCapacity");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetBufferingCapacity");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetBufferingCapacity(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetBufferingCapacity", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("Capacity");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property Capacity must be Tools::VT_ULONG", 
                            "IndexProperty_GetBufferingCapacity");
            return 0;
        }
        
        return var.m_val.ulVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property Capacity was empty", 
                    "IndexProperty_GetBufferingCapacity");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetEnsureTightMBRs(  IndexPropertyH hProp, 
                                                    uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetEnsureTightMBRs", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        if (value > 1 ) {
            Error_PushError(RT_Failure, 
                            "EnsureTightMBRs is a boolean value and must be 1 or 0", 
                            "IndexProperty_SetEnsureTightMBRs");
            return RT_Failure;
        }
        Tools::Variant var;
        var.m_varType = Tools::VT_BOOL;
        var.m_val.bVal = value;
        prop->setProperty("EnsureTightMBRs", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetEnsureTightMBRs");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetEnsureTightMBRs");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetEnsureTightMBRs");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetEnsureTightMBRs(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetEnsureTightMBRs", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("EnsureTightMBRs");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_BOOL) {
            Error_PushError(RT_Failure, 
                            "Property EnsureTightMBRs must be Tools::VT_BOOL", 
                            "IndexProperty_GetEnsureTightMBRs");
            return 0;
        }
        
        return var.m_val.bVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property EnsureTightMBRs was empty", 
                    "IndexProperty_GetEnsureTightMBRs");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetWriteThrough(IndexPropertyH hProp, 
                                                    uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetWriteThrough", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        if (value > 1 ) {
            Error_PushError(RT_Failure, 
                            "WriteThrough is a boolean value and must be 1 or 0", 
                            "IndexProperty_SetWriteThrough");
            return RT_Failure;
        }
        Tools::Variant var;
        var.m_varType = Tools::VT_BOOL;
        var.m_val.bVal = value;
        prop->setProperty("WriteThrough", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetWriteThrough");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetWriteThrough");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetWriteThrough");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetWriteThrough(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetWriteThrough", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("WriteThrough");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_BOOL) {
            Error_PushError(RT_Failure, 
                            "Property WriteThrough must be Tools::VT_BOOL", 
                            "IndexProperty_GetWriteThrough");
            return 0;
        }
        
        return var.m_val.bVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property WriteThrough was empty", 
                    "IndexProperty_GetWriteThrough");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetOverwrite(IndexPropertyH hProp, 
                                            uint32_t value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetOverwrite", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        if (value > 1 ) {
            Error_PushError(RT_Failure, 
                            "Overwrite is a boolean value and must be 1 or 0", 
                            "IndexProperty_SetOverwrite");
            return RT_Failure;
        }
        Tools::Variant var;
        var.m_varType = Tools::VT_BOOL;
        var.m_val.bVal = value;
        prop->setProperty("Overwrite", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetOverwrite");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetOverwrite");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetOverwrite");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL uint32_t IndexProperty_GetOverwrite(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetOverwrite", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("Overwrite");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_BOOL) {
            Error_PushError(RT_Failure, 
                            "Property Overwrite must be Tools::VT_BOOL", 
                            "IndexProperty_GetOverwrite");
            return 0;
        }
        
        return var.m_val.bVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property Overwrite was empty", 
                    "IndexProperty_GetOverwrite");
    return 0;
}


SIDX_DLL RTError IndexProperty_SetFillFactor(   IndexPropertyH hProp, 
                                                double value)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_SetFillFactor", RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_DOUBLE;
        var.m_val.dblVal = value;
        prop->setProperty("FillFactor", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetFillFactor");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetFillFactor");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetFillFactor");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL double IndexProperty_GetFillFactor(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetFillFactor", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("FillFactor");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property FillFactor must be Tools::VT_DOUBLE", 
                            "IndexProperty_GetFillFactor");
            return 0;
        }
        
        return var.m_val.dblVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property FillFactor was empty", 
                    "IndexProperty_GetFillFactor");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetSplitDistributionFactor(  IndexPropertyH hProp, 
                                                            double value)
{
    VALIDATE_POINTER1(  hProp, 
                        "IndexProperty_SetSplitDistributionFactor", 
                        RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_DOUBLE;
        var.m_val.dblVal = value;
        prop->setProperty("SplitDistributionFactor", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetSplitDistributionFactor");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetSplitDistributionFactor");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetSplitDistributionFactor");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL double IndexProperty_GetSplitDistributionFactor(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetSplitDistributionFactor", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("SplitDistributionFactor");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property SplitDistributionFactor must be Tools::VT_DOUBLE", 
                            "IndexProperty_GetSplitDistributionFactor");
            return 0;
        }
        
        return var.m_val.dblVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property SplitDistributionFactor was empty", 
                    "IndexProperty_GetSplitDistributionFactor");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetTPRHorizon(IndexPropertyH hProp, 
                                             double value)
{
    VALIDATE_POINTER1(  hProp, 
                        "IndexProperty_SetTPRHorizon", 
                        RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_DOUBLE;
        var.m_val.dblVal = value;
        prop->setProperty("Horizon", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetTPRHorizon");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetTPRHorizon");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetTPRHorizon");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL double IndexProperty_GetTPRHorizon(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetTPRHorizon", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("Horizon");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property Horizon must be Tools::VT_DOUBLE", 
                            "IndexProperty_GetTPRHorizon");
            return 0;
        }
        
        return var.m_val.dblVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property Horizon was empty", 
                    "IndexProperty_GetTPRHorizon");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetReinsertFactor(   IndexPropertyH hProp, 
                                                    double value)
{
    VALIDATE_POINTER1(  hProp, 
                        "IndexProperty_SetReinsertFactor", 
                        RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_DOUBLE;
        var.m_val.dblVal = value;
        prop->setProperty("ReinsertFactor", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetReinsertFactor");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetReinsertFactor");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetReinsertFactor");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL double IndexProperty_GetReinsertFactor(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetReinsertFactor", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("ReinsertFactor");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_ULONG) {
            Error_PushError(RT_Failure, 
                            "Property ReinsertFactor must be Tools::VT_DOUBLE", 
                            "IndexProperty_GetReinsertFactor");
            return 0;
        }
        
        return var.m_val.dblVal;
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property ReinsertFactor was empty", 
                    "IndexProperty_GetReinsertFactor");
    return 0;
}

SIDX_DLL RTError IndexProperty_SetFileName( IndexPropertyH hProp, 
                                            const char* value)
{
    VALIDATE_POINTER1(  hProp, 
                        "IndexProperty_SetFileName", 
                        RT_Failure);    
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    try
    {
        Tools::Variant var;
        var.m_varType = Tools::VT_PCHAR;
        var.m_val.pcVal = strdup(value); // not sure if we should copy here
        prop->setProperty("FileName", var);
    } catch (Tools::Exception& e)
    {
        Error_PushError(RT_Failure, 
                        e.what().c_str(), 
                        "IndexProperty_SetFileName");
        return RT_Failure;
    } catch (std::exception const& e)
    {
        Error_PushError(RT_Failure, 
                        e.what(), 
                        "IndexProperty_SetFileName");
        return RT_Failure;
    } catch (...) {
        Error_PushError(RT_Failure, 
                        "Unknown Error", 
                        "IndexProperty_SetFileName");
        return RT_Failure;        
    }
    return RT_None;
}

SIDX_DLL char* IndexProperty_GetFileName(IndexPropertyH hProp)
{
    VALIDATE_POINTER1(hProp, "IndexProperty_GetFileName", 0);
    Tools::PropertySet* prop = static_cast<Tools::PropertySet*>(hProp);

    Tools::Variant var;
    var = prop->getProperty("FileName");

    if (var.m_varType != Tools::VT_EMPTY)
    {
        if (var.m_varType != Tools::VT_PCHAR) {
            Error_PushError(RT_Failure, 
                            "Property FileName must be Tools::VT_PCHAR", 
                            "IndexProperty_GetFileName");
            return NULL;
        }
        
        return strdup(var.m_val.pcVal);
    }
    
    // return nothing for an error
    Error_PushError(RT_Failure, 
                    "Property FileName was empty", 
                    "IndexProperty_GetFileName");
    return NULL;
}


IDX_C_END

// pybind11 bindings for the libspatialindex C API (sidx_api.h).
//
// This module replaces the hand-maintained ctypes prototypes in the old
// ``rtree/core.py``.  Because it is compiled against the real headers, every
// argument and return type is checked by the C++ compiler, and pybind11 emits
// Python signatures that ``pybind11-stubgen`` turns into ``rtree/_core.pyi``.
//
// Design notes
// ------------
// * The binding is intentionally *thin*: it mirrors the C API one-to-one but
//   speaks Python types (``list[float]``, ``bytes``, ``numpy.ndarray``)
//   instead of raw pointers.  All policy (interleaving, serialization,
//   TPR-tree argument unpacking...) stays in ``rtree/index.py``.
// * Memory returned by the C API is always released with ``Index_Free`` /
//   ``IndexItem_Destroy`` so that allocation and deallocation happen in the
//   same CRT on Windows.
// * The GIL is released around calls into libspatialindex, matching what
//   ctypes did implicitly.  Callbacks (custom storage) re-acquire it.

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/typing.h>

#include <spatialindex/capi/sidx_api.h>
#include <spatialindex/capi/sidx_impl.h>
#include <spatialindex/Version.h>

#include <cstdint>
#include <cstring>
#include <exception>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace py = pybind11;
using namespace py::literals;

// These are exported by libspatialindex_c but are *not* declared in
// sidx_api.h.  ctypes never noticed because it does not read headers.
IDX_C_START
SIDX_C_DLL void Error_Reset(void);
SIDX_C_DLL int Error_GetErrorCount(void);
IDX_C_END

#ifndef SIDX_VERSION_NUM
#define SIDX_VERSION_NUM 0
#endif

namespace {

using CustomCallbacks = SpatialIndex::StorageManager::CustomStorageManagerCallbacks;

PyObject *g_rtree_error = nullptr;
PyObject *g_invalid_handle = nullptr;

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

std::string take_c_string(char *p) {
    if (p == nullptr) {
        return {};
    }
    std::string s(p);
    Index_Free(p);
    return s;
}

[[noreturn]] void raise_sidx(const char *func) {
    std::string msg = take_c_string(Error_GetLastErrorMsg());
    Error_Reset();
    std::string full = std::string("Error in \"") + func + "\": " + msg;
    PyErr_SetString(g_rtree_error, full.c_str());
    throw py::error_already_set();
}

// ``errcheck = check_return`` equivalent.
inline void check_rc(RTError rc, const char *func) {
    if (rc != RT_None) {
        raise_sidx(func);
    }
}

// ``errcheck = check_value`` / ``check_void_done`` equivalent.
inline void check_err(const char *func) {
    if (Error_GetErrorCount() != 0) {
        raise_sidx(func);
    }
}

[[noreturn]] void raise_invalid_handle() {
    PyErr_SetString(g_invalid_handle, "Handle has been destroyed");
    throw py::error_already_set();
}

void require_same_dim(const std::vector<double> &a, const std::vector<double> &b,
                      const char *what) {
    if (a.size() != b.size()) {
        throw py::value_error(std::string(what) + ": mins and maxs must have the same length");
    }
    if (a.empty()) {
        throw py::value_error(std::string(what) + ": coordinates must not be empty");
    }
}

using Coords = std::vector<double>;
using Bounds = std::pair<Coords, Coords>;

// Copy a C array of ``n`` values and release it with Index_Free.
template <typename T> std::vector<T> take_array(T *p, uint64_t n) {
    std::vector<T> out;
    if (p != nullptr) {
        out.assign(p, p + n);
        Index_Free(p);
    }
    return out;
}

// ---------------------------------------------------------------------------
// IndexItem: an owned result object from *_obj queries
// ---------------------------------------------------------------------------

class IndexItem {
  public:
    explicit IndexItem(IndexItemH h) : h_(h) {}
    IndexItem(const IndexItem &) = delete;
    IndexItem &operator=(const IndexItem &) = delete;
    IndexItem(IndexItem &&o) noexcept : h_(std::exchange(o.h_, nullptr)) {}
    IndexItem &operator=(IndexItem &&o) noexcept {
        std::swap(h_, o.h_);
        return *this;
    }
    ~IndexItem() {
        if (h_ != nullptr) {
            IndexItem_Destroy(h_);
        }
    }

    int64_t id() const {
        int64_t v = IndexItem_GetID(get());
        check_err("IndexItem_GetID");
        return v;
    }

    std::optional<py::bytes> data() const {
        uint8_t *d = nullptr;
        uint64_t len = 0;
        check_rc(IndexItem_GetData(get(), &d, &len), "IndexItem_GetData");
        if (len == 0) {
            if (d != nullptr) {
                Index_Free(d);
            }
            return std::nullopt;
        }
        py::bytes out(reinterpret_cast<const char *>(d), static_cast<size_t>(len));
        Index_Free(d);
        return out;
    }

    std::optional<Bounds> bounds() const {
        double *mins = nullptr;
        double *maxs = nullptr;
        uint32_t dim = 0;
        check_rc(IndexItem_GetBounds(get(), &mins, &maxs, &dim), "IndexItem_GetBounds");
        if (dim == 0) {
            return std::nullopt;
        }
        return Bounds{take_array(mins, dim), take_array(maxs, dim)};
    }

  private:
    IndexItemH get() const {
        if (h_ == nullptr) {
            raise_invalid_handle();
        }
        return h_;
    }
    IndexItemH h_;
};

// Convert a C result array of IndexItemH into owned wrappers.  Ownership of
// every element moves to the wrappers; only the outer array is freed here.
std::vector<IndexItem> take_items(IndexItemH *items, uint64_t n) {
    std::vector<IndexItem> out;
    out.reserve(static_cast<size_t>(n));
    for (uint64_t i = 0; i < n; ++i) {
        out.emplace_back(items[i]);
    }
    if (items != nullptr) {
        Index_Free(items);
    }
    return out;
}

// ---------------------------------------------------------------------------
// Custom storage bridge: C callbacks -> Python ``CustomStorage`` methods
// ---------------------------------------------------------------------------

// Stand-in for the ``ctypes.POINTER(c_int)`` the old callbacks received.
// ``err.contents.value = X`` and ``err.value = X`` both work.
struct ErrorRef {
    int value = 0;
};

struct StorageBridge {
    py::object storage;

    static StorageBridge &from(const void *ctx) {
        return *static_cast<StorageBridge *>(const_cast<void *>(ctx));
    }

    template <typename F> static void guarded(const void *ctx, int *errorCode, F &&f) {
        py::gil_scoped_acquire gil;
        auto &self = from(ctx);
        // Python owns the ErrorRef so a callback that stashes it cannot
        // leave a dangling pointer behind.
        py::object ref = py::cast(ErrorRef{});
        try {
            f(self.storage, ref);
            *errorCode = ref.cast<ErrorRef &>().value;
        } catch (py::error_already_set &e) {
            e.discard_as_unraisable("rtree custom storage callback");
            *errorCode = SpatialIndex::StorageManager::CustomStorageManager::IllegalStateError;
        } catch (std::exception &e) {
            PyErr_SetString(PyExc_RuntimeError, e.what());
            PyErr_WriteUnraisable(nullptr);
            *errorCode = SpatialIndex::StorageManager::CustomStorageManager::IllegalStateError;
        }
    }

    static void create(const void *ctx, int *ec) {
        guarded(ctx, ec, [](py::object &s, py::object &e) { s.attr("create")(e); });
    }
    static void destroy(const void *ctx, int *ec) {
        guarded(ctx, ec, [](py::object &s, py::object &e) { s.attr("destroy")(e); });
    }
    static void flush(const void *ctx, int *ec) {
        guarded(ctx, ec, [](py::object &s, py::object &e) { s.attr("flush")(e); });
    }
    static void load(const void *ctx, const SpatialIndex::id_type page, uint32_t *len,
                     uint8_t **data, int *ec) {
        guarded(ctx, ec, [&](py::object &s, py::object &e) {
            py::object r = s.attr("loadByteArray")(page, e);
            if (e.cast<ErrorRef &>().value != 0) {
                return;
            }
            char *buf = nullptr;
            Py_ssize_t n = 0;
            py::bytes b = py::reinterpret_borrow<py::object>(r);
            if (PyBytes_AsStringAndSize(b.ptr(), &buf, &n) != 0) {
                throw py::error_already_set();
            }
            // Must be allocated by libspatialindex, which later delete[]s it.
            auto *out = static_cast<uint8_t *>(SIDX_NewBuffer(static_cast<size_t>(n)));
            std::memcpy(out, buf, static_cast<size_t>(n));
            *len = static_cast<uint32_t>(n);
            *data = out;
        });
    }
    static void store(const void *ctx, SpatialIndex::id_type *page, const uint32_t len,
                      const uint8_t *const data, int *ec) {
        guarded(ctx, ec, [&](py::object &s, py::object &e) {
            py::bytes b(reinterpret_cast<const char *>(data), len);
            py::object r = s.attr("storeByteArray")(*page, b, e);
            if (!r.is_none()) {
                *page = r.cast<SpatialIndex::id_type>();
            }
        });
    }
    static void del(const void *ctx, const SpatialIndex::id_type page, int *ec) {
        guarded(ctx, ec, [&](py::object &s, py::object &e) { s.attr("deleteByteArray")(page, e); });
    }
};

// ---------------------------------------------------------------------------
// PropertyHandle
// ---------------------------------------------------------------------------

class PropertyHandle {
  public:
    PropertyHandle() : h_(IndexProperty_Create()) {
        if (h_ == nullptr) {
            raise_sidx("IndexProperty_Create");
        }
    }
    PropertyHandle(const PropertyHandle &) = delete;
    PropertyHandle &operator=(const PropertyHandle &) = delete;
    ~PropertyHandle() { destroy(); }

    void destroy() {
        if (h_ != nullptr) {
            IndexProperty_Destroy(h_);
            h_ = nullptr;
        }
    }
    bool valid() const { return h_ != nullptr; }

    IndexPropertyH get() const {
        if (h_ == nullptr) {
            raise_invalid_handle();
        }
        return h_;
    }

    // Wire a Python ``rtree.index.CustomStorage`` into this property set.
    void set_python_storage(py::object storage) {
        bridge_ = std::make_unique<StorageBridge>();
        bridge_->storage = std::move(storage);
        CustomCallbacks cb;
        cb.context = bridge_.get();
        cb.createCallback = &StorageBridge::create;
        cb.destroyCallback = &StorageBridge::destroy;
        cb.flushCallback = &StorageBridge::flush;
        cb.loadByteArrayCallback = &StorageBridge::load;
        cb.storeByteArrayCallback = &StorageBridge::store;
        cb.deleteByteArrayCallback = &StorageBridge::del;
        check_rc(IndexProperty_SetCustomStorageCallbacksSize(get(), sizeof(CustomCallbacks)),
                 "IndexProperty_SetCustomStorageCallbacksSize");
        check_rc(IndexProperty_SetCustomStorageCallbacks(get(), &cb),
                 "IndexProperty_SetCustomStorageCallbacks");
    }

  private:
    IndexPropertyH h_;
    std::unique_ptr<StorageBridge> bridge_;
};

// ---------------------------------------------------------------------------
// Bulk-load stream support.  Index_CreateWithStream takes a bare function
// pointer with no user-data argument, so the active stream is kept in a
// thread-local for the duration of the (synchronous) create call.
// ---------------------------------------------------------------------------

struct StreamState {
    py::function next_item;
    Coords mins, maxs;
    py::object data;  // keeps the current item's bytes alive
    std::exception_ptr error;
};

thread_local StreamState *g_stream = nullptr;
const uint8_t k_no_data = 0;

#if SIDX_VERSION_NUM && SIDX_VERSION_NUM < 1900
// libspatialindex < 1.9.0: headers say size_t* but the implementation writes a
// uint32_t (see rtree issue #220).
using stream_len_t = uint32_t;
#else
using stream_len_t = size_t;
#endif

int stream_read_next(int64_t *id, double **pMin, double **pMax, uint32_t *nDim,
                     const uint8_t **pData, stream_len_t *nLen) {
    StreamState *s = g_stream;
    try {
        py::object r = s->next_item();
        if (r.is_none()) {
            return -1;
        }
        auto t = r.cast<py::tuple>();
        if (t.size() != 4) {
            throw py::value_error("stream item must be (id, mins, maxs, data)");
        }
        *id = t[0].cast<int64_t>();
        s->mins = t[1].cast<Coords>();
        s->maxs = t[2].cast<Coords>();
        require_same_dim(s->mins, s->maxs, "stream");
        *pMin = s->mins.data();
        *pMax = s->maxs.data();
        *nDim = static_cast<uint32_t>(s->mins.size());
        s->data = t[3];
        if (s->data.is_none()) {
            *pData = &k_no_data;
            *nLen = 0;
        } else {
            char *buf = nullptr;
            Py_ssize_t n = 0;
            if (PyBytes_AsStringAndSize(s->data.ptr(), &buf, &n) != 0) {
                throw py::error_already_set();
            }
            *pData = reinterpret_cast<const uint8_t *>(buf);
            *nLen = static_cast<stream_len_t>(n);
        }
        return 0;
    } catch (...) {
        s->error = std::current_exception();
        return -1;
    }
}

// ---------------------------------------------------------------------------
// numpy helpers for the vectorized (_v) and array bulk-load APIs
// ---------------------------------------------------------------------------

template <typename T> void require_dtype(const py::array &a, const char *name) {
    if (!a.dtype().is(py::dtype::of<T>())) {
        throw py::type_error(std::string(name) + " has the wrong dtype");
    }
}

uint64_t elem_stride(const py::array &a, py::ssize_t axis) {
    auto s = a.strides(axis);
    if (s < 0 || s % a.itemsize() != 0) {
        throw py::value_error("array strides must be positive multiples of the item size");
    }
    return static_cast<uint64_t>(s / a.itemsize());
}

void check_box_arrays(const py::array &mins, const py::array &maxs) {
    require_dtype<double>(mins, "mins");
    require_dtype<double>(maxs, "maxs");
    if (mins.ndim() != 2 || maxs.ndim() != 2) {
        throw py::value_error("mins/maxs must have 2 dimensions: (n, d)");
    }
    for (py::ssize_t ax = 0; ax < 2; ++ax) {
        if (mins.shape(ax) != maxs.shape(ax) || mins.strides(ax) != maxs.strides(ax)) {
            throw py::value_error("mins and maxs must have equal shapes and strides");
        }
    }
}

// ---------------------------------------------------------------------------
// IndexHandle
// ---------------------------------------------------------------------------

class IndexHandle {
  public:
    explicit IndexHandle(PropertyHandle &p) : h_(Index_Create(p.get())) {
        if (h_ == nullptr) {
            raise_sidx("Index_Create");
        }
    }

    using StreamItem =
        py::typing::Optional<py::typing::Tuple<py::int_, py::typing::List<py::float_>,
                                               py::typing::List<py::float_>,
                                               py::typing::Optional<py::bytes>>>;
    using NextItemFn = py::typing::Callable<StreamItem()>;

    static std::unique_ptr<IndexHandle> from_stream(PropertyHandle &p, NextItemFn next_item) {
        StreamState state;
        state.next_item = std::move(next_item);
        StreamState *prev = std::exchange(g_stream, &state);
        IndexH h = Index_CreateWithStream(
            p.get(), reinterpret_cast<int (*)(int64_t *, double **, double **, uint32_t *,
                                              const uint8_t **, size_t *)>(&stream_read_next));
        g_stream = prev;
        if (state.error) {
            if (h != nullptr) {
                Index_Destroy(h);
            }
            Error_Reset();
            std::rethrow_exception(state.error);
        }
        if (h == nullptr) {
            raise_sidx("Index_CreateWithStream");
        }
        return std::unique_ptr<IndexHandle>(new IndexHandle(h));
    }

#ifdef RTREE_HAVE_ARRAY_API
    static std::unique_ptr<IndexHandle> from_arrays(PropertyHandle &p, const py::array &ids,
                                                    const py::array &mins, const py::array &maxs) {
        require_dtype<int64_t>(ids, "ids");
        check_box_arrays(mins, maxs);
        if (ids.ndim() != 1 || ids.shape(0) != mins.shape(0)) {
            throw py::value_error("index and point counts different");
        }
        const uint64_t n = static_cast<uint64_t>(mins.shape(0));
        const uint32_t d = static_cast<uint32_t>(mins.shape(1));
        IndexH h = Index_CreateWithArray(
            p.get(), n, d, elem_stride(ids, 0), elem_stride(mins, 0), elem_stride(mins, 1),
            static_cast<int64_t *>(const_cast<void *>(ids.data())),
            static_cast<double *>(const_cast<void *>(mins.data())),
            static_cast<double *>(const_cast<void *>(maxs.data())));
        if (h == nullptr) {
            raise_sidx("Index_CreateWithArray");
        }
        return std::unique_ptr<IndexHandle>(new IndexHandle(h));
    }
#endif

    IndexHandle(const IndexHandle &) = delete;
    IndexHandle &operator=(const IndexHandle &) = delete;
    ~IndexHandle() { destroy(); }

    void destroy() {
        if (h_ != nullptr) {
            Index_Destroy(h_);
            h_ = nullptr;
            // Index_Destroy is void; surface anything it pushed (e.g. flush
            // failures on disk storage) only if Python is in a sane state.
            if (Error_GetErrorCount() != 0 && Py_IsInitialized()) {
                raise_sidx("Index_Destroy");
            }
        }
    }
    bool valid_handle() const { return h_ != nullptr; }

    // -- mutation ----------------------------------------------------------

    void insert(int64_t id, Coords mins, Coords maxs, std::optional<py::bytes> data) {
        require_same_dim(mins, maxs, "insert");
        const uint8_t *buf = &k_no_data;
        size_t len = 0;
        if (data) {
            char *b = nullptr;
            Py_ssize_t n = 0;
            PyBytes_AsStringAndSize(data->ptr(), &b, &n);
            buf = reinterpret_cast<const uint8_t *>(b);
            len = static_cast<size_t>(n);
        }
        IndexH h = get();
        RTError rc;
        {
            py::gil_scoped_release nogil;
            rc = Index_InsertData(h, id, mins.data(), maxs.data(),
                                  static_cast<uint32_t>(mins.size()), buf, len);
        }
        check_rc(rc, "Index_InsertData");
    }

    void remove(int64_t id, Coords mins, Coords maxs) {
        require_same_dim(mins, maxs, "delete");
        IndexH h = get();
        RTError rc;
        {
            py::gil_scoped_release nogil;
            rc = Index_DeleteData(h, id, mins.data(), maxs.data(),
                                  static_cast<uint32_t>(mins.size()));
        }
        check_rc(rc, "Index_DeleteData");
    }

    // -- queries -----------------------------------------------------------

    uint64_t intersects_count(Coords mins, Coords maxs) {
        require_same_dim(mins, maxs, "count");
        IndexH h = get();
        uint64_t n = 0;
        RTError rc;
        {
            py::gil_scoped_release nogil;
            rc = Index_Intersects_count(h, mins.data(), maxs.data(),
                                        static_cast<uint32_t>(mins.size()), &n);
        }
        check_rc(rc, "Index_Intersects_count");
        return n;
    }

    using IdQuery = RTError (*)(IndexH, double *, double *, uint32_t, int64_t **, uint64_t *);
    using ObjQuery = RTError (*)(IndexH, double *, double *, uint32_t, IndexItemH **, uint64_t *);

    std::vector<int64_t> run_id(IdQuery fn, const char *name, Coords &mins, Coords &maxs,
                                uint64_t n_in = 0) {
        require_same_dim(mins, maxs, name);
        IndexH h = get();
        int64_t *ids = nullptr;
        uint64_t n = n_in;
        RTError rc;
        {
            py::gil_scoped_release nogil;
            rc = fn(h, mins.data(), maxs.data(), static_cast<uint32_t>(mins.size()), &ids, &n);
        }
        if (rc != RT_None) {
            if (ids != nullptr) {
                Index_Free(ids);
            }
            raise_sidx(name);
        }
        return take_array(ids, n);
    }

    std::vector<IndexItem> run_obj(ObjQuery fn, const char *name, Coords &mins, Coords &maxs,
                                   uint64_t n_in = 0) {
        require_same_dim(mins, maxs, name);
        IndexH h = get();
        IndexItemH *items = nullptr;
        uint64_t n = n_in;
        RTError rc;
        {
            py::gil_scoped_release nogil;
            rc = fn(h, mins.data(), maxs.data(), static_cast<uint32_t>(mins.size()), &items, &n);
        }
        if (rc != RT_None) {
            raise_sidx(name);
        }
        return take_items(items, n);
    }

    std::optional<Bounds> bounds() {
        IndexH h = get();
        double *mins = nullptr;
        double *maxs = nullptr;
        uint32_t dim = 0;
        RTError rc = Index_GetBounds(h, &mins, &maxs, &dim);
        check_rc(rc, "Index_GetBounds");
        check_err("Index_GetBounds");
        if (dim == 0) {
            return std::nullopt;
        }
        return Bounds{take_array(mins, dim), take_array(maxs, dim)};
    }

    std::vector<std::tuple<int64_t, std::vector<int64_t>, Coords>> leaves() {
        IndexH h = get();
        uint32_t count = 0, dim = 0;
        uint32_t *sizes = nullptr;
        int64_t *ids = nullptr;
        int64_t **children = nullptr;
        double **mins = nullptr;
        double **maxs = nullptr;
        check_rc(Index_GetLeaves(h, &count, &sizes, &ids, &children, &mins, &maxs, &dim),
                 "Index_GetLeaves");
        std::vector<std::tuple<int64_t, std::vector<int64_t>, Coords>> out;
        out.reserve(count);
        for (uint32_t i = 0; i < count; ++i) {
            Coords b = take_array(mins[i], dim);
            Coords mx = take_array(maxs[i], dim);
            b.insert(b.end(), mx.begin(), mx.end());
            out.emplace_back(ids[i], take_array(children[i], sizes[i]), std::move(b));
        }
        for (void *p : {static_cast<void *>(sizes), static_cast<void *>(ids),
                        static_cast<void *>(children), static_cast<void *>(mins),
                        static_cast<void *>(maxs)}) {
            if (p != nullptr) {
                Index_Free(p);
            }
        }
        return out;
    }

#ifdef RTREE_HAVE_ARRAY_API
    int64_t intersects_id_v(const py::array &mins, const py::array &maxs, py::array ids,
                            py::array counts) {
        check_box_arrays(mins, maxs);
        require_dtype<int64_t>(ids, "ids");
        require_dtype<uint64_t>(counts, "counts");
        const int64_t n = mins.shape(0);
        const uint32_t d = static_cast<uint32_t>(mins.shape(1));
        const uint64_t di = n ? elem_stride(mins, 0) : 0, dj = elem_stride(mins, 1);
        IndexH h = get();
        const auto *pmin = static_cast<const double *>(mins.data());
        const auto *pmax = static_cast<const double *>(maxs.data());
        auto *pids = static_cast<int64_t *>(ids.mutable_data());
        auto *pcnt = static_cast<uint64_t *>(counts.mutable_data());
        const uint64_t idsz = static_cast<uint64_t>(ids.size());
        int64_t nr = 0;
        RTError rc;
        {
            py::gil_scoped_release nogil;
            rc = Index_Intersects_id_v(h, n, d, idsz, di, dj, pmin, pmax, pids, pcnt, &nr);
        }
        check_rc(rc, "Index_Intersects_id_v");
        return nr;
    }

    int64_t nearest_id_v(int64_t knn, const py::array &mins, const py::array &maxs, py::array ids,
                         py::array counts, std::optional<py::array> dists) {
        check_box_arrays(mins, maxs);
        require_dtype<int64_t>(ids, "ids");
        require_dtype<uint64_t>(counts, "counts");
        double *pd = nullptr;
        if (dists) {
            require_dtype<double>(*dists, "dists");
            pd = static_cast<double *>(dists->mutable_data());
        }
        const int64_t n = mins.shape(0);
        const uint32_t d = static_cast<uint32_t>(mins.shape(1));
        const uint64_t di = n ? elem_stride(mins, 0) : 0, dj = elem_stride(mins, 1);
        IndexH h = get();
        const auto *pmin = static_cast<const double *>(mins.data());
        const auto *pmax = static_cast<const double *>(maxs.data());
        auto *pids = static_cast<int64_t *>(ids.mutable_data());
        auto *pcnt = static_cast<uint64_t *>(counts.mutable_data());
        const uint64_t idsz = static_cast<uint64_t>(ids.size());
        int64_t nr = 0;
        RTError rc;
        {
            py::gil_scoped_release nogil;
            rc = Index_NearestNeighbors_id_v(h, knn, n, d, idsz, di, dj, pmin, pmax, pids, pcnt,
                                             pd, &nr);
        }
        check_rc(rc, "Index_NearestNeighbors_id_v");
        return nr;
    }
#endif

    // -- TPR-tree ----------------------------------------------------------

    void tp_insert(int64_t id, Coords mins, Coords maxs, Coords vmins, Coords vmaxs,
                   double t_start, double t_end, std::optional<py::bytes> data) {
        require_same_dim(mins, maxs, "insert");
        require_same_dim(vmins, vmaxs, "insert velocities");
        const uint8_t *buf = &k_no_data;
        size_t len = 0;
        if (data) {
            char *b = nullptr;
            Py_ssize_t n = 0;
            PyBytes_AsStringAndSize(data->ptr(), &b, &n);
            buf = reinterpret_cast<const uint8_t *>(b);
            len = static_cast<size_t>(n);
        }
        check_rc(Index_InsertTPData(get(), id, mins.data(), maxs.data(), vmins.data(),
                                    vmaxs.data(), t_start, t_end,
                                    static_cast<uint32_t>(mins.size()), buf, len),
                 "Index_InsertTPData");
    }

    void tp_remove(int64_t id, Coords mins, Coords maxs, Coords vmins, Coords vmaxs,
                   double t_start, double t_end) {
        require_same_dim(mins, maxs, "delete");
        require_same_dim(vmins, vmaxs, "delete velocities");
        check_rc(Index_DeleteTPData(get(), id, mins.data(), maxs.data(), vmins.data(),
                                    vmaxs.data(), t_start, t_end,
                                    static_cast<uint32_t>(mins.size())),
                 "Index_DeleteTPData");
    }

    uint64_t tp_intersects_count(Coords mins, Coords maxs, Coords vmins, Coords vmaxs,
                                 double t_start, double t_end) {
        require_same_dim(mins, maxs, "count");
        uint64_t n = 0;
        check_rc(Index_TPIntersects_count(get(), mins.data(), maxs.data(), vmins.data(),
                                          vmaxs.data(), t_start, t_end,
                                          static_cast<uint32_t>(mins.size()), &n),
                 "Index_TPIntersects_count");
        return n;
    }

    using TPIdQuery = RTError (*)(IndexH, double *, double *, double *, double *, double, double,
                                  uint32_t, int64_t **, uint64_t *);
    using TPObjQuery = RTError (*)(IndexH, double *, double *, double *, double *, double,
                                   double, uint32_t, IndexItemH **, uint64_t *);

    std::vector<int64_t> tp_run_id(TPIdQuery fn, const char *name, Coords &mins, Coords &maxs,
                                   Coords &vmins, Coords &vmaxs, double t0, double t1,
                                   uint64_t n_in = 0) {
        require_same_dim(mins, maxs, name);
        int64_t *ids = nullptr;
        uint64_t n = n_in;
        check_rc(fn(get(), mins.data(), maxs.data(), vmins.data(), vmaxs.data(), t0, t1,
                    static_cast<uint32_t>(mins.size()), &ids, &n),
                 name);
        return take_array(ids, n);
    }

    std::vector<IndexItem> tp_run_obj(TPObjQuery fn, const char *name, Coords &mins,
                                      Coords &maxs, Coords &vmins, Coords &vmaxs, double t0,
                                      double t1, uint64_t n_in = 0) {
        require_same_dim(mins, maxs, name);
        IndexItemH *items = nullptr;
        uint64_t n = n_in;
        check_rc(fn(get(), mins.data(), maxs.data(), vmins.data(), vmaxs.data(), t0, t1,
                    static_cast<uint32_t>(mins.size()), &items, &n),
                 name);
        return take_items(items, n);
    }

    // -- misc --------------------------------------------------------------

    bool is_valid() {
        uint32_t v = Index_IsValid(get());
        check_err("Index_IsValid");
        return v != 0;
    }
    void clear_buffer() {
        Index_ClearBuffer(get());
        check_err("Index_ClearBuffer");
    }
    void flush() {
        Index_Flush(get());
        check_err("Index_Flush");
    }
    int64_t get_result_set_offset() {
        int64_t v = Index_GetResultSetOffset(get());
        check_err("Index_GetResultSetOffset");
        return v;
    }
    void set_result_set_offset(int64_t v) {
        check_rc(Index_SetResultSetOffset(get(), v), "Index_SetResultSetOffset");
    }
    int64_t get_result_set_limit() {
        int64_t v = Index_GetResultSetLimit(get());
        check_err("Index_GetResultSetLimit");
        return v;
    }
    void set_result_set_limit(int64_t v) {
        check_rc(Index_SetResultSetLimit(get(), v), "Index_SetResultSetLimit");
    }

  private:
    explicit IndexHandle(IndexH h) : h_(h) {}
    IndexH get() const {
        if (h_ == nullptr) {
            raise_invalid_handle();
        }
        return h_;
    }
    IndexH h_;
};

}  // namespace

// ---------------------------------------------------------------------------
// Property accessor macros: one line per C getter/setter pair.
// ---------------------------------------------------------------------------

#define RTREE_PROP(cls, pyname, CName, T)                                                     \
    cls.def_property(                                                                         \
        pyname,                                                                               \
        [](PropertyHandle &p) -> T {                                                          \
            T v = static_cast<T>(IndexProperty_Get##CName(p.get()));                          \
            check_err("IndexProperty_Get" #CName);                                            \
            return v;                                                                         \
        },                                                                                    \
        [](PropertyHandle &p, T v) {                                                          \
            check_rc(IndexProperty_Set##CName(p.get(), v), "IndexProperty_Set" #CName);       \
        })

#define RTREE_PROP_ENUM(cls, pyname, CName, CEnum)                                            \
    cls.def_property(                                                                         \
        pyname,                                                                               \
        [](PropertyHandle &p) -> int {                                                        \
            int v = static_cast<int>(IndexProperty_Get##CName(p.get()));                      \
            check_err("IndexProperty_Get" #CName);                                            \
            return v;                                                                         \
        },                                                                                    \
        [](PropertyHandle &p, int v) {                                                        \
            check_rc(IndexProperty_Set##CName(p.get(), static_cast<CEnum>(v)),                \
                     "IndexProperty_Set" #CName);                                             \
        })

#define RTREE_PROP_STR(cls, pyname, CName)                                                    \
    cls.def_property(                                                                         \
        pyname,                                                                               \
        [](PropertyHandle &p) -> std::string {                                                \
            char *s = IndexProperty_Get##CName(p.get());                                      \
            check_err("IndexProperty_Get" #CName);                                            \
            return take_c_string(s);                                                          \
        },                                                                                    \
        [](PropertyHandle &p, const std::string &v) {                                         \
            check_rc(IndexProperty_Set##CName(p.get(), v.c_str()), "IndexProperty_Set" #CName); \
        })

// Not declared free-threading safe yet: libspatialindex keeps per-index state
// without locking, and its MSVC build uses a global (not thread-local) error
// stack.  See docs/pybind11-port.md.
PYBIND11_MODULE(_core, m) {
    m.doc() = "Compiled bindings to the libspatialindex C API.";

    auto exc = py::module_::import("rtree.exceptions");
    g_rtree_error = exc.attr("RTreeError").ptr();
    g_invalid_handle = exc.attr("InvalidHandleException").ptr();
    Py_INCREF(g_rtree_error);
    Py_INCREF(g_invalid_handle);

    m.def(
        "sidx_version",
        []() { return take_c_string(SIDX_Version()); },
        "Version string of the libspatialindex C library that is linked at runtime.");
    m.attr("SIDX_VERSION_COMPILED") = py::typing::Tuple<py::int_, py::int_, py::int_>(
        py::make_tuple(SIDX_VERSION_MAJOR, SIDX_VERSION_MINOR, SIDX_VERSION_REV));

    m.def(
        "new_buffer",
        [](size_t n) { return reinterpret_cast<uintptr_t>(SIDX_NewBuffer(n)); }, "size"_a,
        "Allocate ``size`` bytes with libspatialindex's allocator and return the\n"
        "address.  For CustomStorageBase.loadByteArray implementations; the\n"
        "library takes ownership of the buffer.");

#ifdef RTREE_HAVE_CONTAINS
    m.attr("HAS_CONTAINS") = true;
#else
    m.attr("HAS_CONTAINS") = false;
#endif
#ifdef RTREE_HAVE_ARRAY_API
    m.attr("HAS_ARRAY_API") = true;
#else
    m.attr("HAS_ARRAY_API") = false;
#endif

    py::class_<ErrorRef>(m, "ErrorRef",
                         "Mutable error code passed to CustomStorage callbacks.\n\n"
                         "Compatible with the old ctypes pointer: both ``err.value = X`` and\n"
                         "``err.contents.value = X`` set the code.")
        .def_readwrite("value", &ErrorRef::value)
        .def_property_readonly(
            "contents", [](ErrorRef &e) -> ErrorRef & { return e; },
            py::return_value_policy::reference_internal);

    py::class_<IndexItem>(m, "IndexItem", "An entry returned by an ``*_obj`` query.")
        .def_property_readonly("id", &IndexItem::id)
        .def_property_readonly("data", &IndexItem::data,
                               "The raw stored bytes, or None if nothing was stored.")
        .def_property_readonly("bounds", &IndexItem::bounds,
                               "(mins, maxs) of the entry, or None for an empty entry.");

    // -- PropertyHandle ----------------------------------------------------
    py::class_<PropertyHandle> prop(m, "PropertyHandle", "Owned libspatialindex property set.");
    prop.def(py::init<>())
        .def("destroy", &PropertyHandle::destroy)
        .def("__bool__", &PropertyHandle::valid)
        .def("set_python_storage", &PropertyHandle::set_python_storage, "storage"_a,
             "Route RT_Custom storage callbacks to a Python CustomStorage object.")
        .def_property(
            "custom_storage_callbacks",
            [](PropertyHandle &p) -> std::optional<uintptr_t> {
                void *v = IndexProperty_GetCustomStorageCallbacks(p.get());
                check_err("IndexProperty_GetCustomStorageCallbacks");
                if (v == nullptr) {
                    return std::nullopt;
                }
                return reinterpret_cast<uintptr_t>(v);
            },
            [](PropertyHandle &p, uintptr_t addr) {
                check_rc(IndexProperty_SetCustomStorageCallbacks(
                             p.get(), reinterpret_cast<const void *>(addr)),
                         "IndexProperty_SetCustomStorageCallbacks");
            },
            "Raw address of a CustomStorageManagerCallbacks struct (advanced use).");

    RTREE_PROP_ENUM(prop, "index_type", IndexType, RTIndexType);
    RTREE_PROP_ENUM(prop, "index_variant", IndexVariant, RTIndexVariant);
    RTREE_PROP_ENUM(prop, "index_storage", IndexStorage, RTStorageType);
    RTREE_PROP(prop, "dimension", Dimension, uint32_t);
    RTREE_PROP(prop, "pagesize", Pagesize, uint32_t);
    RTREE_PROP(prop, "index_capacity", IndexCapacity, uint32_t);
    RTREE_PROP(prop, "leaf_capacity", LeafCapacity, uint32_t);
    RTREE_PROP(prop, "leaf_pool_capacity", LeafPoolCapacity, uint32_t);
    RTREE_PROP(prop, "index_pool_capacity", IndexPoolCapacity, uint32_t);
    RTREE_PROP(prop, "region_pool_capacity", RegionPoolCapacity, uint32_t);
    RTREE_PROP(prop, "point_pool_capacity", PointPoolCapacity, uint32_t);
    RTREE_PROP(prop, "buffering_capacity", BufferingCapacity, uint32_t);
    RTREE_PROP(prop, "ensure_tight_mbrs", EnsureTightMBRs, uint32_t);
    RTREE_PROP(prop, "overwrite", Overwrite, uint32_t);
    RTREE_PROP(prop, "near_minimum_overlap_factor", NearMinimumOverlapFactor, uint32_t);
    RTREE_PROP(prop, "write_through", WriteThrough, uint32_t);
    RTREE_PROP(prop, "fill_factor", FillFactor, double);
    RTREE_PROP(prop, "split_distribution_factor", SplitDistributionFactor, double);
    RTREE_PROP(prop, "tpr_horizon", TPRHorizon, double);
    RTREE_PROP(prop, "reinsert_factor", ReinsertFactor, double);
    RTREE_PROP(prop, "custom_storage_callbacks_size", CustomStorageCallbacksSize, uint32_t);
    RTREE_PROP(prop, "index_id", IndexID, int64_t);
    RTREE_PROP_STR(prop, "filename", FileName);
    RTREE_PROP_STR(prop, "dat_extension", FileNameExtensionDat);
    RTREE_PROP_STR(prop, "idx_extension", FileNameExtensionIdx);

    // -- IndexHandle -------------------------------------------------------
    using Q = IndexHandle;
    py::class_<IndexHandle> idx(m, "IndexHandle", "Owned libspatialindex index.");
    idx.def(py::init<PropertyHandle &>(), "properties"_a, py::keep_alive<1, 2>())
        .def_static("from_stream", &IndexHandle::from_stream, "properties"_a, "next_item"_a,
                    py::keep_alive<0, 1>(),
                    "Bulk-load from ``next_item()`` which returns ``(id, mins, maxs, data)``\n"
                    "tuples and ``None`` when exhausted.")
#ifdef RTREE_HAVE_ARRAY_API
        .def_static("from_arrays", &IndexHandle::from_arrays, "properties"_a, "ids"_a, "mins"_a,
                    "maxs"_a, py::keep_alive<0, 1>())
        .def("intersects_id_v", &IndexHandle::intersects_id_v, "mins"_a, "maxs"_a, "ids"_a,
             "counts"_a)
        .def("nearest_id_v", &IndexHandle::nearest_id_v, "knn"_a, "mins"_a, "maxs"_a, "ids"_a,
             "counts"_a, "dists"_a = py::none())
#endif
#ifdef RTREE_HAVE_CONTAINS
        .def(
            "contains_id",
            [](Q &q, Coords mins, Coords maxs) {
                return q.run_id(&Index_Contains_id, "Index_Contains_id", mins, maxs);
            },
            "mins"_a, "maxs"_a)
        .def(
            "contains_obj",
            [](Q &q, Coords mins, Coords maxs) {
                return q.run_obj(&Index_Contains_obj, "Index_Contains_obj", mins, maxs);
            },
            "mins"_a, "maxs"_a)
#endif
        .def("destroy", &IndexHandle::destroy)
        .def("__bool__", &IndexHandle::valid_handle)
        .def("insert", &IndexHandle::insert, "id"_a, "mins"_a, "maxs"_a, "data"_a = py::none())
        .def("delete", &IndexHandle::remove, "id"_a, "mins"_a, "maxs"_a)
        .def("intersects_count", &IndexHandle::intersects_count, "mins"_a, "maxs"_a)
        .def(
            "intersects_id",
            [](Q &q, Coords mins, Coords maxs) {
                return q.run_id(&Index_Intersects_id, "Index_Intersects_id", mins, maxs);
            },
            "mins"_a, "maxs"_a)
        .def(
            "intersects_obj",
            [](Q &q, Coords mins, Coords maxs) {
                return q.run_obj(&Index_Intersects_obj, "Index_Intersects_obj", mins, maxs);
            },
            "mins"_a, "maxs"_a)
        .def(
            "nearest_id",
            [](Q &q, Coords mins, Coords maxs, uint64_t num_results) {
                return q.run_id(&Index_NearestNeighbors_id, "Index_NearestNeighbors_id", mins,
                                maxs, num_results);
            },
            "mins"_a, "maxs"_a, "num_results"_a)
        .def(
            "nearest_obj",
            [](Q &q, Coords mins, Coords maxs, uint64_t num_results) {
                return q.run_obj(&Index_NearestNeighbors_obj, "Index_NearestNeighbors_obj", mins,
                                 maxs, num_results);
            },
            "mins"_a, "maxs"_a, "num_results"_a)
        .def("bounds", &IndexHandle::bounds, "(mins, maxs) of the whole index, or None.")
        .def("leaves", &IndexHandle::leaves,
             "List of (leaf id, child ids, [mins..., maxs...]) tuples.")
        .def("tp_insert", &IndexHandle::tp_insert, "id"_a, "mins"_a, "maxs"_a, "vmins"_a,
             "vmaxs"_a, "t_start"_a, "t_end"_a, "data"_a = py::none())
        .def("tp_delete", &IndexHandle::tp_remove, "id"_a, "mins"_a, "maxs"_a, "vmins"_a,
             "vmaxs"_a, "t_start"_a, "t_end"_a)
        .def("tp_intersects_count", &IndexHandle::tp_intersects_count, "mins"_a, "maxs"_a,
             "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a)
        .def(
            "tp_intersects_id",
            [](Q &q, Coords a, Coords b, Coords va, Coords vb, double t0, double t1) {
                return q.tp_run_id(&Index_TPIntersects_id, "Index_TPIntersects_id", a, b, va, vb,
                                   t0, t1);
            },
            "mins"_a, "maxs"_a, "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a)
        .def(
            "tp_intersects_obj",
            [](Q &q, Coords a, Coords b, Coords va, Coords vb, double t0, double t1) {
                return q.tp_run_obj(&Index_TPIntersects_obj, "Index_TPIntersects_obj", a, b, va,
                                    vb, t0, t1);
            },
            "mins"_a, "maxs"_a, "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a)
        .def(
            "tp_nearest_id",
            [](Q &q, Coords a, Coords b, Coords va, Coords vb, double t0, double t1,
               uint64_t num) {
                return q.tp_run_id(&Index_TPNearestNeighbors_id, "Index_TPNearestNeighbors_id", a,
                                   b, va, vb, t0, t1, num);
            },
            "mins"_a, "maxs"_a, "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a, "num_results"_a)
        .def(
            "tp_nearest_obj",
            [](Q &q, Coords a, Coords b, Coords va, Coords vb, double t0, double t1,
               uint64_t num) {
                return q.tp_run_obj(&Index_TPNearestNeighbors_obj, "Index_TPNearestNeighbors_obj",
                                    a, b, va, vb, t0, t1, num);
            },
            "mins"_a, "maxs"_a, "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a, "num_results"_a)
        .def("is_valid", &IndexHandle::is_valid)
        .def("clear_buffer", &IndexHandle::clear_buffer)
        .def("flush", &IndexHandle::flush)
        .def_property("result_set_offset", &IndexHandle::get_result_set_offset,
                      &IndexHandle::set_result_set_offset)
        .def_property("result_set_limit", &IndexHandle::get_result_set_limit,
                      &IndexHandle::set_result_set_limit);
}

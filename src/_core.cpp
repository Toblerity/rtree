// pybind11 bindings for libspatialindex, using its C++ API directly.
//
// Earlier revisions of this module bound the C API (sidx_api.h, i.e.
// libspatialindex_c), which is itself a C++ -> C shim with its own index
// wrapper, visitors, result paging, error stack and custom-storage manager.
// This version skips that layer: it drives SpatialIndex::ISpatialIndex,
// IStorageManager, IVisitor and IQueryStrategy itself, so
//
// * results are collected straight into std::vector / owned records instead of
//   being cloned (twice, for objects), malloc'd into C arrays and copied again;
// * result paging (limit/offset) happens inside the visitor, so skipped hits are
//   never materialised;
// * errors are C++ exceptions translated once, instead of a global error stack
//   that has to be polled after every call;
// * custom storage calls Python directly instead of going through a C callback
//   table (the ctypes-level table is still accepted for CustomStorageBase);
// * only libspatialindex (not libspatialindex_c) is needed at build time.
//
// The Python-facing API of ``rtree._core`` is unchanged from the C-API version
// so the two can be compared like for like.

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/typing.h>

// libspatialindex throws its own exception types (Tools::Exception is not a
// std::exception) across the shared-library boundary. pybind11 builds this
// module with -fvisibility=hidden, and libc++ (macOS, and clang on Linux)
// matches exception types by type_info *address*, so with hidden visibility
// `catch (Tools::Exception&)` silently fails to match an exception thrown by
// libspatialindex.dylib. Give the library's declarations default visibility
// so their type_info resolves to the library's own symbols.
#if defined(__GNUC__) || defined(__clang__)
#pragma GCC visibility push(default)
#endif
#include <spatialindex/SpatialIndex.h>
#if defined(__GNUC__) || defined(__clang__)
#pragma GCC visibility pop
#endif

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <exception>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

namespace py = pybind11;
using namespace py::literals;
namespace SI = SpatialIndex;
using SI::id_type;

#ifndef SIDX_VERSION_NUM
#define SIDX_VERSION_NUM 0
#endif

namespace {

// Values of rtree.index.RT_* (identical to the C API's enums).
enum : uint32_t { RT_RTree = 0, RT_MVRTree = 1, RT_TPRTree = 2 };
enum : uint32_t { RT_Memory = 0, RT_Disk = 1, RT_Custom = 2 };

// Custom storage error codes (rtree.index.ICustomStorage).
enum : int { NoError = 0, InvalidPageError = 1, IllegalStateError = 2 };
constexpr id_type NewPage = -1;

PyObject *g_rtree_error = nullptr;
PyObject *g_invalid_handle = nullptr;

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------

[[noreturn]] void raise_rtree(const char *func, const std::string &msg) {
    std::string full = std::string("Error in \"") + func + "\": " + msg;
    PyErr_SetString(g_rtree_error, full.c_str());
    throw py::error_already_set();
}

[[noreturn]] void raise_invalid_handle() {
    PyErr_SetString(g_invalid_handle, "Handle has been destroyed");
    throw py::error_already_set();
}

// Run ``f`` (optionally without the GIL) and turn libspatialindex exceptions
// into RTreeError once the GIL is held again.
template <typename F> void run(const char *func, F &&f, bool release_gil = true) {
    std::string msg;
    {
        std::optional<py::gil_scoped_release> nogil;
        if (release_gil) {
            nogil.emplace();
        }
        try {
            f();
            return;
        } catch (py::error_already_set &) {
            throw;  // already a Python exception (only raised with the GIL held)
        } catch (Tools::Exception &e) {
            msg = e.what();
        } catch (std::exception &e) {
            msg = e.what();
        } catch (...) {
            msg = "Unknown Error";
        }
    }
    raise_rtree(func, msg);
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

const uint8_t k_no_data = 0;

// Borrow the buffer of an optional ``bytes``.
std::pair<const uint8_t *, uint32_t> bytes_view(const std::optional<py::bytes> &data) {
    if (!data) {
        return {nullptr, 0};
    }
    char *b = nullptr;
    Py_ssize_t n = 0;
    if (PyBytes_AsStringAndSize(data->ptr(), &b, &n) != 0) {
        throw py::error_already_set();
    }
    return {reinterpret_cast<const uint8_t *>(b), static_cast<uint32_t>(n)};
}

// ---------------------------------------------------------------------------
// Coordinates: parsed from any float sequence or buffer, entirely in C++
// ---------------------------------------------------------------------------

// A Python argument accepted as coordinates.  Only its stub annotation is
// special; parsing happens in Box.
class CoordsArg : public py::object {
  public:
    PYBIND11_OBJECT_DEFAULT(CoordsArg, object, [](PyObject *o) { return o != nullptr; })
};

// An entry id taken as a plain object so that coordinates are validated
// before the id's type, matching the historical error precedence.
class IdArg : public py::object {
  public:
    PYBIND11_OBJECT_DEFAULT(IdArg, object, [](PyObject *o) { return o != nullptr; })
    int64_t value() const {
        PyObject *i = PyNumber_Index(ptr());  // TypeError for None, floats, ...
        if (i == nullptr) {
            throw py::error_already_set();
        }
        const long long v = PyLong_AsLongLong(i);
        Py_DECREF(i);
        if (v == -1 && PyErr_Occurred()) {
            throw py::error_already_set();
        }
        return static_cast<int64_t>(v);
    }
};

// mins/maxs for one query or entry, built the way rtree has always
// interpreted coordinates:
//   * ``dim`` values: a point;
//   * ``2*dim`` values: a box, ``[mins..., maxs...]`` when ``interleaved`` else
//     ``[min0, max0, min1, max1, ...]``.
// Small dimensions (the common case) live on the stack.
class Box {
  public:
    Box(py::handle coords, uint32_t dim, bool interleaved, bool validate = true) : dim_(dim) {
        buf_ = 2 * static_cast<size_t>(dim) <= kInline ? inline_ : (heap_.resize(2 * dim), heap_.data());
        double *vals = scratch(2 * static_cast<size_t>(dim));
        const size_t n = read_values(coords, vals, 2 * static_cast<size_t>(dim));
        if (n == dim) {
            std::copy(vals, vals + dim, buf_);
            std::copy(vals, vals + dim, buf_ + dim);
            return;
        }
        if (n != 2 * static_cast<size_t>(dim)) {
            throw py::value_error("Expected " + std::to_string(dim) + " or " +
                                  std::to_string(2 * dim) + " coordinates, got " +
                                  std::to_string(n));
        }
        for (uint32_t i = 0; i < dim; ++i) {
            buf_[i] = interleaved ? vals[i] : vals[2 * i];
            buf_[dim + i] = interleaved ? vals[dim + i] : vals[2 * i + 1];
        }
        if (validate) {
            for (uint32_t i = 0; i < dim; ++i) {
                if (!(buf_[i] <= buf_[dim + i])) {
                    PyErr_SetString(g_rtree_error,
                                    "Coordinates must not have minimums more than maximums");
                    throw py::error_already_set();
                }
            }
        }
    }
    Box(const Box &) = delete;
    Box &operator=(const Box &) = delete;

    const double *lo() const { return buf_; }
    const double *hi() const { return buf_ + dim_; }
    uint32_t dim() const { return dim_; }
    SI::Region region() const { return SI::Region(lo(), hi(), dim_); }
    bool degenerate() const {
        double length = 0;
        for (uint32_t i = 0; i < dim_; ++i) {
            length += std::fabs(buf_[i] - buf_[dim_ + i]);
        }
        return length <= std::numeric_limits<double>::epsilon();
    }

  private:
    static constexpr size_t kInline = 16;

    double *scratch(size_t n) {
        if (n <= kInline) {
            return scratch_inline_;
        }
        scratch_heap_.resize(n);
        return scratch_heap_.data();
    }

    // Returns the number of values; writes at most ``cap`` of them.
    static size_t read_values(py::handle obj, double *out, size_t cap) {
        PyObject *o = obj.ptr();
        // Fast path: a 1-D float64 buffer (NumPy array, array.array('d'), ...).
        if (PyObject_CheckBuffer(o) && !PyBytes_Check(o) && !PyByteArray_Check(o)) {
            Py_buffer view;
            if (PyObject_GetBuffer(o, &view, PyBUF_FORMAT | PyBUF_STRIDES) == 0) {
                const bool f64 = view.itemsize == 8 && view.format != nullptr &&
                                 (std::strcmp(view.format, "d") == 0 ||
                                  std::strcmp(view.format, "<d") == 0 ||
                                  std::strcmp(view.format, "=d") == 0);
                if (f64 && view.ndim == 1) {
                    const auto n = static_cast<size_t>(view.shape[0]);
                    const auto *base = static_cast<const char *>(view.buf);
                    for (size_t i = 0; i < n && i < cap; ++i) {
                        std::memcpy(&out[i], base + i * view.strides[0], sizeof(double));
                    }
                    PyBuffer_Release(&view);
                    return n;
                }
                PyBuffer_Release(&view);
            } else {
                PyErr_Clear();
            }
        }
        // General path: any sequence of numbers.
        py::object seq = py::reinterpret_steal<py::object>(
            PySequence_Fast(o, "coordinates must be a sequence of numbers"));
        if (!seq) {
            throw py::error_already_set();
        }
        const auto n = static_cast<size_t>(PySequence_Fast_GET_SIZE(seq.ptr()));
        PyObject **items = PySequence_Fast_ITEMS(seq.ptr());
        for (size_t i = 0; i < n && i < cap; ++i) {
            const double v = PyFloat_AsDouble(items[i]);
            if (v == -1.0 && PyErr_Occurred()) {
                throw py::error_already_set();
            }
            out[i] = v;
        }
        return n;
    }

    uint32_t dim_;
    double *buf_;
    double inline_[kInline];
    double scratch_inline_[kInline];
    std::vector<double> heap_, scratch_heap_;
};

// Hand a vector of ids to NumPy without copying.
py::array_t<int64_t> to_array(std::vector<int64_t> &&v) {
    if (v.empty()) {
        return py::array_t<int64_t>(0);
    }
    auto *owned = new std::vector<int64_t>(std::move(v));
    py::capsule owner(owned, [](void *p) { delete static_cast<std::vector<int64_t> *>(p); });
    return py::array_t<int64_t>(static_cast<py::ssize_t>(owned->size()), owned->data(), owner);
}

// ---------------------------------------------------------------------------
// Query result records and visitors
// ---------------------------------------------------------------------------

// Everything rtree needs from an IData, extracted once while visiting.
struct ItemRecord {
    int64_t id = 0;
    uint32_t dim = 0;
    std::vector<double> bounds;  // lows then highs
    std::unique_ptr<uint8_t[]> data;
    uint32_t len = 0;
};

void fill_mbr(const SI::IShape &shape, uint32_t &dim, std::vector<double> &out) {
    SI::Region r;
    shape.getMBR(r);
    dim = r.getDimension();
    out.resize(2 * static_cast<size_t>(dim));
    for (uint32_t i = 0; i < dim; ++i) {
        out[i] = r.getLow(i);
        out[dim + i] = r.getHigh(i);
    }
}

// Applies rtree's result_offset / result_limit while visiting: hits outside the
// window are counted but never stored.
struct Pager {
    int64_t offset = 0, limit = 0, seen = 0;
    bool keep() {
        const int64_t i = seen++;
        return limit == 0 || (i >= offset && i < offset + limit);
    }
};

struct IdVisitor : SI::IVisitor {
    std::vector<int64_t> ids;
    Pager pager;
    void visitNode(const SI::INode &) override {}
    void visitData(const SI::IData &d) override {
        if (pager.keep()) {
            ids.push_back(d.getIdentifier());
        }
    }
    void visitData(std::vector<const SI::IData *> &) override {}
};

struct ObjVisitor : SI::IVisitor {
    std::vector<ItemRecord> items;
    Pager pager;
    void visitNode(const SI::INode &) override {}
    void visitData(const SI::IData &d) override {
        if (!pager.keep()) {
            return;
        }
        ItemRecord rec;
        rec.id = d.getIdentifier();
        SI::IShape *s = nullptr;
        d.getShape(&s);
        std::unique_ptr<SI::IShape> shape(s);
        fill_mbr(*shape, rec.dim, rec.bounds);
        uint8_t *p = nullptr;
        d.getData(rec.len, &p);
        rec.data.reset(p);
        items.push_back(std::move(rec));
    }
    void visitData(std::vector<const SI::IData *> &) override {}
};

struct CountVisitor : SI::IVisitor {
    uint64_t n = 0;
    void visitNode(const SI::INode &) override {}
    void visitData(const SI::IData &) override { ++n; }
    void visitData(std::vector<const SI::IData *> &) override {}
};

// Root MBR of the tree (what Index_GetBounds reported).
struct BoundsQuery : SI::IQueryStrategy {
    uint32_t dim = 0;
    std::vector<double> bounds;
    void getNextEntry(const SI::IEntry &e, id_type &, bool &hasNext) override {
        SI::IShape *s = nullptr;
        e.getShape(&s);
        std::unique_ptr<SI::IShape> shape(s);
        fill_mbr(*shape, dim, bounds);
        hasNext = false;
    }
};

using Leaf = std::tuple<int64_t, std::vector<int64_t>, Coords>;

// Breadth-first walk collecting every leaf node (what Index_GetLeaves did).
struct LeafQuery : SI::IQueryStrategy {
    std::vector<Leaf> leaves;
    std::vector<id_type> queue;
    size_t head = 0;
    void getNextEntry(const SI::IEntry &e, id_type &next, bool &hasNext) override {
        const auto *n = dynamic_cast<const SI::INode *>(&e);
        if (n != nullptr) {
            const uint32_t c = n->getChildrenCount();
            if (n->getLevel() > 0) {
                for (uint32_t i = 0; i < c; ++i) {
                    queue.push_back(n->getChildIdentifier(i));
                }
            }
            if (n->isLeaf()) {
                std::vector<int64_t> ids(c);
                for (uint32_t i = 0; i < c; ++i) {
                    ids[i] = n->getChildIdentifier(i);
                }
                SI::IShape *s = nullptr;
                n->getShape(&s);
                std::unique_ptr<SI::IShape> shape(s);
                uint32_t dim = 0;
                Coords b;
                fill_mbr(*shape, dim, b);
                leaves.emplace_back(n->getIdentifier(), std::move(ids), std::move(b));
            }
        }
        hasNext = head < queue.size();
        if (hasNext) {
            next = queue[head++];
        }
    }
};

// ---------------------------------------------------------------------------
// IndexItem: an owned result from an ``*_obj`` query
// ---------------------------------------------------------------------------

class IndexItem {
  public:
    explicit IndexItem(ItemRecord &&r) : r_(std::move(r)) {}
    int64_t id() const { return r_.id; }
    std::optional<py::bytes> data() const {
        if (r_.len == 0) {
            return std::nullopt;
        }
        return py::bytes(reinterpret_cast<const char *>(r_.data.get()), r_.len);
    }
    std::optional<Bounds> bounds() const {
        if (r_.dim == 0) {
            return std::nullopt;
        }
        auto mid = r_.bounds.begin() + r_.dim;
        return Bounds{Coords(r_.bounds.begin(), mid), Coords(mid, r_.bounds.end())};
    }

  private:
    ItemRecord r_;
};

std::vector<IndexItem> to_items(std::vector<ItemRecord> &recs) {
    std::vector<IndexItem> out;
    out.reserve(recs.size());
    for (auto &r : recs) {
        out.emplace_back(std::move(r));
    }
    return out;
}

// ---------------------------------------------------------------------------
// Custom storage
// ---------------------------------------------------------------------------

void throw_storage_error(int code, id_type page) {
    switch (code) {
    case NoError:
        return;
    case InvalidPageError:
        throw SI::InvalidPageException(page);
    case IllegalStateError:
        throw Tools::IllegalStateException("CustomStorage: Error in user implementation.");
    default:
        throw Tools::IllegalStateException("CustomStorage: Unknown error.");
    }
}

// Stand-in for the ``ctypes.POINTER(c_int)`` the old callbacks received.
// ``err.contents.value = X`` and ``err.value = X`` both work.
struct ErrorRef {
    int value = 0;
};

// Storage manager backed by a Python ``rtree.index.CustomStorage``.
class PythonStorage final : public SI::IStorageManager {
  public:
    explicit PythonStorage(py::object storage) : s_(std::move(storage)) {
        call(NewPage, [&](py::object &e) { s_.attr("create")(e); });
    }
    ~PythonStorage() override {
        try {
            call(NewPage, [&](py::object &e) { s_.attr("destroy")(e); });
        } catch (...) {
            // Destructors must not throw; the error was already reported.
        }
        py::gil_scoped_acquire gil;
        s_ = py::object();
    }
    void flush() override {
        call(NewPage, [&](py::object &e) { s_.attr("flush")(e); });
    }
    void loadByteArray(const id_type page, uint32_t &len, uint8_t **data) override {
        call(page, [&](py::object &e) {
            py::object r = s_.attr("loadByteArray")(page, e);
            if (e.cast<ErrorRef &>().value != NoError) {
                return;
            }
            char *buf = nullptr;
            Py_ssize_t n = 0;
            if (PyBytes_AsStringAndSize(r.ptr(), &buf, &n) != 0) {
                throw py::error_already_set();
            }
            // libspatialindex takes ownership and delete[]s the page.
            auto out = std::make_unique<uint8_t[]>(static_cast<size_t>(n));
            std::memcpy(out.get(), buf, static_cast<size_t>(n));
            len = static_cast<uint32_t>(n);
            *data = out.release();
        });
    }
    void storeByteArray(id_type &page, const uint32_t len, const uint8_t *const data) override {
        call(page, [&](py::object &e) {
            py::bytes b(reinterpret_cast<const char *>(data), len);
            py::object r = s_.attr("storeByteArray")(page, b, e);
            if (!r.is_none()) {
                page = r.cast<id_type>();
            }
        });
    }
    void deleteByteArray(const id_type page) override {
        call(page, [&](py::object &e) { s_.attr("deleteByteArray")(page, e); });
    }

  private:
    template <typename F> void call(id_type page, F &&f) {
        int code = NoError;
        {
            py::gil_scoped_acquire gil;
            // Python owns the ErrorRef, so a callback that keeps a reference to
            // it cannot leave a dangling pointer behind.
            py::object err = py::cast(ErrorRef{});
            try {
                f(err);
                code = err.cast<ErrorRef &>().value;
            } catch (py::error_already_set &e) {
                e.discard_as_unraisable("rtree custom storage callback");
                code = IllegalStateError;
            }
        }
        throw_storage_error(code, page);
    }
    py::object s_;
};

// Mirror of libspatialindex_c's CustomStorageManagerCallbacks, which is what
// rtree.index.CustomStorageCallbacks (ctypes) lays out.  Used only by
// CustomStorageBase, whose callbacks work on raw buffers.
struct RawCallbacks {
    void *context;
    void (*createCallback)(const void *context, int *errorCode);
    void (*destroyCallback)(const void *context, int *errorCode);
    void (*flushCallback)(const void *context, int *errorCode);
    void (*loadByteArrayCallback)(const void *context, const id_type page, uint32_t *len,
                                  uint8_t **data, int *errorCode);
    void (*storeByteArrayCallback)(const void *context, id_type *page, const uint32_t len,
                                   const uint8_t *const data, int *errorCode);
    void (*deleteByteArrayCallback)(const void *context, const id_type page, int *errorCode);
};

class RawCallbackStorage final : public SI::IStorageManager {
  public:
    explicit RawCallbackStorage(const RawCallbacks &cb) : cb_(cb) {
        int ec = NoError;
        if (cb_.createCallback) {
            with_gil([&] { cb_.createCallback(cb_.context, &ec); });
        }
        throw_storage_error(ec, NewPage);
    }
    ~RawCallbackStorage() override {
        int ec = NoError;
        if (cb_.destroyCallback) {
            with_gil([&] { cb_.destroyCallback(cb_.context, &ec); });
        }
    }
    void flush() override {
        int ec = NoError;
        if (cb_.flushCallback) {
            with_gil([&] { cb_.flushCallback(cb_.context, &ec); });
        }
        throw_storage_error(ec, NewPage);
    }
    void loadByteArray(const id_type page, uint32_t &len, uint8_t **data) override {
        int ec = NoError;
        if (cb_.loadByteArrayCallback) {
            with_gil([&] { cb_.loadByteArrayCallback(cb_.context, page, &len, data, &ec); });
        }
        throw_storage_error(ec, page);
    }
    void storeByteArray(id_type &page, const uint32_t len, const uint8_t *const data) override {
        int ec = NoError;
        if (cb_.storeByteArrayCallback) {
            with_gil([&] { cb_.storeByteArrayCallback(cb_.context, &page, len, data, &ec); });
        }
        throw_storage_error(ec, page);
    }
    void deleteByteArray(const id_type page) override {
        int ec = NoError;
        if (cb_.deleteByteArrayCallback) {
            with_gil([&] { cb_.deleteByteArrayCallback(cb_.context, page, &ec); });
        }
        throw_storage_error(ec, page);
    }

  private:
    // ctypes callbacks acquire the GIL themselves, but being explicit keeps us
    // correct if the callbacks are ever implemented in Python some other way.
    template <typename F> static void with_gil(F &&f) {
        py::gil_scoped_acquire gil;
        f();
    }
    RawCallbacks cb_;
};

// ---------------------------------------------------------------------------
// PropertyHandle: a Tools::PropertySet with rtree's defaults
// ---------------------------------------------------------------------------

class PropertyHandle {
  public:
    PropertyHandle() {
        // Same defaults as libspatialindex_c's GetDefaults().
        set_double("FillFactor", 0.7);
        set_ulong("IndexCapacity", 100);
        set_ulong("LeafCapacity", 100);
        set_long("TreeVariant", SI::RTree::RV_RSTAR);
        set_ulong("NearMinimumOverlapFactor", 32);
        set_double("SplitDistributionFactor", 0.4);
        set_double("ReinsertFactor", 0.3);
        set_ulong("Dimension", 2);
        set_bool("EnsureTightMBRs", true);
        set_ulong("IndexPoolCapacity", 100);
        set_ulong("LeafPoolCapacity", 100);
        set_ulong("RegionPoolCapacity", 1000);
        set_ulong("PointPoolCapacity", 500);
        set_double("Horizon", 20.0);
        set_ulong("Capacity", 10);
        set_bool("WriteThrough", false);
        set_bool("Overwrite", true);
        set_str("FileName", "");
        set_ulong("PageSize", 4096);
        set_ulong("IndexStorageType", RT_Disk);
        set_ulong("IndexType", RT_RTree);
        set_str("FileNameDat", "dat");
        set_str("FileNameIdx", "idx");
    }
    PropertyHandle(const PropertyHandle &) = delete;
    PropertyHandle &operator=(const PropertyHandle &) = delete;

    void destroy() { valid_ = false; }
    bool valid() const { return valid_; }

    // -- typed accessors -----------------------------------------------------

    Tools::Variant get(const char *key) const {
        check();
        Tools::Variant v = ps_.getProperty(key);
        if (v.m_varType == Tools::VT_EMPTY) {
            raise_rtree("PropertyHandle.get", std::string("Property ") + key + " was empty");
        }
        return v;
    }
    template <typename T> T get_as(const char *key, Tools::VariantType vt) const {
        Tools::Variant v = get(key);
        if (v.m_varType != vt) {
            raise_rtree("PropertyHandle.get",
                        std::string("Property ") + key + " has an unexpected type");
        }
        switch (vt) {
        case Tools::VT_ULONG:
            return static_cast<T>(v.m_val.ulVal);
        case Tools::VT_LONG:
            return static_cast<T>(v.m_val.lVal);
        case Tools::VT_LONGLONG:
            return static_cast<T>(v.m_val.llVal);
        case Tools::VT_DOUBLE:
            return static_cast<T>(v.m_val.dblVal);
        case Tools::VT_BOOL:
            return static_cast<T>(v.m_val.blVal);
        default:
            raise_rtree("PropertyHandle.get", "unsupported property type");
        }
    }
    void set_var(const char *key, const Tools::Variant &v) {
        check();
        ps_.setProperty(key, v);
    }
    void set_ulong(const char *key, uint32_t x) {
        Tools::Variant v;
        v.m_varType = Tools::VT_ULONG;
        v.m_val.ulVal = x;
        set_var(key, v);
    }
    void set_long(const char *key, int32_t x) {
        Tools::Variant v;
        v.m_varType = Tools::VT_LONG;
        v.m_val.lVal = x;
        set_var(key, v);
    }
    void set_llong(const char *key, int64_t x) {
        Tools::Variant v;
        v.m_varType = Tools::VT_LONGLONG;
        v.m_val.llVal = x;
        set_var(key, v);
    }
    void set_double(const char *key, double x) {
        Tools::Variant v;
        v.m_varType = Tools::VT_DOUBLE;
        v.m_val.dblVal = x;
        set_var(key, v);
    }
    void set_bool(const char *key, bool x) {
        Tools::Variant v;
        v.m_varType = Tools::VT_BOOL;
        v.m_val.blVal = x;
        set_var(key, v);
    }
    // PropertySet stores a bare char*; keep the characters alive here.
    void set_str(const char *key, const std::string &s) {
        auto &slot = strings_[key];
        slot = std::make_shared<std::string>(s);
        Tools::Variant v;
        v.m_varType = Tools::VT_PCHAR;
        v.m_val.pcVal = const_cast<char *>(slot->c_str());
        set_var(key, v);
    }
    std::string get_str(const char *key) const {
        Tools::Variant v = get(key);
        if (v.m_varType != Tools::VT_PCHAR) {
            raise_rtree("PropertyHandle.get", std::string("Property ") + key + " must be a string");
        }
        return v.m_val.pcVal ? std::string(v.m_val.pcVal) : std::string();
    }

    // -- storage -------------------------------------------------------------

    void set_python_storage(py::object storage) { py_storage_ = std::move(storage); }

    std::optional<uintptr_t> raw_callbacks_address() const {
        check();
        if (!raw_) {
            return std::nullopt;
        }
        return reinterpret_cast<uintptr_t>(&*raw_);
    }
    void set_raw_callbacks(uintptr_t addr) {
        check();
        if (addr == 0) {
            raw_.reset();
            return;
        }
        if (raw_size_ != sizeof(RawCallbacks)) {
            raise_rtree("PropertyHandle.custom_storage_callbacks",
                        "The supplied storage callbacks size is wrong, expected " +
                            std::to_string(sizeof(RawCallbacks)) + ", got " +
                            std::to_string(raw_size_));
        }
        raw_ = *reinterpret_cast<const RawCallbacks *>(addr);
    }
    uint32_t raw_size_ = 0;

    // Build the storage manager for a new index from these properties.
    std::unique_ptr<SI::IStorageManager> make_storage(Tools::PropertySet &ps) const {
        const uint32_t kind = get_as<uint32_t>("IndexStorageType", Tools::VT_ULONG);
        switch (kind) {
        case RT_Memory:
            return std::unique_ptr<SI::IStorageManager>(
                SI::StorageManager::returnMemoryStorageManager(ps));
        case RT_Disk: {
            if (get_str("FileName").empty()) {
                throw std::runtime_error(
                    "Spatial Index Error: filename was empty. Set IndexStorageType to RT_Memory");
            }
            return std::unique_ptr<SI::IStorageManager>(
                SI::StorageManager::returnDiskStorageManager(ps));
        }
        case RT_Custom:
            if (py_storage_) {
                return std::make_unique<PythonStorage>(py_storage_);
            }
            if (raw_) {
                return std::make_unique<RawCallbackStorage>(*raw_);
            }
            throw std::runtime_error("RT_Custom storage requested but no callbacks were set");
        default:
            throw std::runtime_error("Invalid IndexStorageType");
        }
    }

    // Snapshot for an index: the set itself plus owned copies of its strings.
    Tools::PropertySet snapshot(std::vector<std::shared_ptr<std::string>> &keep) const {
        check();
        Tools::PropertySet copy = ps_;
        for (const auto &kv : strings_) {
            keep.push_back(kv.second);
        }
        return copy;
    }

  private:
    void check() const {
        if (!valid_) {
            raise_invalid_handle();
        }
    }
    Tools::PropertySet ps_;
    std::map<std::string, std::shared_ptr<std::string>> strings_;
    std::optional<RawCallbacks> raw_;
    py::object py_storage_;
    bool valid_ = true;
};

// ---------------------------------------------------------------------------
// Bulk-load data streams
// ---------------------------------------------------------------------------

// Pulls ``(id, coordinates, obj)`` items from a Python iterator; coordinates
// are parsed in C++ and ``obj`` is serialized with ``dumps`` unless None.
class PyDataStream final : public SI::IDataStream {
  public:
    PyDataStream(py::iterator it, uint32_t dim, bool interleaved, py::function dumps)
        : it_(std::move(it)), dumps_(std::move(dumps)), dim_(dim), interleaved_(interleaved) {
        read();
    }
    SI::IData *getNext() override {
        SI::IData *r = pending_.release();
        read();
        return r;
    }
    bool hasNext() override { return pending_ != nullptr; }
    uint32_t size() override { throw Tools::NotSupportedException("Operation not supported."); }
    void rewind() override { throw Tools::NotSupportedException("Operation not supported."); }
    std::exception_ptr error;

  private:
    void read() {
        if (done_) {
            return;
        }
        try {
            PyObject *item = PyIter_Next(it_.ptr());
            if (item == nullptr) {
                if (PyErr_Occurred()) {
                    throw py::error_already_set();
                }
                done_ = true;
                return;
            }
            py::object entry = py::reinterpret_steal<py::object>(item);
            py::object seq = py::reinterpret_steal<py::object>(
                PySequence_Fast(entry.ptr(), "stream items must be (id, coordinates, obj)"));
            if (!seq) {
                throw py::error_already_set();
            }
            if (PySequence_Fast_GET_SIZE(seq.ptr()) != 3) {
                throw py::value_error("stream items must be (id, coordinates, obj)");
            }
            PyObject **f = PySequence_Fast_ITEMS(seq.ptr());
            const auto id = py::reinterpret_borrow<py::object>(f[0]).cast<int64_t>();
            // The ctypes-era stream never validated min <= max; keep that.
            Box box(f[1], dim_, interleaved_, /*validate=*/false);
            const uint8_t *buf = nullptr;
            uint32_t len = 0;
            if (f[2] != Py_None) {
                data_ = dumps_(py::reinterpret_borrow<py::object>(f[2]));
                std::tie(buf, len) = bytes_view(data_.cast<py::bytes>());
            }
            SI::Region region = box.region();
            // RTree::Data copies the payload.
            pending_.reset(new SI::RTree::Data(len, const_cast<uint8_t *>(buf), region, id));
        } catch (...) {
            error = std::current_exception();
            done_ = true;
        }
    }
    py::iterator it_;
    py::function dumps_;
    py::object data_;
    std::unique_ptr<SI::RTree::Data> pending_;
    uint32_t dim_;
    bool interleaved_;
    bool done_ = false;
};

// Reads boxes straight out of strided NumPy buffers.
class ArrayStream final : public SI::IDataStream {
  public:
    ArrayStream(uint64_t n, uint32_t d, uint64_t i_stri, uint64_t d_i_stri, uint64_t d_j_stri,
                const int64_t *ids, const double *mins, const double *maxs)
        : n_(n), d_(d), i_stri_(i_stri), di_(d_i_stri), dj_(d_j_stri), ids_(ids), mins_(mins),
          maxs_(maxs), tmp_(2 * static_cast<size_t>(d)) {}
    SI::IData *getNext() override {
        if (i_ >= n_) {
            return nullptr;
        }
        for (uint32_t j = 0; j < d_; ++j) {
            tmp_[j] = mins_[i_ * di_ + j * dj_];
            tmp_[j + d_] = maxs_[i_ * di_ + j * dj_];
        }
        SI::Region r(tmp_.data(), tmp_.data() + d_, d_);
        return new SI::RTree::Data(0, nullptr, r, ids_[i_++ * i_stri_]);
    }
    bool hasNext() override { return i_ < n_; }
    uint32_t size() override { return static_cast<uint32_t>(n_); }
    void rewind() override { i_ = 0; }

  private:
    uint64_t i_ = 0, n_;
    uint32_t d_;
    uint64_t i_stri_, di_, dj_;
    const int64_t *ids_;
    const double *mins_, *maxs_;
    std::vector<double> tmp_;
};

// ---------------------------------------------------------------------------
// numpy helpers
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
// IndexHandle: storage manager + buffer + tree
// ---------------------------------------------------------------------------

bool is_degenerate(const Coords &a, const Coords &b) {
    double length = 0;
    for (size_t i = 0; i < a.size(); ++i) {
        length += std::fabs(a[i] - b[i]);
    }
    return length <= std::numeric_limits<double>::epsilon();
}

class IndexHandle {
  public:
    explicit IndexHandle(PropertyHandle &p) {
        run("Index_Create", [&] {
            prepare(p);
            build(nullptr);
        }, false);
    }

    using DumpsFn = py::typing::Callable<py::bytes(py::object)>;

    static std::unique_ptr<IndexHandle> from_stream(PropertyHandle &p,
                                                    py::typing::Iterable<py::object> stream_in,
                                                    bool interleaved, DumpsFn dumps) {
        std::unique_ptr<IndexHandle> h(new IndexHandle());
        run("Index_CreateWithStream", [&] { h->prepare(p); }, false);
        PyDataStream stream(py::iter(stream_in), h->dim_, interleaved, std::move(dumps));
        // Keep the GIL: the stream calls back into Python.
        std::string msg;
        try {
            h->build(&stream);
        } catch (py::error_already_set &) {
            throw;
        } catch (Tools::Exception &e) {
            msg = e.what();
        } catch (std::exception &e) {
            msg = e.what();
        } catch (...) {
            msg = "Unknown Error";
        }
        if (stream.error) {
            h.reset();
            std::rethrow_exception(stream.error);
        }
        if (!msg.empty()) {
            raise_rtree("Index_CreateWithStream", msg);
        }
        return h;
    }

    static std::unique_ptr<IndexHandle> from_arrays(PropertyHandle &p, const py::array &ids,
                                                    const py::array &mins, const py::array &maxs) {
        require_dtype<int64_t>(ids, "ids");
        check_box_arrays(mins, maxs);
        if (ids.ndim() != 1 || ids.shape(0) != mins.shape(0)) {
            throw py::value_error("index and point counts different");
        }
        const auto n = static_cast<uint64_t>(mins.shape(0));
        const auto d = static_cast<uint32_t>(mins.shape(1));
        ArrayStream stream(n, d, elem_stride(ids, 0), n ? elem_stride(mins, 0) : 0,
                           elem_stride(mins, 1), static_cast<const int64_t *>(ids.data()),
                           static_cast<const double *>(mins.data()),
                           static_cast<const double *>(maxs.data()));
        std::unique_ptr<IndexHandle> h(new IndexHandle());
        run("Index_CreateWithArray", [&] { h->prepare(p); }, false);
        run("Index_CreateWithArray", [&] { h->build(&stream); });
        return h;
    }

    IndexHandle(const IndexHandle &) = delete;
    IndexHandle &operator=(const IndexHandle &) = delete;
    ~IndexHandle() { close(); }

    void destroy() {
        run("Index_Destroy", [&] { close(); }, false);
    }
    bool valid_handle() const { return tree_ != nullptr; }

    // -- mutation ----------------------------------------------------------

    void insert(const IdArg &id_arg, const CoordsArg &coords, bool interleaved,
                std::optional<py::bytes> data) {
        auto &t = tree();
        Box box(coords, dim_, interleaved);
        const int64_t id = id_arg.value();
        auto [buf, len] = bytes_view(data);
        run("Index_InsertData", [&] {
            if (box.degenerate()) {
                t.insertData(len, buf, SI::Point(box.lo(), box.dim()), id);
            } else {
                t.insertData(len, buf, box.region(), id);
            }
        });
    }

    void remove(const IdArg &id_arg, const CoordsArg &coords, bool interleaved) {
        auto &t = tree();
        Box box(coords, dim_, interleaved);
        const int64_t id = id_arg.value();
        run("Index_DeleteData", [&] { t.deleteData(box.region(), id); });
    }

    // -- queries -----------------------------------------------------------

    uint64_t count(const CoordsArg &coords, bool interleaved) {
        auto &t = tree();
        Box box(coords, dim_, interleaved);
        CountVisitor v;
        run("Index_Intersects_count", [&] { t.intersectsWithQuery(box.region(), v); });
        return v.n;
    }

    enum class Kind { Intersects, Contains, Nearest };

    template <typename Visitor>
    void region_query(Kind kind, const char *name, const CoordsArg &coords, bool interleaved,
                      Visitor &v, uint32_t k = 0) {
        auto &t = tree();
        Box box(coords, dim_, interleaved);
        v.pager = Pager{offset_, limit_, 0};
        run(name, [&] {
            SI::Region r = box.region();
            switch (kind) {
            case Kind::Intersects:
                t.intersectsWithQuery(r, v);
                break;
            case Kind::Contains:
                t.containsWhatQuery(r, v);
                break;
            case Kind::Nearest:
                t.nearestNeighborQuery(k, r, v);
                break;
            }
        });
    }

    py::array_t<int64_t> query_id(Kind kind, const char *name, const CoordsArg &coords,
                                  bool interleaved, uint32_t k = 0) {
        IdVisitor v;
        region_query(kind, name, coords, interleaved, v, k);
        return to_array(std::move(v.ids));
    }
    std::vector<IndexItem> query_obj(Kind kind, const char *name, const CoordsArg &coords,
                                     bool interleaved, uint32_t k = 0) {
        ObjVisitor v;
        region_query(kind, name, coords, interleaved, v, k);
        return to_items(v.items);
    }

    std::optional<Bounds> bounds() {
        auto &t = tree();
        BoundsQuery q;
        run("Index_GetBounds", [&] { t.queryStrategy(q); }, false);
        if (q.dim == 0) {
            return std::nullopt;
        }
        auto mid = q.bounds.begin() + q.dim;
        return Bounds{Coords(q.bounds.begin(), mid), Coords(mid, q.bounds.end())};
    }

    std::vector<Leaf> leaves() {
        auto &t = tree();
        LeafQuery q;
        run("Index_GetLeaves", [&] { t.queryStrategy(q); });
        return std::move(q.leaves);
    }

    int64_t intersects_id_v(const py::array &mins, const py::array &maxs, py::array ids,
                            py::array counts) {
        check_box_arrays(mins, maxs);
        require_dtype<int64_t>(ids, "ids");
        require_dtype<uint64_t>(counts, "counts");
        const int64_t n = mins.shape(0);
        const auto d = static_cast<uint32_t>(mins.shape(1));
        const uint64_t di = n ? elem_stride(mins, 0) : 0, dj = elem_stride(mins, 1);
        const auto *pmin = static_cast<const double *>(mins.data());
        const auto *pmax = static_cast<const double *>(maxs.data());
        auto *pids = static_cast<int64_t *>(ids.mutable_data());
        auto *pcnt = static_cast<uint64_t *>(counts.mutable_data());
        const auto idsz = static_cast<uint64_t>(ids.size());
        auto &t = tree();
        int64_t nr = 0;
        run("Index_Intersects_id_v", [&] {
            std::vector<double> tmp(2 * static_cast<size_t>(d));
            IdVisitor v;
            uint64_t k = 0;
            for (int64_t i = 0; i < n; ++i) {
                for (uint32_t j = 0; j < d; ++j) {
                    tmp[j] = pmin[i * di + j * dj];
                    tmp[j + d] = pmax[i * di + j * dj];
                }
                v.ids.clear();
                t.intersectsWithQuery(SI::Region(tmp.data(), tmp.data() + d, d), v);
                const uint64_t nrc = v.ids.size();
                pcnt[i] = nrc;
                if (k + nrc > idsz) {
                    return;
                }
                nr = i + 1;
                std::copy(v.ids.begin(), v.ids.end(), pids + k);
                k += nrc;
            }
        });
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
#ifndef RTREE_HAVE_NN_MAXDIST
        if (pd != nullptr) {
            throw py::value_error("max_dists/return_max_dists need libspatialindex >= 1.9");
        }
#endif
        const int64_t n = mins.shape(0);
        const auto d = static_cast<uint32_t>(mins.shape(1));
        const uint64_t di = n ? elem_stride(mins, 0) : 0, dj = elem_stride(mins, 1);
        const auto *pmin = static_cast<const double *>(mins.data());
        const auto *pmax = static_cast<const double *>(maxs.data());
        auto *pids = static_cast<int64_t *>(ids.mutable_data());
        auto *pcnt = static_cast<uint64_t *>(counts.mutable_data());
        const auto idsz = static_cast<uint64_t>(ids.size());
        const auto kabs = static_cast<uint32_t>(knn < 0 ? -knn : knn);
        auto &t = tree();
        int64_t nr = 0;
        run("Index_NearestNeighbors_id_v", [&] {
            std::vector<double> tmp(2 * static_cast<size_t>(d));
            IdVisitor v;
            uint64_t k = 0;
            for (int64_t i = 0; i < n; ++i) {
                for (uint32_t j = 0; j < d; ++j) {
                    tmp[j] = pmin[i * di + j * dj];
                    tmp[j + d] = pmax[i * di + j * dj];
                }
                v.ids.clear();
                SI::Region r(tmp.data(), tmp.data() + d, d);
#ifdef RTREE_HAVE_NN_MAXDIST
                double max_dist = pd ? pd[i] : 0.0;
                max_dist = t.nearestNeighborQuery(kabs, r, v, max_dist);
                if (pd) {
                    pd[i] = max_dist;
                }
#else
                t.nearestNeighborQuery(kabs, r, v);
#endif
                uint64_t nrc = v.ids.size();
                if (knn < 0) {
                    nrc = std::min<uint64_t>(nrc, kabs);
                }
                pcnt[i] = nrc;
                if (k + nrc > idsz) {
                    return;
                }
                nr = i + 1;
                std::copy(v.ids.begin(), v.ids.begin() + static_cast<std::ptrdiff_t>(nrc),
                          pids + k);
                k += nrc;
            }
        });
        return nr;
    }

    // -- TPR-tree ----------------------------------------------------------

    static void require_tp(const Coords &a, const Coords &b, const Coords &va, const Coords &vb,
                           const char *what) {
        require_same_dim(a, b, what);
        require_same_dim(va, vb, what);
        if (va.size() != a.size()) {
            throw py::value_error(std::string(what) +
                                  ": velocities must have the same dimension as coordinates");
        }
    }

    void tp_insert(int64_t id, Coords mins, Coords maxs, Coords vmins, Coords vmaxs,
                   double t_start, double t_end, std::optional<py::bytes> data) {
        require_tp(mins, maxs, vmins, vmaxs, "insert");
        auto [buf, len] = bytes_view(data);
        auto &t = tree();
        const auto dim = static_cast<uint32_t>(mins.size());
        run("Index_InsertTPData", [&] {
            if (is_degenerate(mins, maxs) && is_degenerate(vmins, vmaxs)) {
                t.insertData(len, buf,
                             SI::MovingPoint(mins.data(), vmins.data(), t_start, t_end, dim), id);
            } else {
                t.insertData(len, buf,
                             SI::MovingRegion(mins.data(), maxs.data(), vmins.data(),
                                              vmaxs.data(), t_start, t_end, dim),
                             id);
            }
        });
    }

    void tp_remove(int64_t id, Coords mins, Coords maxs, Coords vmins, Coords vmaxs,
                   double t_start, double t_end) {
        require_tp(mins, maxs, vmins, vmaxs, "delete");
        auto &t = tree();
        run("Index_DeleteTPData", [&] {
            t.deleteData(SI::MovingRegion(mins.data(), maxs.data(), vmins.data(), vmaxs.data(),
                                          t_start, t_end, static_cast<uint32_t>(mins.size())),
                         id);
        });
    }

    template <typename Visitor>
    void tp_query(bool nearest, const char *name, Coords &a, Coords &b, Coords &va, Coords &vb,
                  double t0, double t1, Visitor &v, uint32_t k = 0) {
        require_tp(a, b, va, vb, name);
        auto &t = tree();
        run(name, [&] {
            SI::MovingRegion r(a.data(), b.data(), va.data(), vb.data(), t0, t1,
                               static_cast<uint32_t>(a.size()));
            if (nearest) {
                t.nearestNeighborQuery(k, r, v);
            } else {
                t.intersectsWithQuery(r, v);
            }
        });
    }

    uint64_t tp_intersects_count(Coords a, Coords b, Coords va, Coords vb, double t0, double t1) {
        CountVisitor v;
        tp_query(false, "Index_TPIntersects_count", a, b, va, vb, t0, t1, v);
        return v.n;
    }
    py::array_t<int64_t> tp_id(bool nearest, const char *name, Coords a, Coords b, Coords va,
                               Coords vb, double t0, double t1, uint32_t k) {
        IdVisitor v;
        v.pager = Pager{offset_, limit_, 0};
        tp_query(nearest, name, a, b, va, vb, t0, t1, v, k);
        return to_array(std::move(v.ids));
    }
    std::vector<IndexItem> tp_obj(bool nearest, const char *name, Coords a, Coords b, Coords va,
                                  Coords vb, double t0, double t1, uint32_t k) {
        ObjVisitor v;
        v.pager = Pager{offset_, limit_, 0};
        tp_query(nearest, name, a, b, va, vb, t0, t1, v, k);
        return to_items(v.items);
    }

    // -- misc --------------------------------------------------------------

    bool is_valid() {
        auto &t = tree();
        bool ok = false;
        run("Index_IsValid", [&] { ok = t.isIndexValid(); });
        return ok;
    }
    void clear_buffer() {
        tree();
        run("Index_ClearBuffer", [&] { buffer_->clear(); });
    }
    void flush() {
        auto &t = tree();
        run("Index_Flush", [&] {
#ifdef RTREE_HAVE_TREE_FLUSH
            t.flush();
#else
            (void)t;  // libspatialindex < 1.9: only the storage can be flushed
#endif
            storage_->flush();
        });
    }
    uint32_t dimension() {
        tree();
        return dim_;
    }
    int64_t result_set_offset() {
        tree();
        return offset_;
    }
    void set_result_set_offset(int64_t v) {
        tree();
        offset_ = v;
    }
    int64_t result_set_limit() {
        tree();
        return limit_;
    }
    void set_result_set_limit(int64_t v) {
        tree();
        limit_ = v;
    }

  private:
    IndexHandle() = default;

    SI::ISpatialIndex &tree() const {
        if (tree_ == nullptr) {
            raise_invalid_handle();
        }
        return *tree_;
    }

    // Everything that reads Python-side state; needs the GIL.
    void prepare(PropertyHandle &p) {
        props_ = p.snapshot(strings_);
        type_ = p.get_as<uint32_t>("IndexType", Tools::VT_ULONG);
        dim_ = p.get_as<uint32_t>("Dimension", Tools::VT_ULONG);
        kind_ = p.get_as<uint32_t>("IndexStorageType", Tools::VT_ULONG);
        storage_ = p.make_storage(props_);
        buffer_.reset(SI::StorageManager::returnRandomEvictionsBuffer(*storage_, props_));
    }

    // Build the tree; pure C++ unless custom storage calls back into Python.
    void build(SI::IDataStream *stream) {
        const auto type = type_;
        if (stream != nullptr) {
            if (type != RT_RTree) {
                throw std::runtime_error("bulk loading is only supported for RTree indexes");
            }
            if (kind_ == RT_Memory) {
                // Keep the external sorter entirely in memory.
                Tools::Variant v;
                v.m_varType = Tools::VT_ULONG;
                v.m_val.ulVal = 1073741824;
                props_.setProperty("ExternalSortBufferPageSize", v);
                v.m_val.ulVal = 2;
                props_.setProperty("ExternalSortBufferTotalPages", v);
            }
            id_type index_id = 0;
            Tools::Variant v = props_.getProperty("IndexIdentifier");
            if (v.m_varType == Tools::VT_LONGLONG) {
                index_id = v.m_val.llVal;
            }
#if SIDX_VERSION_NUM >= 1900
            tree_.reset(SI::RTree::createAndBulkLoadNewRTree(SI::RTree::BLM_STR, *stream,
                                                             *buffer_, props_, index_id));
#else
            // 1.8.x ignores ExternalSortBuffer* in the PropertySet overload's
            // favour of on-disk temp files; use the explicit overload like
            // libspatialindex_c 1.8.5 did.
            auto num = [&](const char *key, auto dflt) {
                Tools::Variant x = props_.getProperty(key);
                using T = decltype(dflt);
                if (x.m_varType == Tools::VT_ULONG) return static_cast<T>(x.m_val.ulVal);
                if (x.m_varType == Tools::VT_LONG) return static_cast<T>(x.m_val.lVal);
                if (x.m_varType == Tools::VT_DOUBLE) return static_cast<T>(x.m_val.dblVal);
                return dflt;
            };
            tree_.reset(SI::RTree::createAndBulkLoadNewRTree(
                SI::RTree::BLM_STR, *stream, *buffer_, num("FillFactor", 0.7),
                num("IndexCapacity", 100u), num("LeafCapacity", 100u), num("Dimension", 2u),
                static_cast<SI::RTree::RTreeVariant>(num("TreeVariant", 2)), index_id));
#endif
            return;
        }
        switch (type) {
        case RT_RTree:
            tree_.reset(SI::RTree::returnRTree(*buffer_, props_));
            break;
        case RT_MVRTree:
            tree_.reset(SI::MVRTree::returnMVRTree(*buffer_, props_));
            break;
        case RT_TPRTree:
            tree_.reset(SI::TPRTree::returnTPRTree(*buffer_, props_));
            break;
        default:
            throw std::runtime_error("Invalid IndexType");
        }
    }

    // Tear down in dependency order: tree -> buffer -> storage.
    void close() {
        tree_.reset();
        buffer_.reset();
        storage_.reset();
    }

    Tools::PropertySet props_;
    std::vector<std::shared_ptr<std::string>> strings_;
    std::unique_ptr<SI::IStorageManager> storage_;
    std::unique_ptr<SI::StorageManager::IBuffer> buffer_;
    std::unique_ptr<SI::ISpatialIndex> tree_;
    int64_t offset_ = 0, limit_ = 0;
    uint32_t type_ = RT_RTree, kind_ = RT_Memory, dim_ = 2;
};

std::string version_string() {
#ifdef SIDX_RELEASE_NAME
    return SIDX_RELEASE_NAME;
#else
    return std::to_string(SIDX_VERSION_MAJOR) + "." + std::to_string(SIDX_VERSION_MINOR) + "." +
           std::to_string(SIDX_VERSION_REV);
#endif
}

}  // namespace

namespace pybind11::detail {
template <> struct handle_type_name<IdArg> {
    static constexpr auto name = const_name("int");
};
template <> struct handle_type_name<CoordsArg> {
    static constexpr auto name =
        const_name("collections.abc.Sequence[float] | numpy.typing.NDArray[typing.Any]");
};
}  // namespace pybind11::detail

// ---------------------------------------------------------------------------
// Property accessor macros
// ---------------------------------------------------------------------------

#define RTREE_PROP_ULONG(cls, pyname, key)                                                    \
    cls.def_property(                                                                         \
        pyname, [](PropertyHandle &p) { return p.get_as<uint32_t>(key, Tools::VT_ULONG); },   \
        [](PropertyHandle &p, uint32_t v) { p.set_ulong(key, v); })

#define RTREE_PROP_DOUBLE(cls, pyname, key)                                                   \
    cls.def_property(                                                                         \
        pyname, [](PropertyHandle &p) { return p.get_as<double>(key, Tools::VT_DOUBLE); },    \
        [](PropertyHandle &p, double v) { p.set_double(key, v); })

#define RTREE_PROP_BOOL(cls, pyname, key)                                                     \
    cls.def_property(                                                                         \
        pyname,                                                                               \
        [](PropertyHandle &p) {                                                               \
            return static_cast<uint32_t>(p.get_as<bool>(key, Tools::VT_BOOL));                \
        },                                                                                    \
        [](PropertyHandle &p, uint32_t v) {                                                   \
            if (v > 1) {                                                                      \
                raise_rtree("PropertyHandle." pyname,                                         \
                            key " is a boolean value and must be 1 or 0");                    \
            }                                                                                 \
            p.set_bool(key, v != 0);                                                          \
        })

#define RTREE_PROP_ENUM(cls, pyname, key, setter, maxval)                                     \
    cls.def_property(                                                                         \
        pyname,                                                                               \
        [](PropertyHandle &p) -> int {                                                        \
            Tools::Variant v = p.get(key);                                                    \
            return v.m_varType == Tools::VT_LONG ? v.m_val.lVal                               \
                                                 : static_cast<int>(v.m_val.ulVal);           \
        },                                                                                    \
        [](PropertyHandle &p, int v) {                                                        \
            if (v < 0 || v > (maxval)) {                                                      \
                raise_rtree("PropertyHandle." pyname, "Inputted value is not valid");         \
            }                                                                                 \
            p.setter(key, v);                                                                 \
        })

#define RTREE_PROP_STR(cls, pyname, key)                                                      \
    cls.def_property(                                                                         \
        pyname, [](PropertyHandle &p) { return p.get_str(key); },                             \
        [](PropertyHandle &p, const std::string &v) { p.set_str(key, v); })

// Not declared free-threading safe yet: libspatialindex keeps per-index state
// without locking.  See docs/pybind11-port.md.
PYBIND11_MODULE(_core, m) {
    m.doc() = "Compiled bindings to the libspatialindex C++ API.";

    auto exc = py::module_::import("rtree.exceptions");
    g_rtree_error = exc.attr("RTreeError").ptr();
    g_invalid_handle = exc.attr("InvalidHandleException").ptr();
    Py_INCREF(g_rtree_error);
    Py_INCREF(g_invalid_handle);

    m.def("sidx_version", &version_string,
          "Version of the libspatialindex headers this extension was built against.");
    m.attr("SIDX_VERSION_COMPILED") = py::typing::Tuple<py::int_, py::int_, py::int_>(
        py::make_tuple(SIDX_VERSION_MAJOR, SIDX_VERSION_MINOR, SIDX_VERSION_REV));
    m.def(
        "new_buffer",
        [](size_t n) { return reinterpret_cast<uintptr_t>(new uint8_t[n]); }, "size"_a,
        "Allocate ``size`` bytes the way libspatialindex expects (``new[]``) and\n"
        "return the address.  For CustomStorageBase.loadByteArray implementations;\n"
        "the library takes ownership of the buffer.");

    // The C++ API has these everywhere; kept for API compatibility.
    m.attr("HAS_CONTAINS") = true;
    m.attr("HAS_ARRAY_API") = true;

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
    py::class_<PropertyHandle> prop(m, "PropertyHandle", "libspatialindex property set.");
    prop.def(py::init<>())
        .def("destroy", &PropertyHandle::destroy)
        .def("__bool__", &PropertyHandle::valid)
        .def("set_python_storage", &PropertyHandle::set_python_storage, "storage"_a,
             "Route RT_Custom storage to a Python CustomStorage object.")
        .def_property(
            "custom_storage_callbacks", &PropertyHandle::raw_callbacks_address,
            &PropertyHandle::set_raw_callbacks,
            "Address of a CustomStorageManagerCallbacks struct (CustomStorageBase).")
        .def_property(
            "custom_storage_callbacks_size", [](PropertyHandle &p) { return p.raw_size_; },
            [](PropertyHandle &p, uint32_t v) { p.raw_size_ = v; });

    RTREE_PROP_ENUM(prop, "index_type", "IndexType", set_ulong, 2);
    RTREE_PROP_ENUM(prop, "index_variant", "TreeVariant", set_long, 2);
    RTREE_PROP_ENUM(prop, "index_storage", "IndexStorageType", set_ulong, 2);
    RTREE_PROP_ULONG(prop, "dimension", "Dimension");
    RTREE_PROP_ULONG(prop, "pagesize", "PageSize");
    RTREE_PROP_ULONG(prop, "index_capacity", "IndexCapacity");
    RTREE_PROP_ULONG(prop, "leaf_capacity", "LeafCapacity");
    RTREE_PROP_ULONG(prop, "leaf_pool_capacity", "LeafPoolCapacity");
    RTREE_PROP_ULONG(prop, "index_pool_capacity", "IndexPoolCapacity");
    RTREE_PROP_ULONG(prop, "region_pool_capacity", "RegionPoolCapacity");
    RTREE_PROP_ULONG(prop, "point_pool_capacity", "PointPoolCapacity");
    RTREE_PROP_ULONG(prop, "buffering_capacity", "Capacity");
    RTREE_PROP_BOOL(prop, "ensure_tight_mbrs", "EnsureTightMBRs");
    RTREE_PROP_BOOL(prop, "overwrite", "Overwrite");
    RTREE_PROP_ULONG(prop, "near_minimum_overlap_factor", "NearMinimumOverlapFactor");
    RTREE_PROP_BOOL(prop, "write_through", "WriteThrough");
    RTREE_PROP_DOUBLE(prop, "fill_factor", "FillFactor");
    RTREE_PROP_DOUBLE(prop, "split_distribution_factor", "SplitDistributionFactor");
    RTREE_PROP_DOUBLE(prop, "tpr_horizon", "Horizon");
    RTREE_PROP_DOUBLE(prop, "reinsert_factor", "ReinsertFactor");
    prop.def_property(
        "index_id",
        [](PropertyHandle &p) { return p.get_as<int64_t>("IndexIdentifier", Tools::VT_LONGLONG); },
        [](PropertyHandle &p, int64_t v) { p.set_llong("IndexIdentifier", v); });
    RTREE_PROP_STR(prop, "filename", "FileName");
    RTREE_PROP_STR(prop, "dat_extension", "FileNameDat");
    RTREE_PROP_STR(prop, "idx_extension", "FileNameIdx");

    // -- IndexHandle -------------------------------------------------------
    using Q = IndexHandle;
    using K = IndexHandle::Kind;
    py::class_<IndexHandle> idx(m, "IndexHandle", "Owned libspatialindex index.");
    idx.def(py::init<PropertyHandle &>(), "properties"_a, py::keep_alive<1, 2>())
        .def_static("from_stream", &IndexHandle::from_stream, "properties"_a, "stream"_a,
                    "interleaved"_a, "dumps"_a, py::keep_alive<0, 1>(),
                    "Bulk-load from an iterable of ``(id, coordinates, obj)``; ``obj`` is\n"
                    "stored as ``dumps(obj)`` unless it is None.")
        .def_static("from_arrays", &IndexHandle::from_arrays, "properties"_a, "ids"_a, "mins"_a,
                    "maxs"_a, py::keep_alive<0, 1>())
        .def("intersects_id_v", &IndexHandle::intersects_id_v, "mins"_a, "maxs"_a, "ids"_a,
             "counts"_a)
        .def("nearest_id_v", &IndexHandle::nearest_id_v, "knn"_a, "mins"_a, "maxs"_a, "ids"_a,
             "counts"_a, "dists"_a = py::none())
        .def("destroy", &IndexHandle::destroy)
        .def("__bool__", &IndexHandle::valid_handle)
        .def("insert", &IndexHandle::insert, "id"_a, "coordinates"_a, "interleaved"_a,
             "data"_a = py::none())
        .def("delete", &IndexHandle::remove, "id"_a, "coordinates"_a, "interleaved"_a)
        .def("count", &IndexHandle::count, "coordinates"_a, "interleaved"_a)
        .def(
            "intersection",
            [](Q &q, const CoordsArg &c, bool il) {
                return q.query_id(K::Intersects, "Index_Intersects_id", c, il);
            },
            "coordinates"_a, "interleaved"_a, "Ids of entries intersecting the query.")
        .def(
            "intersection_obj",
            [](Q &q, const CoordsArg &c, bool il) {
                return q.query_obj(K::Intersects, "Index_Intersects_obj", c, il);
            },
            "coordinates"_a, "interleaved"_a)
        .def(
            "contains",
            [](Q &q, const CoordsArg &c, bool il) {
                return q.query_id(K::Contains, "Index_Contains_id", c, il);
            },
            "coordinates"_a, "interleaved"_a, "Ids of entries contained by the query.")
        .def(
            "contains_obj",
            [](Q &q, const CoordsArg &c, bool il) {
                return q.query_obj(K::Contains, "Index_Contains_obj", c, il);
            },
            "coordinates"_a, "interleaved"_a)
        .def(
            "nearest",
            [](Q &q, const CoordsArg &c, bool il, uint32_t k) {
                return q.query_id(K::Nearest, "Index_NearestNeighbors_id", c, il, k);
            },
            "coordinates"_a, "interleaved"_a, "num_results"_a,
            "Ids of the ``num_results`` nearest entries (more on distance ties).")
        .def(
            "nearest_obj",
            [](Q &q, const CoordsArg &c, bool il, uint32_t k) {
                return q.query_obj(K::Nearest, "Index_NearestNeighbors_obj", c, il, k);
            },
            "coordinates"_a, "interleaved"_a, "num_results"_a)
        .def_property_readonly("dimension", &IndexHandle::dimension)
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
                return q.tp_id(false, "Index_TPIntersects_id", a, b, va, vb, t0, t1, 0);
            },
            "mins"_a, "maxs"_a, "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a)
        .def(
            "tp_intersects_obj",
            [](Q &q, Coords a, Coords b, Coords va, Coords vb, double t0, double t1) {
                return q.tp_obj(false, "Index_TPIntersects_obj", a, b, va, vb, t0, t1, 0);
            },
            "mins"_a, "maxs"_a, "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a)
        .def(
            "tp_nearest_id",
            [](Q &q, Coords a, Coords b, Coords va, Coords vb, double t0, double t1, uint32_t k) {
                return q.tp_id(true, "Index_TPNearestNeighbors_id", a, b, va, vb, t0, t1, k);
            },
            "mins"_a, "maxs"_a, "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a, "num_results"_a)
        .def(
            "tp_nearest_obj",
            [](Q &q, Coords a, Coords b, Coords va, Coords vb, double t0, double t1, uint32_t k) {
                return q.tp_obj(true, "Index_TPNearestNeighbors_obj", a, b, va, vb, t0, t1, k);
            },
            "mins"_a, "maxs"_a, "vmins"_a, "vmaxs"_a, "t_start"_a, "t_end"_a, "num_results"_a)
        .def("is_valid", &IndexHandle::is_valid)
        .def("clear_buffer", &IndexHandle::clear_buffer)
        .def("flush", &IndexHandle::flush)
        .def_property("result_set_offset", &IndexHandle::result_set_offset,
                      &IndexHandle::set_result_set_offset)
        .def_property("result_set_limit", &IndexHandle::result_set_limit,
                      &IndexHandle::set_result_set_limit);
}

# Porting rtree from ctypes to pybind11 — investigation notes

Branch: `pybind11` · Tracking issue: [#223](https://github.com/Toblerity/rtree/issues/223)

## TL;DR

A working prototype is on this branch. `rtree/core.py`'s ~700 lines of
hand-written ctypes prototypes are replaced by a pybind11 module
(`src/_core.cpp`) with Python types (`list[float]`, `bytes`, `numpy.ndarray`)
instead of pointers. `rtree/index.py` keeps its public API and now calls the
typed handles.

The module was first written against the libspatialindex **C API**
(`sidx_api.h` / `libspatialindex_c`), and has since been rewritten to drive the
**C++ API** (`SpatialIndex::ISpatialIndex`, visitors, storage managers)
directly, skipping `libspatialindex_c` entirely. The Python-facing `_core`
API — and so `_core.pyi` — is identical between the two, so they can be
compared like for like; see [C API vs C++ API](#c-api-vs-c-api-binding).

| | ctypes (`main`) | pybind11 (this branch) |
|---|---|---|
| Test suite (sidx 2.1.0) | 57 pass | 58 pass (+2 new regression tests, 0 changed expectations except `ctypes.ArgumentError` → `TypeError`) |
| Test suite (sidx 1.8.5) | — | 52 pass, 6 skipped (Contains / array APIs absent, as before) |
| `mypy --strict rtree` | 270 errors (172 index.py, 101 core.py) | 0 in index.py/core.py (2 pre-existing in finder.py) |
| Type info for the binding layer | none (`CDLL` attributes are `Any`) | generated `rtree/_core.pyi` |
| Wheel contents | py3-none wheel + bundled `libspatialindex*.so/.dylib/.dll` + finder/repair scripts | one self-contained extension per CPython version, libspatialindex linked statically (542 KB on linux x86_64; 583 KB for the C-API version) |

## Type hinting — the main goal

1. **The binding layer is typed at the source.** pybind11 emits signatures
   from the C++ types; `scripts/generate_stubs.sh` runs `pybind11-stubgen` and
   writes `rtree/_core.pyi` (committed, shipped in the wheel next to
   `py.typed`). Example:

   ```python
   class IndexHandle:
       def intersects_id(self, mins: Sequence[float], maxs: Sequence[float]) -> list[int]: ...
       def nearest_obj(self, mins, maxs, num_results: int) -> list[IndexItem]: ...
       def bounds(self) -> tuple[list[float], list[float]] | None: ...
       @staticmethod
       def from_stream(properties: PropertyHandle,
                       next_item: Callable[[], tuple[int, list[float], list[float], bytes | None] | None]) -> IndexHandle: ...
   ```

2. **`index.py` can now be checked strictly.** Every method is annotated;
   `pyproject.toml` enables `disallow_untyped_defs` for `rtree.index` /
   `rtree._core`. Once the core was typed, mypy surfaced wrong annotations
   that had been hiding behind `Any`:
   - `fill_factor` / `split_distribution_factor` were annotated `int`; they
     are C `double`s.
   - `_countTP(times: float)` actually takes a `(start, end)` pair.
   - `get_coordinate_pointers()` claimed to return `tuple[float, float]`.
   - `Index.interleave/deinterleave` are now generic (`Sequence[T] -> list[T]`).
   - `intersection_v` / `nearest_v` / `leaves()` now have real return types.

3. **What is still loose:** coordinates are `Sequence[float]` (NumPy arrays
   are accepted at runtime); stored objects are `Any`; the `_v` numpy
   parameters are untyped `ndarray` (could use `py::array_t<T>` — but that
   silently copies on dtype mismatch, which would break the output arrays).

## Bugs found along the way (both exist on `main`)

- **`result_limit` and `result_offset` are cross-wired.** `set_result_limit`
  called `Index_SetResultSetOffset` and vice versa; the getters were swapped
  too, so the round-trip tests passed. On `main`, `idx.result_offset = 3`
  limits results to 3. Fixed; `test_result_limit_and_offset_semantics` added.
- **`CustomStorageBase` is unusable.** `registerCallbacks` passes
  `ctypes.c_void_p()` as the context, which `CustomStorageCallbacks` wraps in a
  second `c_void_p(...)` → `TypeError: cannot be converted to pointer`. There
  was no test. Fixed; `IndexCustomStorageBase` test added.
- C API issues found while binding it (moot now that the C API isn't used,
  but worth fixing upstream for other C API users):
  - `Error_Reset` / `Error_GetErrorCount` are exported by libspatialindex_c
    but **not declared in `sidx_api.h`**; ctypes never noticed.
  - `Index_Free(NULL)` pushes an error onto the error stack, so freeing an
    empty result can poison the next error check.
  - `Index_Intersects_obj` returns `RT_None` even after catching an exception
    and pushing an error.
  - The `IndexProperty_Set*` string setters `strdup` without freeing the
    previous value.

## Design of the prototype

- **Bind the C++ API.** `IndexHandle` owns the same three objects
  `libspatialindex_c`'s `Index` class did — storage manager →
  `RandomEvictionsBuffer` → `RTree`/`MVRTree`/`TPRTree` — built from a
  `Tools::PropertySet` with the same defaults as the C API's `GetDefaults()`.
  Everything the C shim provided is reimplemented in ~200 lines: id / object /
  count visitors, bounds and leaf query strategies, point-vs-region insert
  detection, result paging, stream and array bulk loaders, and storage
  managers for Python and ctypes custom storage.
- **Results are collected once.** Visitors write ids straight into a
  `std::vector`, and `*_obj` queries extract id, bounds and payload into an
  owned record while visiting. The C API cloned every `IData` twice (visitor,
  then pager), `malloc`ed a C array, and copied payload bytes twice more.
- **Paging inside the visitor.** `result_limit`/`result_offset` are applied as
  hits arrive; skipped hits are never materialised (the C API collected and
  cloned all of them, then sliced).
- **Errors are exceptions.** `Tools::Exception` / `std::exception` from
  libspatialindex are translated to `RTreeError` once. No global error stack
  to poll after each call (which was not thread-local on MSVC), and none of the
  C API's swallowed errors (`Index_Intersects_obj` returned `RT_None` after
  pushing an error).
- **Feature detection moved to build time.** `CMakeLists.txt` probes the C++
  headers (`nearestNeighborQuery` with `max_dist` and `ISpatialIndex::flush`,
  both ≥ 1.9). `contains()` now works with 1.8.5 too, since
  `containsWhatQuery` was always in the C++ API — only the C API lacked it.
- **Memory ownership in C++.** `IndexItem` owns its record and is freed when
  garbage-collected, so iterators no longer need `finally:` cleanup.
  Page buffers handed to libspatialindex are allocated with `new[]`, as it
  `delete[]`s them.
- **Lifetimes.** `IndexHandle` keeps its `PropertyHandle` alive
  (`py::keep_alive`), owns copies of the property strings, and tears down
  tree → buffer → storage in that order, so a custom storage object can never
  be called after it's freed.
- **Custom storage.** `CustomStorage` is a C++ `IStorageManager` that calls
  the Python methods with `int`/`bytes` and an `ErrorRef` (supports both
  `err.value = X` and the old `err.contents.value = X`). `CustomStorageBase`
  (raw ctypes buffers) still works: its ctypes callback table is copied into a
  second `IStorageManager`, and `allocateBuffer` uses `_core.new_buffer`.
- **GIL** is released around index calls and re-acquired in callbacks. Bulk
  loading from a Python iterator keeps it. The module is **not** declared
  free-threading safe: libspatialindex is not internally locked.

## C API vs C++ API binding

Same machine, same static libspatialindex 2.1.0, same `index.py`; 100k random
boxes, 20k 10×10 query windows; best of 5 repetitions, best of two runs each.
Script: `benchmarks/bindings.py`.

| operation | C API binding | C++ API binding | speed-up |
|---|---:|---:|---:|
| insert 100k | 3278 ms | 3283 ms | 1.00× |
| insert w/ obj 20k | 737 ms | 724 ms | 1.02× |
| stream bulk load 100k | 111 ms | 110 ms | 1.01× |
| array bulk load 100k | 54 ms | 55 ms | 0.98× |
| intersection → ids, 20k q | 221 ms | 226 ms | 0.98× |
| count, 20k q | 206 ms | 207 ms | 0.99× |
| contains → ids, 20k q | 5121 ms | 5116 ms | 1.00× |
| intersection → `Item`s, 20k q | 562 ms | 513 ms | 1.10× |
| intersection → raw objects, 20k q | 328 ms | 328 ms | 1.00× |
| nearest k=5 → ids, 20k q | 527 ms | 518 ms | 1.02× |
| nearest k=5 → `Item`s, 20k q | 857 ms | 830 ms | 1.03× |
| `intersection_v`, 20k boxes | 175 ms | 169 ms | 1.04× |
| `nearest_v` k=5, 20k boxes | 467 ms | 454 ms | 1.03× |
| `leaves()` | 5.5 ms | 4.4 ms | 1.25× |
| `bounds` ×20k | 18.2 ms | 17.0 ms | 1.07× |
| delete 20k | 10266 ms | 10008 ms | 1.03× |
| **large results:** `Item`s, 100k hits ×5 | 1917 ms | 1625 ms | 1.18× |
| **large results:** raw objects, 100k hits ×5 | 825 ms | 716 ms | 1.15× |
| **paged:** `Item`s, `result_limit=10` of 100k hits ×100 | 2085 ms | 1033 ms | **2.02×** |
| **paged:** ids, `result_limit=10` of 100k hits ×100 | 1137 ms | 1044 ms | 1.09× |

Run-to-run noise is about ±3–7%, so anything under ~1.05× is a tie.

**Takeaway: dropping the C API makes no difference for typical per-query
workloads.** The gains are where the C shim did avoidable work per *result*:
object queries with many hits (1.1–1.2×, fewer `IData` clones and copies) and
paged queries (up to 2×, because the C API materialised and cloned every hit
before slicing). Everything else is bound by libspatialindex itself or by the
Python layer:

- `intersection_v` runs the whole 20k-query loop in C++ with no Python per
  query, and still takes 169 ms against 226 ms for the Python loop. So about
  75% of a single `intersection()` call (~8.5 µs of ~11 µs) is the tree query
  inside libspatialindex. The remaining ~2.5 µs is Python/pybind11 overhead
  (coordinate normalisation in `index.py`, argument conversion, list →
  iterator); the C shim's share was ~0.1 µs.
- Insert, delete and `contains` are dominated by libspatialindex's R*-tree
  maintenance and node (de)serialisation through the memory storage manager.
  Buffer size doesn't change this (`buffering_capacity=100000` gave the same
  query time); tree shape does (`leaf_capacity=index_capacity=16` made
  intersection ~25% faster in a quick probe).

Other reasons to prefer the C++ binding anyway:

- **One fewer library.** Only `libspatialindex` is needed; `libspatialindex_c`
  is not linked (the binary contains none of its code).
- **Fewer semantics hidden in a shim.** Paging, point detection, storage
  setup and error handling are now in rtree's own code, where they can be
  tested and fixed without a libspatialindex release.
- **Fixes C API gaps.** `contains()` on 1.8.5; errors no longer swallowed.

The cost:

- **C++ ABI coupling.** For shared-library builds (distros, conda), the
  extension must be built with a compiler/standard library ABI-compatible with
  the one that built libspatialindex. Irrelevant for the static wheels.
  Windows + a *shared* libspatialindex DLL is untested: its headers don't use
  `__declspec(dllimport)`, which matters for C++ classes.
- **Version drift in the C++ API** is handled with `#if` / CMake probes
  (two so far, both for 1.8.x).
- rtree now owns ~200 more lines of C++ that used to live upstream.

Bigger wins would come from the parts above that bindings don't touch: moving
coordinate normalisation and result iteration into C++ (the ~2.5 µs/query
Python share), or returning NumPy arrays for id queries.

## Packaging impact (the concern raised in #223)

The wheel-building machinery the issue worried about mostly exists already
(cibuildwheel builds libspatialindex from source on every platform). What
changes:

- **One wheel per CPython version.** The ctypes wheel was built once and
  retagged `py3-none-<plat>` by `scripts/repair_wheel.py`. A pybind11 module is
  ABI-specific: 5 CPython versions × ~7 platforms ≈ 35 wheels per release
  (plus sdist). pybind11 has no Limited-API/abi3 support; nanobind does, but
  only for Python ≥ 3.12, so 3.10/3.11 would still need their own wheels.
- **Static linking simplifies everything else.** `install_libspatialindex.*`
  now builds a static, PIC libspatialindex into `sidx-static/`, which CMake
  picks up. The extension has no runtime dependency on a separate
  `libspatialindex_c`, so `repair_wheel.py` (deleted), the `rtree/lib`
  bundling in `setup.py` (deleted), and the `finder` search logic are no longer
  needed for wheels. Standard auditwheel/delocate/delvewheel repair applies.
- **Build backend:** setuptools → scikit-build-core + CMake.
- **Source/distro builds** need a C++17 compiler and libspatialindex
  headers (`libspatialindex-dev`, conda `libspatialindex`) instead of just the
  runtime `.so`. Only the C++ library (`libspatialindex`) is linked, not
  `libspatialindex_c`. CMake finds it via its CMake config (≥ 1.9) or falls
  back to `find_path/find_library` (`SPATIALINDEX_ROOT`). Tested against 2.1.0
  (shared and static) and 1.8.5 (shared, no CMake config).
- macOS deployment target raised 10.9 → 10.13 (C++17 `std::optional`).
- **PyPy:** ctypes worked on PyPy for free. pybind11 supports PyPy via
  cpyext, but it's slower there; if PyPy matters, it needs its own wheels and
  testing.
- **Tests now need an editable install** when run from the source tree
  (`pip install -e .`), otherwise `rtree/` in the checkout shadows the
  installed extension. CI is updated accordingly.
- `rtree.finder` stays for third parties that dlopen libspatialindex
  themselves; its tests skip when no shared library exists (static wheels).
  `finder.get_include()` no longer finds headers in wheels because headers
  are no longer bundled — decide whether anyone still relies on that.

## Performance vs ctypes (C-API binding, libspatialindex 2.1.0, 100k boxes, 20k queries)

The C++ binding is within noise of these numbers except where the table above
says otherwise.

| operation | ctypes | pybind11 | speed-up |
|---|---:|---:|---:|
| insert 100k | 3398 ms | 3234 ms | 1.05× (dominated by libspatialindex) |
| intersection → ids | 342 ms | 229 ms | 1.5× |
| count | 240 ms | 249 ms | ~1× |
| intersection → `Item` objects | 3500 ms | 633 ms | **5.5×** |
| intersection → raw objects | 666 ms | 338 ms | 2.0× |
| nearest k=5 | 666 ms | 507 ms | 1.3× |
| stream bulk load 100k | 221 ms | 118 ms | 1.9× |

(`benchmarks`-style script, single run each; indicative only.)

## Compatibility notes for users

- `rtree.core.rt` (the raw `CDLL`) is gone. `rtree.core` now re-exports the
  typed `_core` objects. Anyone calling `core.rt.Index_*` directly breaks.
- Passing a non-integer id raises `TypeError` instead of `ctypes.ArgumentError`.
- Wrong-length coordinate sequences raise `ValueError` (as before, via ctypes).
- `result_limit` / `result_offset` now do what their names say (behaviour
  change for anyone who worked around the swap).
- `Property.filename` & extensions accept `str` or `bytes`; getters return `str`.
- `Property.custom_storage_callbacks` returns an `int` address (or `None`).

## Suggested next steps

1. Run the updated CI on GitHub (the cibuildwheel matrix changes are untested
   here — especially Windows static linking and the macOS universal static lib).
2. Decide on the release policy: accept ~35 wheels, or evaluate nanobind for
   abi3 on 3.12+ (the binding code would port with modest changes).
3. Add `mypy.stubtest rtree._core` to CI with an allowlist for pybind11
   metaclass noise, so the committed `.pyi` can't drift from the extension.
4. Upstream: the C API fixes listed under "Bugs found".
5. If per-query speed matters: move coordinate normalisation into C++ and/or
   return NumPy arrays from id queries; that's where the remaining binding-side
   time is.
6. Un-skip the `contains` tests for libspatialindex < 2.1 (they are gated on
   the version via `skip_sidx_lt_210`, but the C++ binding supports them).
7. Note: `tox.ini` has `ignore_outcome = True`, so wheel-test failures in
   cibuildwheel never fail CI today.

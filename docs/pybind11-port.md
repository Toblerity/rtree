# Porting rtree from ctypes to pybind11 — investigation notes

Branch: `pybind11` · Tracking issue: [#223](https://github.com/Toblerity/rtree/issues/223)

## TL;DR

A working prototype is on this branch. `rtree/core.py`'s ~700 lines of
hand-written ctypes prototypes are replaced by a ~1,000-line pybind11 module
(`src/_core.cpp`) that binds the libspatialindex **C API** one-to-one, but with
Python types (`list[float]`, `bytes`, `numpy.ndarray`) instead of pointers.
`rtree/index.py` keeps its public API and now calls the typed handles.

| | ctypes (`main`) | pybind11 (this branch) |
|---|---|---|
| Test suite (sidx 2.1.0) | 57 pass | 58 pass (+2 new regression tests, 0 changed expectations except `ctypes.ArgumentError` → `TypeError`) |
| Test suite (sidx 1.8.5) | — | 52 pass, 6 skipped (Contains / array APIs absent, as before) |
| `mypy --strict rtree` | 270 errors (172 index.py, 101 core.py) | 0 in index.py/core.py (2 pre-existing in finder.py) |
| Type info for the binding layer | none (`CDLL` attributes are `Any`) | generated `rtree/_core.pyi` |
| Wheel contents | py3-none wheel + bundled `libspatialindex*.so/.dylib/.dll` + finder/repair scripts | one self-contained extension per CPython version, libspatialindex linked statically (583 KB on linux x86_64) |

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
- `Error_Reset` / `Error_GetErrorCount` are exported by libspatialindex_c but
  **not declared in `sidx_api.h`**; ctypes never noticed. The extension declares
  them itself — worth adding to the header upstream.
- (Observation) `Index_Free(NULL)` pushes an error onto the error stack, so
  freeing an empty result can poison the next error check. The binding avoids
  calling it on NULL.

## Design of the prototype

- **Bind the C API, not the C++ API.** Lowest risk: same entry points, same
  error semantics, same 1.8.5 → 2.x compatibility story, and index.py's
  logic is untouched. Binding `SpatialIndex::ISpatialIndex` directly (visitors
  instead of result arrays) would be faster still, but is a rewrite.
- **Feature detection moved to build time.** `CMakeLists.txt` uses
  `check_cxx_symbol_exists` for `Index_Contains_id` and `Index_CreateWithArray`
  and exposes `_core.HAS_CONTAINS` / `_core.HAS_ARRAY_API`, replacing
  `try: rt.Foo except AttributeError`. The < 1.9 `size_t*`/`uint32_t*`
  stream-callback mismatch (#220) is handled with `SIDX_VERSION_NUM`.
- **Memory ownership in C++.** Result arrays are copied into Python lists and
  freed immediately with `Index_Free`; `IndexItem` owns its handle and is
  destroyed when garbage-collected, so iterators no longer need `finally:`
  cleanup. Everything is freed with the library's own `Index_Free`/
  `SIDX_NewBuffer`, which matters for mismatched CRTs on Windows.
- **Lifetimes.** `IndexHandle` keeps its `PropertyHandle` alive
  (`py::keep_alive`), and the property handle owns the custom-storage bridge,
  so index teardown can never call into a freed callback (a latent ordering
  hazard with the ctypes version).
- **Custom storage.** `CustomStorage` now goes through a compiled bridge that
  calls the Python methods with `int`/`bytes` and an `ErrorRef`. `ErrorRef`
  supports both `err.value = X` and the old `err.contents.value = X`, so
  existing subclasses keep working. `CustomStorageBase` (raw ctypes buffers)
  is kept on ctypes deliberately; `allocateBuffer` now uses
  `_core.new_buffer` instead of dlopen-ing the library.
- **GIL** is released around index calls (as ctypes did implicitly) and
  re-acquired in callbacks. The module is **not** declared free-threading safe
  yet: libspatialindex is not internally locked and its MSVC build uses a
  global error stack.

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
  runtime `.so`. CMake finds libspatialindex via its CMake config (≥ 1.9) or
  falls back to `find_path/find_library` (`SPATIALINDEX_ROOT`). Tested against
  2.1.0 (shared and static) and 1.8.5 (shared, no CMake config).
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

## Performance (same machine, libspatialindex 2.1.0, 100k boxes, 20k queries)

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
4. Upstream: declare `Error_Reset`/`Error_GetErrorCount` in `sidx_api.h`; make
   `Index_Free(NULL)` a no-op.
5. Consider a follow-up that binds the C++ API directly (visitor-based
   queries writing straight into Python lists / NumPy arrays).
6. Note: `tox.ini` has `ignore_outcome = True`, so wheel-test failures in
   cibuildwheel never fail CI today.

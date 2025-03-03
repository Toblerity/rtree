#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    if sys.platform.startswith("linux"):
        os_ = "linux"
    elif sys.platform.startswith("darwin"):
        os_ = "macos"
    elif sys.platform.startswith("win32"):
        os_ = "windows"
    else:
        raise NotImplementedError(
            f"sys.platform '{sys.platform}' is not supported yet."
        )

    p = argparse.ArgumentParser(
        description="Convert wheel to be independent of python implementation and ABI"
    )
    p.set_defaults(prog=Path(sys.argv[0]).name)
    p.add_argument("WHEEL_FILE", help="Path to wheel file.")
    p.add_argument(
        "-w",
        "--wheel-dir",
        dest="WHEEL_DIR",
        help=('Directory to store delocated wheels (default: "wheelhouse/")'),
        default="wheelhouse/",
    )

    args = p.parse_args()

    file = Path(args.WHEEL_FILE).resolve(strict=True)
    wheelhouse = Path(args.WHEEL_DIR).resolve()
    wheelhouse.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir_:
        tmpdir = Path(tmpdir_)
        # use the platform specific repair tool first
        if os_ == "linux":
            # use path from cibuildwheel which allows auditwheel to create
            # rtree.libs/libspatialindex-*.so.*
            cibw_lib_path = "/project/rtree/lib"
            if os.environ.get("LD_LIBRARY_PATH"):  # append path
                os.environ["LD_LIBRARY_PATH"] += f"{os.pathsep}{cibw_lib_path}"
            else:
                os.environ["LD_LIBRARY_PATH"] = cibw_lib_path
            subprocess.run(
                ["auditwheel", "repair", "-w", str(tmpdir), str(file)], check=True
            )
        elif os_ == "macos":
            subprocess.run(
                [
                    "delocate-wheel",
                    # "--require-archs",
                    # "arm64,x86_64",
                    "-w",
                    str(tmpdir),
                    str(file),
                ],
                check=True,
            )
        elif os_ == "windows":
            # no specific tool, just copy
            shutil.copyfile(file, tmpdir / file.name)
        (file,) = tmpdir.glob("*.whl")

        # make this a py3 wheel
        subprocess.run(
            [
                "wheel",
                "tags",
                "--python-tag",
                "py3",
                "--abi-tag",
                "none",
                "--remove",
                str(file),
            ],
            check=True,
        )
        (file,) = tmpdir.glob("*.whl")
        # unpack
        subprocess.run(["wheel", "unpack", file.name], cwd=tmpdir, check=True)
        for unpackdir in tmpdir.iterdir():
            if unpackdir.is_dir():
                break
        else:
            raise RuntimeError("subdirectory not found")

        if os_ == "linux":
            # This is auditwheel's libs, which needs post-processing
            libs_dir = unpackdir / "rtree.libs"
            lsidx_list = list(libs_dir.glob("libspatialindex*.so*"))
            assert len(lsidx_list) == 1, list(libs_dir.iterdir())
            lsidx = lsidx_list[0]
            subprocess.run(["patchelf", "--set-rpath", "$ORIGIN", lsidx], check=True)
            # remove duplicated dir
            lib_dir = unpackdir / "rtree" / "lib"
            shutil.rmtree(lib_dir)
        # re-pack
        subprocess.run(["wheel", "pack", str(unpackdir.name)], cwd=tmpdir, check=True)
        files = list(tmpdir.glob("*.whl"))
        assert len(files) == 1, files
        file = files[0]
        file.rename(wheelhouse / file.name)


if __name__ == "__main__":
    main()

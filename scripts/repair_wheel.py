#!/usr/bin/env python3

import argparse
import re
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
            "sys.platform '{}' is not supported yet.".format(sys.platform)
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
            subprocess.run(
                ["auditwheel", "repair", "-w", str(tmpdir), str(file)], check=True
            )
        elif os_ == "macos":
            subprocess.run(
                [
                    "delocate-wheel",
                    "--require-archs",
                    "arm64,x86_64",
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

        # we need to handle macOS universal2 & arm64 here for now,
        # let's use platform_tag_args for this.
        platform_tag_args = []
        if os_ == "macos":
            additional_platforms = []

            # first, get the target macOS deployment target from the wheel
            match = re.match(r"^.*-macosx_(\d+)_(\d+)_x86_64\.whl$", file.name)
            assert match is not None
            target = tuple(map(int, match.groups()))

            # let's add universal2 platform for this wheel.
            additional_platforms = ["macosx_{}_{}_universal2".format(*target)]

            # given pip support for universal2 was added after arm64 introduction
            # let's also add arm64 platform.
            arm64_target = target
            if arm64_target < (11, 0):
                arm64_target = (11, 0)
            additional_platforms.append("macosx_{}_{}_arm64".format(*arm64_target))

            if target < (11, 0):
                # They're were also issues with pip not picking up some
                # universal2 wheels, tag twice
                additional_platforms.append("macosx_11_0_universal2")

            platform_tag_args = [f"--platform-tag=+{'.'.join(additional_platforms)}"]

        # make this a py3 wheel
        subprocess.run(
            [
                "wheel",
                "tags",
                "--python-tag",
                "py3",
                "--abi-tag",
                "none",
                *platform_tag_args,
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
            # remove duplicated dir
            assert len(list((unpackdir / "Rtree.libs").glob("*.so*"))) >= 1
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

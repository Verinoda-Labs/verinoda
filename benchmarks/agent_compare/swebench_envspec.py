"""Read a SWE-bench 5.x instance Dockerfile into what a Windows venv needs: the Python version, the Python packages
(conda's and pip's) and the commands run in /testbed after the clone."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

# conda packages that are the platform, not Python libraries
SYSTEM = {
    "_libgcc_mutex", "_openmp_mutex", "ca-certificates", "ld_impl_linux-64", "libffi", "libgcc-ng", "libgomp",
    "libstdcxx-ng", "ncurses", "openssl", "readline", "sqlite", "tk", "xz", "zlib", "tzdata", "pip", "setuptools",
    "wheel", "python", "libuuid", "bzip2", "libedit", "libxcb", "expat", "libgfortran-ng", "libgfortran5", "intel-openmp",
    "mkl", "mkl-service", "mkl_fft", "mkl_random", "blas", "libblas", "libcblas", "liblapack", "libopenblas", "openblas",
    "libstdcxx", "libgcc", "libzlib", "libnsl", "libsqlite", "libxcrypt", "libexpat", "libmpdec", "pthread-stubs",
    "lerc", "libdeflate", "libpng", "libtiff", "libwebp", "libwebp-base", "jpeg", "freetype", "fontconfig", "lcms2",
    "libjpeg-turbo", "openjpeg", "zstd", "lz4-c", "glib", "dbus", "gst-plugins-base", "gstreamer", "icu", "krb5",
    "libclang", "libevent", "libllvm", "libpq", "libxkbcommon", "libxml2", "libxslt", "nspr", "nss", "qt-main", "xcb-util",
    "cyrus-sasl", "libcurl", "libssh2", "c-ares", "libev", "libnghttp2", "mpfr", "gmp", "mpc", "libbrotlicommon",
    "libbrotlidec", "libbrotlienc", "brotli-bin", "giflib", "libiconv", "gettext", "pcre", "pcre2", "graphite2",
    "harfbuzz", "libgd", "cairo", "pixman", "fribidi", "libuv", "yaml", "libyaml", "libsodium", "zeromq", "libgfortran",
    "tbb", "libabseil", "libprotobuf", "re2", "orc", "snappy", "aws-c-common", "libthrift", "libutf8proc",
}
CONDA_TO_PIP = {"pytables": "tables", "pyqt": None, "matplotlib-base": "matplotlib", "py-cpuinfo": "py-cpuinfo",
                "msgpack-python": "msgpack", "brotli": None, "brotli-python": None, "python_abi": None,
                "pyyaml": "pyyaml", "pytorch": None, "ipython_genutils": "ipython-genutils", "typing_extensions":
                "typing-extensions", "importlib_metadata": "importlib-metadata", "backports.zoneinfo": None,
                "libblas": None, "numpy-base": None, "pywin32": None, "sip": None, "qt": None, "pyqt5-sip": None}


def parse(dockerfile: Path) -> dict:
    text = dockerfile.read_text(encoding="utf-8")
    env = re.search(r"cat <<'(EOF_\w+)' > /root/environment\.yml\n(.*?)\n\1", text, re.DOTALL)
    python, conda, pip, tools = None, [], [], []
    if env:
        section = None
        for line in env.group(2).splitlines():
            s = line.strip()
            if s.startswith("dependencies:"):
                section = "conda"
                continue
            if s == "- pip:":
                section = "pip"
                continue
            if not s.startswith("- "):
                if s.startswith("prefix:"):
                    break
                continue
            item = s[2:].strip()
            if section == "pip" and line.startswith("      "):
                pip.append(item)
            elif section in ("conda", "pip"):
                section = "conda"
                name, *rest = item.split("=")
                version = rest[0] if rest else ""
                if name in ("setuptools", "wheel") and version:
                    tools.append(f"{name}=={version}")  # kept out of the key: older envs got them after they were built
                elif name == "python":
                    python = version
                elif name not in SYSTEM:
                    mapped = CONDA_TO_PIP.get(name, name)
                    if mapped:
                        conda.append(f"{mapped}=={version}" if version else mapped)
    # the commands of the last RUN block, after the clone: the project's own install steps
    runs = re.findall(r"RUN <<(EOF_\w+)\n(.*?)\n\1", text, re.DOTALL)
    install = []
    for _, body in runs:
        if "/testbed" in body and "git clone" in body:
            after = body.split("conda activate testbed", 1)[-1]
            for line in after.splitlines():
                s = line.strip()
                if s and not s.startswith(("#", "echo ", "cd ", "git config", "git commit", "source ")):
                    install.append(s)
    pre = re.findall(r"^RUN (?!<<)(.*)$", text, re.MULTILINE)
    return {"python": python, "packages": sorted(set(conda + pip)), "build_tools": tools, "install": install, "run_lines": pre}


def env_key(spec: dict) -> str:
    return hashlib.sha256(json.dumps([spec["python"], spec["packages"]]).encode()).hexdigest()[:12]

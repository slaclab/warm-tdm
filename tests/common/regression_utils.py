from __future__ import annotations

from fnmatch import fnmatch
from functools import lru_cache
import os
from pathlib import Path
import shlex
import subprocess

from cocotb_test.simulator import run


REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_ROOT = REPO_ROOT / "tests"
DEFAULT_IMPORT_ROOT = REPO_ROOT / "build" / "SRC_VHDL"
UNISIM_VCOMPONENTS_STUB = TESTS_ROOT / "common" / "vhdl" / "unisim_vcomponents.vhd"

BASE_GHDL_COMPILE_ARGS = [
    "--std=08",
    "-fsynopsys",
    "-frelaxed-rules",
    "-fexplicit",
]

OPTIONAL_GHDL_WARNINGS = ("elaboration", "hide", "specs")


@lru_cache(maxsize=1)
def _supported_ghdl_warning_names() -> frozenset[str]:
    try:
        result = subprocess.run(
            [*shlex.split(os.environ.get("GHDL_CMD", "ghdl")), "--help-warnings"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return frozenset()

    names = set()
    for line in result.stdout.splitlines():
        token = line.strip().split(maxsplit=1)[0]
        if not token.startswith("-W") or token == "-Wall":
            continue
        names.add(token.removeprefix("-W").removesuffix("*"))
    return frozenset(names)


def _optional_ghdl_warning_flags() -> list[str]:
    supported_names = _supported_ghdl_warning_names()
    return [f"-Wno-{name}" for name in OPTIONAL_GHDL_WARNINGS if name in supported_names]


COMMON_VHDL_COMPILE_ARGS = [
    *BASE_GHDL_COMPILE_ARGS,
    *_optional_ghdl_warning_flags(),
    "-O2",
]


def start_lockstep_clocks(*signals, period_ns: float) -> None:
    import cocotb
    from cocotb.triggers import Timer

    async def drive() -> None:
        half_period_ns = period_ns / 2
        for signal in signals:
            signal.value = 0

        while True:
            await Timer(half_period_ns, unit="ns")
            for signal in signals:
                signal.value = 1
            await Timer(half_period_ns, unit="ns")
            for signal in signals:
                signal.value = 0

    cocotb.start_soon(drive())


def env_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw is None else int(raw.strip().strip("'").strip('"'))


def _ordered_library_names(library_names: set[str]) -> list[str]:
    preferred_order = ("unisim", "surf", "warm_tdm")
    ordered = [name for name in preferred_order if name in library_names]
    ordered.extend(sorted(name for name in library_names if name not in preferred_order))
    return ordered


def build_vhdl_sources(
    import_root: str | Path | None = None,
    *,
    library_allowlist: set[str] | None = None,
    file_allowlists: dict[str, set[str]] | None = None,
    file_excludes: tuple[str, ...] = (),
) -> dict[str, list[str]]:
    if import_root is None:
        import_path = DEFAULT_IMPORT_ROOT
    else:
        import_path = Path(import_root)

    if not import_path.exists():
        raise FileNotFoundError(
            "Missing imported HDL sources at "
            f"{import_path}. Run `make rtl_import` or set WARM_TDM_IMPORT_ROOT."
        )

    libraries: dict[str, list[str]] = {}
    for library_dir in sorted(import_path.iterdir()):
        if not library_dir.is_dir():
            continue
        library_name = library_dir.name
        if library_allowlist is not None and library_name not in library_allowlist:
            continue

        allowed_files = None if file_allowlists is None else file_allowlists.get(library_name)
        library_sources = []
        for path in sorted(library_dir.iterdir()):
            if not path.is_file():
                continue
            if allowed_files is not None and path.name not in allowed_files:
                continue
            if any(fnmatch(path.name, pattern) for pattern in file_excludes):
                continue
            library_sources.append(str(path))

        if library_sources:
            libraries[library_name] = library_sources

    if not libraries:
        raise FileNotFoundError(f"No imported VHDL libraries found under {import_path}")

    return libraries


def merge_vhdl_sources(
    base_sources: dict[str, list[str]],
    extra_sources: dict[str, list[str]] | None,
) -> dict[str, list[str]]:
    if not extra_sources:
        return base_sources

    merged: dict[str, list[str]] = {}
    all_library_names = set(base_sources) | set(extra_sources)
    for library in _ordered_library_names(all_library_names):
        merged[library] = []
        if library in extra_sources:
            merged[library].extend(str(Path(path)) for path in extra_sources[library])
        if library in base_sources:
            merged[library].extend(base_sources[library])
    return merged


def cocotb_module_name_from_test_file(test_file: str | Path) -> str:
    return ".".join(
        Path(test_file).resolve().relative_to(REPO_ROOT).with_suffix("").parts
    )


def _sim_build_path(test_file: Path, parameters: dict[str, object] | None) -> str:
    rel_parent = test_file.resolve().relative_to(TESTS_ROOT).parent
    build_dir = TESTS_ROOT / "sim_build" / rel_parent / test_file.stem
    if not parameters:
        return str(build_dir)

    suffix = ",".join(f"{key}={value}" for key, value in parameters.items())
    return str(build_dir.with_name(f"{test_file.stem}.{suffix}"))


def _sim_build_from_key(test_file: Path, sim_build_key: str) -> str:
    sim_build_path = Path(sim_build_key)
    if sim_build_path.is_absolute():
        return str(sim_build_path)

    rel_parent = test_file.resolve().relative_to(TESTS_ROOT).parent
    return str(TESTS_ROOT / "sim_build" / rel_parent / sim_build_path)


def run_warm_tdm_vhdl_test(
    *,
    test_file: str | Path,
    toplevel: str,
    parameters: dict[str, object] | None = None,
    extra_env: dict[str, object] | None = None,
    extra_vhdl_sources: dict[str, list[str]] | None = None,
    sim_build_key: str | None = None,
    import_root: str | Path | None = None,
    import_library_allowlist: set[str] | None = None,
    import_file_allowlists: dict[str, set[str]] | None = None,
    import_file_excludes: tuple[str, ...] = (),
) -> None:
    test_file = Path(test_file)
    simulator_env = None
    sim_build_parameters = parameters
    if extra_env is not None:
        simulator_env = {key: str(value) for key, value in extra_env.items()}
        if sim_build_parameters is None:
            sim_build_parameters = simulator_env
    elif parameters is not None:
        simulator_env = {key: str(value) for key, value in parameters.items()}

    imported_sources = build_vhdl_sources(
        os.environ.get("WARM_TDM_IMPORT_ROOT", import_root),
        library_allowlist=import_library_allowlist,
        file_allowlists=import_file_allowlists,
        file_excludes=import_file_excludes,
    )

    run(
        toplevel=toplevel,
        module=cocotb_module_name_from_test_file(test_file),
        toplevel_lang="vhdl",
        vhdl_sources=merge_vhdl_sources(imported_sources, extra_vhdl_sources),
        parameters=parameters,
        sim_build=_sim_build_from_key(test_file, sim_build_key)
        if sim_build_key is not None
        else _sim_build_path(test_file, sim_build_parameters),
        extra_env=simulator_env,
        simulator="ghdl",
        vhdl_compile_args=COMMON_VHDL_COMPILE_ARGS,
    )

#!/usr/bin/xcrun python3
"""
Launch Keynote (or technically Pages, or any other iWork app), set a
breakpoint at the first reasonable method after everything is loaded,
then dump the contents of `TSPRegistry sharedRegistry` to a JSON file.

Nastiest hack. Please don't use this.
Copyright 2020 Peter Sobot (psobot.com).
"""

from __future__ import annotations

import argparse
import enum
import json
import logging
import os
import subprocess
import sys
import time


class StateType(enum.Enum):
    Invalid = 0
    Unloaded = 1
    Connected = 2
    Attaching = 3
    Launching = 4
    Stopped = 5
    Running = 6
    Stepping = 7
    Crashed = 8
    Detached = 9
    Exited = 10
    Suspended = 11


class StopReason(enum.Enum):
    Invalid = 0
    _None = 1
    Trace = 2
    Breakpoint = 3
    Watchpoint = 4
    Signal = 5
    Exception = 6
    Exec = 7
    PlanComplete = 8
    ThreadExiting = 9
    Instrumentation = 10
    ProcessorTrace = 11
    Fork = 12
    VFork = 13
    VForkDone = 14
    Interrupt = 15


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", type=str, help="Path to the executable to debug.")
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to the output file to write to. Will be overwritten.",
    )
    args = parser.parse_args()

    if os.path.exists(args.output):
        logging.info(f"Removing output file {args.output}...")
        os.remove(args.output)

    mapping = extract_mapping(args.exe)
    with open(args.output, "w") as f:
        json.dump(mapping, f, indent=2)


def _add_lldb_to_path():
    """Make `import lldb` work, or explain why it can't.

    There is no lldb package on PyPI: the bindings ship with a toolchain and
    only load into the Python they were built against. That is either Xcode's
    (or the Command Line Tools') lldb with /usr/bin/python3, or Homebrew's llvm
    with the Homebrew Python of the same minor version.
    """
    try:
        import lldb  # noqa: F401

        return
    except ImportError:
        pass

    candidates = []
    try:
        # `lldb -P` prints the directory holding that lldb's Python bindings.
        candidates.append(
            subprocess.check_output(
                ["lldb", "-P"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        pass
    LLVM_PYTHON_ROOT = "/opt/homebrew/opt/llvm/libexec"
    candidates.append(
        f"{LLVM_PYTHON_ROOT}/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )

    errors = []
    for candidate in candidates:
        if not candidate or not os.path.isdir(candidate):
            continue
        sys.path.append(candidate)
        try:
            import lldb  # noqa: F401

            logging.info(f"Using LLDB Python bindings from {candidate}.")
            return
        except ImportError as e:
            errors.append(f"{candidate}: {e}")
            sys.path.remove(candidate)

    raise ImportError(
        "Could not import LLDB's Python bindings into Python "
        f"{sys.version_info.major}.{sys.version_info.minor} ({sys.executable}). "
        "The bindings must match the interpreter: use Xcode's lldb with "
        "/usr/bin/python3, or Homebrew's llvm with the matching Homebrew Python. "
        + ("Tried: " + "; ".join(errors) if errors else "No bindings were found.")
    )


def extract_mapping(exe: str) -> dict[int, str]:
    _add_lldb_to_path()

    import lldb

    logging.info("Creating debugger...")
    debugger = lldb.SBDebugger.Create()
    debugger.SetAsync(False)
    logging.info(f"Creating target of {exe}...")
    target = debugger.CreateTargetWithFileAndArch(exe, None)
    logging.info("Setting breakpoint for _sendFinishLaunchingNotification...")
    target.BreakpointCreateByName("_sendFinishLaunchingNotification")

    logging.info("Setting breakpoint for _handleAEOpenEvent:...")
    target.BreakpointCreateByName("_handleAEOpenEvent:")

    logging.info("Setting breakpoint for [CKContainer containerWithIdentifier:]...")
    # let's break in the CloudKit code and early exit the function before it can raise an exception:
    target.BreakpointCreateByName("[CKContainer containerWithIdentifier:]")

    logging.info("Setting breakpoint for ___lldb_unnamed_symbol[0-9]+...")
    # In later Keynote versions, 'containerWithIdentifier' isn't called directly, but we can break on similar methods:
    # Note: this __lldb_unnamed_symbol hack was determined by painstaking experimentation. It will break again for sure.
    target.BreakpointCreateByRegex("___lldb_unnamed_symbol[0-9]+", "CloudKit")

    logging.info("Launching process...")
    process = target.LaunchSimple(None, None, os.getcwd())

    if not process:
        raise ValueError(f"Failed to launch process: {exe}")
    try:
        logging.info("Waiting for process to stop on a breakpoint...")
        while (
            process.GetState() != lldb.eStateStopped
            and process.GetState() != lldb.eStateExited
        ):
            logging.info(f"Current state: {StateType(process.GetState())}")
            time.sleep(0.1)

        if process.GetState() == lldb.eStateExited:
            raise ValueError(
                "Process exited before stopping on a breakpoint. "
                "Ensure the process is properly code signed."
            )

        while process.GetState() == lldb.eStateStopped:
            thread = process.GetThreadAtIndex(0)
            logging.info(
                f"Thread: {thread} stopped at: {StopReason(thread.GetStopReason())}"
            )
            # if/elif rather than match: the Xcode bindings only load into
            # /usr/bin/python3, which is Python 3.9.
            stop_reason = thread.GetStopReason()
            if stop_reason == lldb.eStopReasonBreakpoint:
                if any(
                    [
                        x in str(thread.GetSelectedFrame())
                        for x in ["CKContainer", "CloudKit"]
                    ]
                ):
                    # Skip the code in CKContainer, avoiding a crash due to missing entitlements:
                    thread.ReturnFromFrame(
                        thread.GetSelectedFrame(),
                        lldb.SBValue().CreateValueFromExpression("0", ""),
                    )
                    process.Continue()
                else:
                    break
            elif stop_reason == lldb.eStopReasonException:
                logging.info(repr(thread) + "\n")
                raise NotImplementedError(
                    f"LLDB caught exception, {__file__} needs to be updated to handle."
                )
            else:
                process.Continue()

        if process.GetState() != lldb.eStateStopped:
            raise ValueError("LLDB was unable to stop process! " + str(process))
        if not thread:
            raise ValueError("Could not get thread to print out registry!")
        frame = thread.GetFrameAtIndex(0)
        if not frame:
            raise ValueError("Could not get frame to print out registry!")
        registry = frame.EvaluateExpression("[TSPRegistry sharedRegistry]").description
        split = [
            x.strip().split(" -> ")
            for x in registry.split("{")[1].split("}")[0].split("\n")
            if x.strip()
        ]
        mapping = [(int(a), b.split(" ")[-1]) for a, b in split if "null" not in b]
        logging.info(f"Extracted mapping with {len(mapping):,} elements.")
        return dict(sorted(mapping))
    finally:
        process.Kill()


if __name__ == "__main__":
    main()

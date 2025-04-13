#!/usr/bin/xcrun python3
"""
Launch Keynote (or technically Pages, or any other iWork app), set a
breakpoint at the first reasonable method after everything is loaded,
then dump the contents of `TSPRegistry sharedRegistry` to a JSON file.

Nastiest hack. Please don't use this.
Copyright 2020 Peter Sobot (psobot.com).
"""

import argparse
import enum
import json
import logging
import os
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


def extract_mapping(exe: str) -> dict[int, str]:
    # Add the installed LLVM Python path to the Python path and error if the Python version does not match:
    # i.e.: /opt/homebrew/opt/llvm/libexec/python3.13/site-packages
    LLVM_PYTHON_ROOT = "/opt/homebrew/opt/llvm/libexec"
    if not os.path.exists(LLVM_PYTHON_ROOT):
        raise ImportError(
            f"{LLVM_PYTHON_ROOT} does not exist. Please install LLVM/LLDB first."
        )

    existing_versions = [
        x for x in os.listdir(LLVM_PYTHON_ROOT) if x.startswith("python")
    ]

    THIS_PYTHON_LLVM_PATH = f"{LLVM_PYTHON_ROOT}/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    if not os.path.exists(THIS_PYTHON_LLVM_PATH):
        raise ImportError(
            "Your system has LLVM/LLDB installed, but it is not the same version as the Python interpreter "
            f"you are using; found: {', '.join(existing_versions)}, but the current Python version is "
            f"{sys.version_info.major}.{sys.version_info.minor}. Please install the same "
            "version of LLVM/LLDB as your Python interpreter."
        )

    sys.path.append(THIS_PYTHON_LLVM_PATH)

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
            match thread.GetStopReason():
                case lldb.eStopReasonBreakpoint:
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
                case lldb.eStopReasonException:
                    logging.info(repr(thread) + "\n")
                    raise NotImplementedError(
                        f"LLDB caught exception, {__file__} needs to be updated to handle."
                    )
                case _:
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

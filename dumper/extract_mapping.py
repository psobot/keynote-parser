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
import os
import time

import lldb


class StateType(enum.Enum):
    Invalid = 0
    Unloaded = 1
    Connected = 2
    Attaching = 3
    Launching = 4
    Stopped = 5
    Running = 6
    Stepping = 7


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
        print(f"Removing output file {args.output}...")
        os.remove(args.output)

    print("Creating debugger...")
    debugger = lldb.SBDebugger.Create()
    debugger.SetAsync(False)
    print(f"Creating target of {args.exe}...")
    target = debugger.CreateTargetWithFileAndArch(args.exe, None)
    print("Setting breakpoint for _sendFinishLaunchingNotification...")
    target.BreakpointCreateByName("_sendFinishLaunchingNotification")

    print("Setting breakpoint for _handleAEOpenEvent:...")
    target.BreakpointCreateByName("_handleAEOpenEvent:")

    print("Setting breakpoint for [CKContainer containerWithIdentifier:]...")
    # let's break in the CloudKit code and early exit the function before it can raise an exception:
    target.BreakpointCreateByName("[CKContainer containerWithIdentifier:]")

    print("Setting breakpoint for ___lldb_unnamed_symbol[0-9]+...")
    # In later Keynote versions, 'containerWithIdentifier' isn't called directly, but we can break on similar methods:
    # Note: this __lldb_unnamed_symbol hack was determined by painstaking experimentation. It will break again for sure.
    target.BreakpointCreateByRegex("___lldb_unnamed_symbol[0-9]+", "CloudKit")

    print("Launching process...")
    process = target.LaunchSimple(None, None, os.getcwd())

    if not process:
        raise ValueError("Failed to launch process: " + args.exe)
    try:
        print("Waiting for process to stop on a breakpoint...")
        while process.GetState() != lldb.eStateStopped:
            print(f"Current state: {StateType(process.GetState())}")
            time.sleep(0.1)

        while process.GetState() == lldb.eStateStopped:
            thread = process.GetThreadAtIndex(0)
            print(f"Thread: {thread} stopped at: {StopReason(thread.GetStopReason())}")
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
                    print(repr(thread) + "\n")
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
        print(f"Extracted mapping with {len(mapping):,} elements.")
        results = json.dumps(dict(sorted(mapping)), indent=2)
        with open(args.output, "w") as f:
            f.write(results)
        print(f"Wrote {len(results):,} bytes of mapping to {args.output}.")
    finally:
        process.Kill()


if __name__ == "__main__":
    main()

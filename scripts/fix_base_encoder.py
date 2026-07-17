#!/usr/bin/env python3
# ============================================================================
#  fix_base_encoder.py
#  One-key-center the SO-101 base joint (shoulder_pan) on a Feetech STS3215.
# ============================================================================
#
#  PROVENANCE
#  ----------
#  Reconstructed, cleaned-up script written from the documented fix below --
#  NOT the exact original one-off used on the bench (that script was not
#  preserved on disk). The imports were checked against LeRobot 0.6.0, but this
#  file has not itself been re-run on hardware.
#
#  THE BUG
#  -------
#  The Feetech STS3215 has a 12-bit absolute magnetic encoder: raw positions
#  run 0..4095, with the electrical midpoint at 2048. On this arm the *base*
#  joint (shoulder_pan, motor id 1) had its mechanical zero sitting right on
#  the 0 / 4096 wraparound seam.
#
#  On Feetech motors:   Present_Position = Actual_Position - Homing_Offset
#
#  With zero on the seam, calibration could only compensate by pushing
#  Homing_Offset to the rail. Homing_Offset is an 11-bit sign-magnitude field,
#  so its largest magnitude is 2047 -- and that is exactly where it pinned
#  (the leader's shoulder_pan in calibration/my_leader.json reads -2047).
#  With the offset stuck at the rail, the joint's forward target fell OUTSIDE
#  its usable swept range [range_min, range_max]. Under torque the follower
#  then chased that target across the 4095 -> 0 discontinuity and drove itself
#  into a hard stop.
#
#  THE FIX (no disassembly)
#  ------------------------
#  Physically hold the arm at forward-center, then issue the Feetech
#  "one-key middle" command: write 128 to the Torque_Enable register
#  (address 40) of the shoulder_pan motor. The servo latches its current raw
#  position as 2048 -- dead center, well off the seam -- and persists the new
#  home to EEPROM. Afterwards, re-run calibration so range_min / range_max /
#  homing_offset are recomputed around the fresh center:
#
#      lerobot-calibrate --robot.type=so101_follower \
#          --robot.port=COM4 --robot.id=my_follower
#
#  The call that did the work:
#      FeetechMotorsBus.write("Torque_Enable", "shoulder_pan", 128, normalize=False)
#
#  ---------------------------------------------------------------------------
#  !!  VERIFY THE IMPORT PATH BEFORE RUNNING  !!
#  ---------------------------------------------------------------------------
#  LeRobot has moved its motor classes across releases (e.g. the old
#  `lerobot.common.motors...` namespace was dropped). The imports below are
#  correct for the LeRobot version this repo was built against (0.6.0). If you
#  are on a different version and the import fails, find the current location
#  with, e.g.:
#      python -c "import lerobot.motors.feetech as m; print(m.__file__)"
#  and update the two imports accordingly.
#  ---------------------------------------------------------------------------
#
#  SAFETY
#  ------
#  * This script touches shoulder_pan ONLY. No other motor is in the bus map,
#    so no other joint can be addressed.
#  * It never enables motor torque; the arm stays limp. YOU hold it at center.
#  * Keep a hand on the arm and be ready to cut power.
# ============================================================================

import argparse
import sys
import time

try:
    # Verified correct for LeRobot 0.6.0 -- see the VERIFY note above.
    from lerobot.motors import Motor, MotorNormMode
    from lerobot.motors.feetech import FeetechMotorsBus
except ImportError as exc:  # depends on the installed LeRobot version
    sys.exit(
        "Could not import LeRobot's Feetech motor classes.\n"
        f"  ImportError: {exc}\n"
        "Activate the environment where lerobot is installed and VERIFY the\n"
        "import path for your version (the module has moved across releases):\n"
        '  python -c "import lerobot.motors.feetech as m; print(m.__file__)"'
    )

MOTOR_NAME = "shoulder_pan"   # the base joint -- the ONLY motor we touch
MOTOR_ID = 1                  # SO-101 base joint is id 1
MOTOR_MODEL = "sts3215"       # Feetech STS3215
ENCODER_MIDPOINT = 2048       # 12-bit encoder (0..4095) center
ONE_KEY_MIDDLE = 128          # value written to Torque_Enable to latch center


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="One-key-center the SO-101 base joint (shoulder_pan) on a Feetech STS3215.",
    )
    p.add_argument(
        "port",
        nargs="?",
        default="COM4",
        help="Serial port of the FOLLOWER arm bus (default: COM4).",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation (only if the arm is already at forward-center).",
    )
    return p.parse_args()


def confirm_centered(skip: bool) -> None:
    print()
    print("  Physically move the arm so the BASE joint is at forward-center")
    print("  (arm pointing straight ahead, mid-travel). The one-key-middle")
    print("  command latches the CURRENT position as 2048.")
    print()
    if skip:
        print("  --yes given: assuming the arm is centered.")
        return
    resp = input("  Type 'yes' to confirm the arm is at forward-center: ").strip().lower()
    if resp not in ("y", "yes"):
        sys.exit("Aborted -- center not confirmed. Nothing was written.")


def main() -> None:
    args = parse_args()

    # Build a bus that contains shoulder_pan and NOTHING else. Because it is the
    # only entry in the motors map, no other joint can be read or written here.
    bus = FeetechMotorsBus(
        port=args.port,
        motors={
            MOTOR_NAME: Motor(id=MOTOR_ID, model=MOTOR_MODEL, norm_mode=MotorNormMode.RANGE_M100_100),
        },
    )

    print(f"Connecting to {MOTOR_MODEL} '{MOTOR_NAME}' (id {MOTOR_ID}) on {args.port} ...")
    bus.connect()  # handshake pings shoulder_pan; fails loudly if it isn't there
    try:
        # Read raw encoder counts. normalize=False bypasses calibration and
        # returns the plain 0..4095 value (near the seam this reads ~0 or ~4095).
        before = bus.read("Present_Position", MOTOR_NAME, normalize=False)
        print(f"  Present_Position BEFORE: {before}  (target center = {ENCODER_MIDPOINT})")

        confirm_centered(args.yes)

        # THE FIX: one-key middle. Writing 128 to Torque_Enable tells the STS3215
        # to take its current shaft position as 2048 and persist it to EEPROM.
        print(f"  Writing {ONE_KEY_MIDDLE} -> Torque_Enable on '{MOTOR_NAME}' (one-key middle) ...")
        bus.write("Torque_Enable", MOTOR_NAME, ONE_KEY_MIDDLE, normalize=False)
        time.sleep(0.5)  # give the servo a moment to store the new home

        after = bus.read("Present_Position", MOTOR_NAME, normalize=False)
        print(f"  Present_Position AFTER:  {after}  (expected ~{ENCODER_MIDPOINT})")

        # Leave the joint limp / in a known-safe state (torque off). This does NOT
        # undo the centering above -- that is already saved in the motor's EEPROM.
        bus.write("Torque_Enable", MOTOR_NAME, 0, normalize=False)

        drift = abs(int(after) - ENCODER_MIDPOINT)
        if drift <= 64:
            print("  OK: base joint is now centered near 2048, off the wraparound seam.")
        else:
            print(f"  NOTE: AFTER is {drift} counts from center -- re-check that the arm")
            print("        was actually at forward-center, then run this script again.")

        print()
        print("  NEXT: recalibrate the follower so its range is rebuilt around center:")
        print(f"      lerobot-calibrate --robot.type=so101_follower \\")
        print(f"          --robot.port={args.port} --robot.id=my_follower")
    finally:
        bus.disconnect()  # disables torque and releases the serial port
        print("Disconnected.")


if __name__ == "__main__":
    main()

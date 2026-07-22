"""
camera_stress_test.py — isolate an intermittent UVC camera failure on Windows.

Mirrors LeRobot's OpenCVCamera.connect() sequence (DSHOW backend, set fps +
size, then FOURCC) but with NO robot, NO LeRobot, and NO second camera unless
you ask for one. The point is to change one variable at a time.

Why this exists: LeRobot reported
    failed to set fourcc=MJPG (actual=, success=False)
An EMPTY `actual` means CAP_PROP_FOURCC returned 0 -- the device handle opened
but no capture graph was established. This script reports that value explicitly
on every trial so you can see whether the failure is the device, contention with
the other camera, or something holding the device.

Usage (from the `lerobot` conda env, which already has opencv):

    # C920s alone, 10 consecutive open/read/release cycles
    python camera_stress_test.py --index 1 --trials 10

    # both cameras opened simultaneously, 10 cycles
    python camera_stress_test.py --index 1 --also 2 --trials 10

    # leave a camera open for 60s to check for mid-session drops
    python camera_stress_test.py --index 1 --soak 60
"""

import argparse
import time

import cv2


def decode_fourcc(value) -> str:
    """Unpack a FOURCC float/int into its 4-char string, same as LeRobot does."""
    v = int(value)
    return "".join([chr((v >> 8 * i) & 0xFF) for i in range(4)])


BACKENDS = {"any": cv2.CAP_ANY, "dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF}


def open_camera(index, width, height, fps, fourcc, backend=cv2.CAP_ANY):
    """Open one camera and apply settings the way LeRobot does. Returns (cap, info)."""
    info = {}
    t0 = time.perf_counter()
    cap = cv2.VideoCapture(index, backend)
    info["open_s"] = round(time.perf_counter() - t0, 2)
    info["isOpened"] = cap.isOpened()
    try:
        info["backend"] = cap.getBackendName()
    except Exception:
        info["backend"] = "?"

    if not cap.isOpened():
        cap.release()
        return None, info

    # LeRobot sets fps and size, then FOURCC last on Windows, because on DSHOW
    # changing the resolution can silently override the pixel format.
    cap.set(cv2.CAP_PROP_FPS, float(fps))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))

    set_ok = cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    raw = cap.get(cv2.CAP_PROP_FOURCC)

    info["fourcc_set_ok"] = bool(set_ok)
    info["fourcc_raw"] = raw
    info["fourcc"] = decode_fourcc(raw) if raw else "<EMPTY -- no capture graph>"
    info["w"] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    info["h"] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    info["fps"] = cap.get(cv2.CAP_PROP_FPS)
    return cap, info


def read_frames(cap, n):
    """Read n frames, return (successes, elapsed_seconds)."""
    ok = 0
    t0 = time.perf_counter()
    for _ in range(n):
        ret, frame = cap.read()
        if ret and frame is not None:
            ok += 1
    return ok, round(time.perf_counter() - t0, 2)


def describe(label, info, ok, total, elapsed, want_fourcc):
    """PASS requires: every frame read AND the requested pixel format actually applied."""
    fourcc = info.get("fourcc", "?")
    frames_ok = ok == total
    format_ok = fourcc == want_fourcc
    verdict = "PASS" if (frames_ok and format_ok) else "FAIL"
    why = ""
    if not frames_ok:
        why += " [DROPPED FRAMES]"
    if not format_ok:
        why += f" [WANTED {want_fourcc}, GOT {fourcc}]"
    print(
        f"  [{verdict}] {label}: backend={info.get('backend')} open={info.get('open_s')}s "
        f"isOpened={info.get('isOpened')} fourcc={fourcc!r} "
        f"set_ok={info.get('fourcc_set_ok')} "
        f"{info.get('w')}x{info.get('h')}@{round(float(info.get('fps') or 0), 1)} "
        f"frames={ok}/{total} in {elapsed}s{why}"
    )
    return verdict == "PASS"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--index", type=int, required=True, help="camera index to test")
    p.add_argument("--also", type=int, default=None, help="second camera to open at the same time")
    p.add_argument("--trials", type=int, default=10)
    p.add_argument("--frames", type=int, default=30, help="frames to read per trial")
    p.add_argument("--width", type=int, default=640)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--fourcc", type=str, default="MJPG")
    p.add_argument("--pause", type=float, default=1.0, help="seconds between trials")
    p.add_argument("--soak", type=int, default=0, help="instead of trials, hold open and read for N seconds")
    p.add_argument("--backend", choices=["any", "dshow", "msmf"], default="any",
                   help="capture backend. 'any' matches LeRobot's default (Cv2Backends.ANY)")
    args = p.parse_args()

    cv2.setNumThreads(1)  # matches LeRobot
    backend = BACKENDS[args.backend]

    if args.soak:
        print(f"SOAK: camera {args.index} held open for {args.soak}s\n")
        cap, info = open_camera(args.index, args.width, args.height, args.fps, args.fourcc, backend)
        if cap is None:
            print(f"  FAILED TO OPEN: {info}")
            return
        print(f"  opened: fourcc={info['fourcc']!r} {info['w']}x{info['h']}@{info['fps']}")
        t0 = time.time()
        n = fails = 0
        first_fail_at = None
        while time.time() - t0 < args.soak:
            ret, frame = cap.read()
            n += 1
            if not ret or frame is None:
                fails += 1
                if first_fail_at is None:
                    first_fail_at = round(time.time() - t0, 1)
        cap.release()
        print(f"  reads={n} failures={fails} first_failure_at={first_fail_at}s")
        return

    passes = 0
    for i in range(1, args.trials + 1):
        print(f"Trial {i}/{args.trials}")
        cap_a, info_a = open_camera(args.index, args.width, args.height, args.fps, args.fourcc, backend)
        cap_b, info_b = (None, None)
        if args.also is not None:
            cap_b, info_b = open_camera(args.also, args.width, args.height, args.fps, args.fourcc, backend)

        trial_ok = True
        if cap_a is None:
            print(f"  [FAIL] cam{args.index}: could not open ({info_a})")
            trial_ok = False
        else:
            ok, el = read_frames(cap_a, args.frames)
            trial_ok &= describe(f"cam{args.index}", info_a, ok, args.frames, el, args.fourcc)

        if args.also is not None:
            if cap_b is None:
                print(f"  [FAIL] cam{args.also}: could not open ({info_b})")
                trial_ok = False
            else:
                ok, el = read_frames(cap_b, args.frames)
                trial_ok &= describe(f"cam{args.also}", info_b, ok, args.frames, el, args.fourcc)

        for c in (cap_a, cap_b):
            if c is not None:
                c.release()

        passes += 1 if trial_ok else 0
        time.sleep(args.pause)

    print(f"\nRESULT: {passes}/{args.trials} trials passed")
    if passes == args.trials:
        print("No failure reproduced under these conditions.")
    elif passes == 0:
        print("Fails every time -- not intermittent under these conditions.")
    else:
        print("Intermittent. Note WHICH trial numbers failed and whether fourcc came back empty.")


if __name__ == "__main__":
    main()

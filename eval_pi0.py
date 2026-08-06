"""
eval_pi0.py — run the SO-101 follower against a pi0 policy served remotely by openpi.

WHY THIS EXISTS: `lerobot-rollout` cannot talk to an openpi policy server. LeRobot and
openpi are separate projects with separate wire protocols — LeRobot loads a policy
in-process from a local checkpoint, while openpi serves one over its own websocket
protocol with its own observation schema. Neither knows about the other. This script is
the bridge: it opens the SO-101 follower and both cameras through LeRobot, packs each
observation into the exact keys openpi's SO101Inputs expects, calls the openpi websocket
client, and executes the action chunk that comes back.

It is the counterpart to the local SmolVLA rollout loop, so the same nine-position grid
can be run against a remotely-served pi0 checkpoint under an identical protocol. The
policy runs on a rented GPU; this script owns the arm, the cameras, and the safety
envelope, and does nothing else.

Architecture: read observation -> send to the policy server -> receive an action chunk
-> execute the chunk open-loop at 30 Hz -> re-query. Executing a chunk open-loop is what
hides the round-trip latency to a remote GPU; per-cycle RTT is printed so you can see
whether the network or the arm is the limiting factor.

NO rerun, NO --display_data, no visualization of any kind. That hangs the robot on this
machine and there is no reason to risk it during an eval.

Requires the openpi client package in this env (see README note at the bottom of the
argument parser epilog, or the install command in the commit message).

Usage (from the `lerobot` conda env, with the policy server tunnelled to localhost:8000):

    python eval_pi0.py --task "Pick up the cube and drop it in the tray."

    # different camera indices after a USB replug
    python eval_pi0.py --task "..." --scene-index 1 --wrist-index 3

    # longer run, execute more of each chunk before re-querying
    python eval_pi0.py --task "..." --duration 40 --chunk-exec 40
"""

import argparse
import sys
import time

import numpy as np

from lerobot.cameras.opencv import OpenCVCameraConfig
from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig

from openpi_client import image_tools
from openpi_client import websocket_client_policy


# Joint order. This is the order the dataset's `observation.state` and `action` vectors
# use, and the order lerobot's FeetechMotorsBus declares the motors in
# (lerobot/robots/so_follower/so_follower.py). Both agree; do not reorder.
JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]

# The 5 arm joints are in degrees (use_degrees=True); the gripper is normalised 0-100.
N_ARM = 5

# pi0 sees 224x224. The server applies transforms.ResizeImages(224, 224) itself, which
# calls the very same image_tools.resize_with_pad used below -- doing it client-side is
# therefore bit-identical (resize_with_pad on an already-224x224 input is a no-op) and
# cuts the websocket payload per camera from ~920 KB to ~150 KB.
IMG_SIZE = 224


def build_camera_configs(scene_index, wrist_index):
    """Both cameras 640x480 @ 30fps with MJPG forced -- the known-good configuration."""
    return {
        "scene": OpenCVCameraConfig(
            index_or_path=scene_index, fps=30, width=640, height=480, fourcc="MJPG"
        ),
        "wrist": OpenCVCameraConfig(
            index_or_path=wrist_index, fps=30, width=640, height=480, fourcc="MJPG"
        ),
    }


def build_observation(robot, task):
    """Read the arm and both cameras, and pack them into the dict the policy expects.

    The keys below are the contract from reference/so101_policy.py: SO101Inputs reads
    exactly `observation/image`, `observation/wrist_image`, `observation/state` and
    `prompt`. They are not negotiable and are not remapped anywhere on the server --
    openpi's scripts/serve_policy.py calls create_trained_policy() WITHOUT passing
    repack_transforms, so that parameter defaults to an empty Group and the dataset's
    `observation.images.scene` -> `observation/image` repack runs at TRAINING time only.
    What this function emits is what SO101Inputs receives.

    Camera slots, also from so101_policy.py: scene -> base_0_rgb (third-person),
    wrist -> left_wrist_0_rgb. The unused right-wrist slot is zero-padded server-side.

    Returns (observation_dict, state_vector).
    """
    obs = robot.get_observation()

    state = np.array([obs[f"{j}.pos"] for j in JOINTS], dtype=np.float32)

    scene = image_tools.convert_to_uint8(
        image_tools.resize_with_pad(obs["scene"], IMG_SIZE, IMG_SIZE)
    )
    wrist = image_tools.convert_to_uint8(
        image_tools.resize_with_pad(obs["wrist"], IMG_SIZE, IMG_SIZE)
    )

    packed = {
        "observation/image": scene,
        "observation/wrist_image": wrist,
        "observation/state": state,
        "prompt": task,
    }
    return packed, state


def check_step(target, reference, max_arm_step, max_gripper_step):
    """Return a complaint string if `target` is too far from `reference`, else None."""
    delta = np.abs(target - reference)

    offenders = []
    for i in range(N_ARM):
        if delta[i] > max_arm_step:
            offenders.append(f"{JOINTS[i]} moves {delta[i]:.2f} deg (limit {max_arm_step:.2f})")
    if delta[N_ARM] > max_gripper_step:
        offenders.append(
            f"gripper moves {delta[N_ARM]:.2f} units (limit {max_gripper_step:.2f})"
        )

    if not offenders:
        return None
    return "; ".join(offenders)


def format_vector(vec):
    return "  ".join(f"{name}={value:8.2f}" for name, value in zip(JOINTS, vec))


def safe_shutdown(robot, hold_s):
    """Stop cleanly: freeze at the measured pose, settle, then drop torque.

    Commanding the *current measured* position first means the arm does not lurch
    toward a stale goal on the way out. Torque is then released by disconnect()
    (disable_torque_on_disconnect defaults to True). Gravity still applies once torque
    is off -- support the arm if it is holding a raised pose.
    """
    try:
        if not robot.is_connected:
            return
        obs = robot.get_observation()
        here = {f"{j}.pos": float(obs[f"{j}.pos"]) for j in JOINTS}
        robot.send_action(here)
        print(f"Holding position for {hold_s:.1f}s before releasing torque -- support the arm.")
        time.sleep(hold_s)
    except Exception as exc:  # never let cleanup mask the original failure
        print(f"WARNING: could not freeze pose before shutdown: {exc}")
    finally:
        try:
            robot.disconnect()
            print("Disconnected, torque released.")
        except Exception as exc:
            print(f"WARNING: disconnect failed: {exc}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate a remotely-served pi0 policy on the SO-101 follower.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Language instruction. Must match the training instruction VERBATIM.",
    )
    parser.add_argument("--host", default="localhost", help="Policy server host.")
    parser.add_argument("--port", type=int, default=8000, help="Policy server port.")
    parser.add_argument("--duration", type=float, default=20.0, help="Hard stop, seconds.")
    parser.add_argument("--port-arm", default="COM4", help="Serial port of the follower.")
    parser.add_argument("--robot-id", default="my_follower", help="Follower id (calibration).")
    parser.add_argument("--scene-index", type=int, default=0, help="Scene camera index.")
    parser.add_argument("--wrist-index", type=int, default=2, help="Wrist camera index.")
    parser.add_argument(
        "--chunk-exec",
        type=int,
        default=25,
        help="Actions executed open-loop per chunk before re-querying (horizon is 50).",
    )
    parser.add_argument("--fps", type=float, default=30.0, help="Action execution rate.")
    parser.add_argument(
        "--max-arm-step",
        type=float,
        default=8.0,
        help="Abort if any arm joint is commanded to move more than this (degrees) in one step.",
    )
    parser.add_argument(
        "--max-gripper-step",
        type=float,
        default=15.0,
        help="Abort if the gripper is commanded to move more than this (0-100 units) in one step.",
    )
    parser.add_argument(
        "--hold-on-exit",
        type=float,
        default=1.0,
        help="Seconds to hold the final pose before releasing torque.",
    )
    args = parser.parse_args()

    if args.chunk_exec < 1:
        parser.error("--chunk-exec must be >= 1")

    period = 1.0 / args.fps

    print(f"Connecting to policy server at {args.host}:{args.port} ...")
    client = websocket_client_policy.WebsocketClientPolicy(host=args.host, port=args.port)
    print(f"Server metadata: {client.get_server_metadata()}")

    robot_config = SO101FollowerConfig(
        port=args.port_arm,
        id=args.robot_id,
        cameras=build_camera_configs(args.scene_index, args.wrist_index),
        use_degrees=True,
    )
    robot = SO101Follower(robot_config)

    print(f"Connecting to follower on {args.port_arm} ...")
    robot.connect()
    print("Follower connected.")

    armed = False
    aborted = False
    cycle = 0
    t_start = time.perf_counter()

    try:
        while True:
            elapsed = time.perf_counter() - t_start
            if armed and elapsed >= args.duration:
                print(f"\nDuration limit reached ({args.duration:.1f}s). Stopping.")
                break

            observation, state = build_observation(robot, args.task)

            t_query = time.perf_counter()
            result = client.infer(observation)
            rtt = time.perf_counter() - t_query

            chunk = np.asarray(result["actions"], dtype=np.float32)
            if chunk.ndim != 2 or chunk.shape[1] != len(JOINTS):
                raise RuntimeError(
                    f"Expected an (horizon, {len(JOINTS)}) action chunk, got {chunk.shape}. "
                    "The server is not running the SO-101 config."
                )

            # -----------------------------------------------------------------
            # DELTA ACTIONS: RESOLVED. The server returns ABSOLUTE joint positions.
            # This client must NOT add the current state back to the arm joints.
            #
            # Training converted the 5 arm joints to deltas relative to the first state
            # in each chunk, leaving the gripper absolute. That transform is configured
            # as a MATCHED PAIR, and the inverse half runs server-side at inference.
            #
            # Chain of evidence, all read from source. Every openpi citation below was
            # verified at commit 15a9616a00943ada6c20a0f158e3adb39df2ccac, which is the
            # commit this project's checkpoint was trained and served from. Re-check
            # them against any newer openpi before trusting this client.
            #
            #  1. reference/config.py:400-404, LeRobotSO101DataConfig.create():
            #         delta_action_mask = _transforms.make_bool_mask(5, -1)
            #         data_transforms = data_transforms.push(
            #             inputs=[_transforms.DeltaActions(delta_action_mask)],
            #             outputs=[_transforms.AbsoluteActions(delta_action_mask)],
            #         )
            #     `inputs` is the training direction (absolute -> delta). `outputs` is
            #     the inference direction (delta -> absolute). Both halves are declared.
            #
            #  2. openpi transforms.Group.push appends to inputs but PREPENDS to outputs:
            #         Group(inputs=(*self.inputs, *inputs), outputs=(*outputs, *self.outputs))
            #     so the output chain is (AbsoluteActions, SO101Outputs) -- the un-delta
            #     runs before SO101Outputs' [..., :6] slice. AbsoluteActions indexes only
            #     mask.shape[-1] == 6 dims, so that ordering is harmless.
            #
            #  3. openpi transforms.AbsoluteActions is exactly the inverse of DeltaActions:
            #         actions[..., :dims] += np.expand_dims(
            #             np.where(mask, state[..., :dims], 0), axis=-2)
            #     It adds state back for the 5 masked arm joints; the gripper's mask entry
            #     is False, so `np.where` contributes 0 and the gripper stays absolute.
            #
            #  4. openpi policy.Policy.infer carries state into the output chain precisely
            #     so step 3 has something to add:
            #         outputs = {"state": inputs["state"], "actions": ...}
            #     The state added back is the state THIS client sent this cycle.
            #
            #  5. openpi policy_config.create_trained_policy orders output transforms as
            #     [model_transforms.outputs, Unnormalize, data_transforms.outputs], so
            #     Unnormalize restores real units for BOTH "state" and "actions" before
            #     AbsoluteActions sums them. The result is in raw joint units.
            #
            # Net: send absolute, receive absolute, in the same units and joint order.
            # The chunk below goes straight to send_action() untouched.
            # -----------------------------------------------------------------
            n_exec = min(args.chunk_exec, chunk.shape[0])
            if cycle == 0 and args.chunk_exec > chunk.shape[0]:
                print(
                    f"NOTE: --chunk-exec {args.chunk_exec} exceeds the returned horizon "
                    f"{chunk.shape[0]}; executing {n_exec}."
                )

            if not armed:
                print("\n" + "=" * 78)
                print("FIRST COMMANDED ACTION -- sanity-check this against the current pose.")
                print("=" * 78)
                print(f"  horizon returned : {chunk.shape[0]} actions, executing {n_exec}")
                print(f"  current state    : {format_vector(state)}")
                print(f"  first action     : {format_vector(chunk[0])}")
                print(f"  delta            : {format_vector(chunk[0] - state)}")
                print("=" * 78)
                print("These are ABSOLUTE targets (see the delta-action note in the source).")
                print("If the deltas look wild, Ctrl+C now.")
                try:
                    input("Press Enter to begin moving, or Ctrl+C to abort: ")
                except (EOFError, KeyboardInterrupt):
                    print("\nAborted before any motion.")
                    break
                armed = True
                t_start = time.perf_counter()

            # Safety gate: the first action of a chunk is checked against where the arm
            # actually is; subsequent actions against the previous commanded target.
            reference = state
            for step in range(n_exec):
                target = chunk[step]
                complaint = check_step(target, reference, args.max_arm_step, args.max_gripper_step)
                if complaint is not None:
                    print("\n" + "!" * 78)
                    print(f"ABORT: policy commanded an unsafe step at chunk index {step}.")
                    print(f"  {complaint}")
                    print(f"  reference : {format_vector(reference)}")
                    print(f"  commanded : {format_vector(target)}")
                    print("!" * 78)
                    aborted = True
                    break
                reference = target

            if aborted:
                break

            # Execute the chunk open-loop at a fixed rate. --duration is a hard stop:
            # it breaks mid-chunk rather than overshooting by up to a full chunk.
            deadline = time.perf_counter()
            executed = 0
            for step in range(n_exec):
                if time.perf_counter() - t_start >= args.duration:
                    print(f"\nDuration limit reached ({args.duration:.1f}s) mid-chunk. Stopping.")
                    expired = True
                    break
                action = {f"{j}.pos": float(v) for j, v in zip(JOINTS, chunk[step])}
                robot.send_action(action)
                executed += 1
                deadline += period
                remaining = deadline - time.perf_counter()
                if remaining > 0:
                    time.sleep(remaining)
            else:
                expired = False

            cycle += 1
            exec_s = executed * period
            print(
                f"cycle {cycle:3d} | rtt {rtt * 1000:7.1f} ms | exec {exec_s * 1000:7.1f} ms "
                f"({executed} actions) | rtt/cycle {rtt / (rtt + exec_s) * 100:4.1f}% "
                f"| t {time.perf_counter() - t_start:5.1f}s"
            )

            if expired:
                break

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        safe_shutdown(robot, args.hold_on_exit)

    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())

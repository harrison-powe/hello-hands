# LeRobot command reference — hello-hands

The exact commands used to bring up and drive this SO-101 leader–follower pair.

> **Version.** These are for the **LeRobot 0.6.0** CLI (the version this repo was
> built against), which installs console-script entry points (`lerobot-find-port`,
> `lerobot-calibrate`, …). Each has a module equivalent, e.g.
> `python -m lerobot.scripts.lerobot_calibrate`. Flag names and robot-`type`
> strings have changed across releases — verify with `--help` if you are on a
> different version.
>
> **Shell.** Commands below use `\` line-continuations (bash/WSL style). In
> **Windows PowerShell** (where COM ports live), either put each command on one
> line or replace `\` with a backtick `` ` ``.

## This hardware

| Role     | `--*.type`       | Port   | `--*.id`      |
| -------- | ---------------- | ------ | ------------- |
| Follower | `so101_follower` | `COM4` | `my_follower` |
| Leader   | `so101_leader`   | `COM5` | `my_leader`   |

Cameras are configured inline at **640×480** (see teleoperate/record below).
Calibration for both arms is already committed under [`../calibration/`](../calibration/);
LeRobot also stores it under `~/.cache/huggingface/lerobot/calibration/`. Re-run
`calibrate` only if you re-seat motors or swap hardware.

---

## 0. Environment

```bash
conda activate lerobot        # the env where lerobot 0.6.0 is installed
lerobot-info                  # sanity-check the install / version
```

## 1. Find the serial ports

Run once per arm. Unplug the arm when prompted so the tool can identify which
COM port disappeared. Do the two arms one at a time to tell them apart.

```bash
lerobot-find-port
```

Expected here: follower on `COM4`, leader on `COM5`.

## 2. Set motor IDs (one-time, per arm)

Only needed when first assembling an arm (writes each servo's id 1–6 and
baudrate). Follow the prompts, connecting one motor at a time.

```bash
# Follower
lerobot-setup-motors --robot.type=so101_follower --robot.port=COM4

# Leader
lerobot-setup-motors --teleop.type=so101_leader --teleop.port=COM5
```

## 3. Find cameras

Lists connected cameras and their indices; use the reported index as
`index_or_path` below. (Sample frames are written to `outputs/`, which is
git-ignored.)

```bash
lerobot-find-cameras opencv
```

## 4. Calibrate

Sets each joint's range and homing offset; writes
`<type-name>/<id>.json` under the LeRobot calibration cache.

```bash
# Follower (robot)
lerobot-calibrate --robot.type=so101_follower --robot.port=COM4 --robot.id=my_follower

# Leader (teleoperator)
lerobot-calibrate --teleop.type=so101_leader --teleop.port=COM5 --teleop.id=my_leader
```

> If the **base joint** (`shoulder_pan`) hits a hard stop or its `homing_offset`
> pins to the rail (±2047), the encoder zero is on the 0/4096 wraparound seam.
> Fix it with [`fix_base_encoder.py`](fix_base_encoder.py), then re-run this step.

## 5. Teleoperate (mechanical mirroring — no model, no cameras)

Leader joint angles drive the follower directly. `--display_data=true` opens a
live view; cameras are optional for teleop.

```bash
lerobot-teleoperate \
    --robot.type=so101_follower \
    --robot.port=COM4 \
    --robot.id=my_follower \
    --teleop.type=so101_leader \
    --teleop.port=COM5 \
    --teleop.id=my_leader \
    --display_data=true
```

To preview the camera feed alongside teleop, add a camera:

```bash
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}"
```

## 6. Record demonstrations

Teleoperate while logging synchronized camera + joint frames to a
`LeRobotDataset`. This is pure data collection — no policy inference.

```bash
lerobot-record \
    --robot.type=so101_follower \
    --robot.port=COM4 \
    --robot.id=my_follower \
    --robot.cameras="{ front: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}}" \
    --teleop.type=so101_leader \
    --teleop.port=COM5 \
    --teleop.id=my_leader \
    --dataset.repo_id=<hf-username>/<dataset-name> \
    --dataset.num_episodes=50 \
    --dataset.single_task="Pick up the cube and place it in the bin" \
    --display_data=true
```

- `--dataset.repo_id` is a Hugging Face Hub path — set `<hf-username>` and a
  dataset name (the dataset repo does not exist yet; see the README).
- `num_episodes`, `single_task`, and the camera index/name are examples — adjust
  per recording session.

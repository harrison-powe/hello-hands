# LeRobot command reference — hello-hands

The working reference for this SO-101 leader–follower pair: bring-up,
teleoperation, recording, pushing data to the Hub, SmolVLA fine-tuning, and
autonomous rollout.

> **Version.** These are for the **LeRobot 0.6.0** CLI (the version this repo was
> built against), which installs console-script entry points (`lerobot-find-port`,
> `lerobot-calibrate`, …). Each has a module equivalent, e.g.
> `python -m lerobot.scripts.lerobot_calibrate`. Flag names and robot-`type`
> strings have changed across releases — verify with `--help` if you are on a
> different version.
>
> **Shell.** Commands below use `\` line-continuations (bash/WSL style). In
> **Windows PowerShell** (where COM ports live), either put each command on one
> line or replace `\` with a backtick `` ` ``. The one flag with shell-sensitive
> quoting (`--rename_map`, § 8) is shown exactly as run from **cmd**.

## This hardware

| Role     | `--*.type`       | Port   | `--*.id`      |
| -------- | ---------------- | ------ | ------------- |
| Follower | `so101_follower` | `COM4` | `my_follower` |
| Leader   | `so101_leader`   | `COM5` | `my_leader`   |

Both cameras run **640×480 @ 30 fps**, FOURCC **`MJPG`** (LeRobot forces MJPG
when it connects). Calibration for both arms is committed under
[`../calibration/`](../calibration/); LeRobot also stores it under
`~/.cache/huggingface/lerobot/calibration/`. Re-run `calibrate` only if you
re-seat motors or swap hardware.

## ⚠️ Camera indices — re-verify before EVERY session

As of the last session:

| Index | Device              | Role     |
| ----- | ------------------- | -------- |
| `0`   | Logitech C920s      | scene    |
| `1`   | laptop built-in     | not used |
| `2`   | InnoMaker 32×32 UVC | wrist    |

**These indices drift on ANY USB replug — including the motor control boards,
not just the cameras.** A wrong index does not error: it silently records the
wrong view. Re-verify at the start of every session:

```bash
lerobot-find-cameras opencv
```

(Sample frames land in `outputs/`, which is git-ignored — look at the frames;
don't trust device names alone.)

If a camera misbehaves (empty FOURCC, dropped frames, mid-session drops),
isolate it with [`camera_stress_test.py`](camera_stress_test.py) — usage is in
its docstring.

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

## 3. Calibrate

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

## 4. Teleoperate

Leader joint angles drive the follower directly — no model, no recording.
Without cameras:

```bash
lerobot-teleoperate \
    --robot.type=so101_follower \
    --robot.port=COM4 \
    --robot.id=my_follower \
    --teleop.type=so101_leader \
    --teleop.port=COM5 \
    --teleop.id=my_leader
```

With both cameras and the live viewer — this is how to frame and focus the
shots before a recording session:

```bash
lerobot-teleoperate \
    --robot.type=so101_follower \
    --robot.port=COM4 \
    --robot.id=my_follower \
    --robot.cameras="{ scene: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}}" \
    --teleop.type=so101_leader \
    --teleop.port=COM5 \
    --teleop.id=my_leader \
    --display_data=true
```

> **`--display_data=true` is for framing/focus setup ONLY.** The live viewer
> makes the follower visibly jagged. Never use it while recording.

## 5. Record demonstrations

Teleoperate while logging synchronized camera + joint frames to a
`LeRobotDataset`. The camera names chosen here (`scene`, `wrist`) become the
dataset's camera keys **permanently** — they are frozen at creation (see the
`--rename_map` note in § 8). No `--display_data` here (§ 4).

```bash
lerobot-record \
    --robot.type=so101_follower \
    --robot.port=COM4 \
    --robot.id=my_follower \
    --robot.cameras="{ scene: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}}" \
    --teleop.type=so101_leader \
    --teleop.port=COM5 \
    --teleop.id=my_leader \
    --dataset.repo_id=harrison-powe/<dataset-name> \
    --dataset.single_task="Pick up the Kyogre and drop it in the tray." \
    --dataset.num_episodes=50 \
    --dataset.episode_time_s=15 \
    --dataset.reset_time_s=10 \
    --dataset.push_to_hub=false
```

Defaults worth overriding, and why:

- `--dataset.episode_time_s` / `--dataset.reset_time_s` — default **60 / 60**.
  This task takes ~15 s, so the defaults add a minute of dead air per episode;
  ~**15 / 10** fits.
- `--dataset.push_to_hub` — defaults **`true`**. Set `false` and push
  deliberately after checking the data (§ 7).
- `--dataset.num_episodes` — defaults **50**; set it explicitly anyway.

Dataset #1 ([`harrison-powe/hello-hands-pick-place_20260721_163414`](https://huggingface.co/datasets/harrison-powe/hello-hands-pick-place_20260721_163414))
was recorded exactly this way: 50 episodes / 22,500 frames / 655 MB.

## 6. Append episodes to an existing dataset

Two footguns:

- `--resume=true` is a **top-level** flag — `--dataset.resume` does not exist.
- An explicit `--dataset.root` pointing at the **full stamped dataset folder**
  (the one containing `meta/`, `data/`, `videos/`) is **required**. Default
  location: `~/.cache/huggingface/lerobot/<repo_id>`.

```bash
lerobot-record \
    ... same robot/teleop/camera flags as § 5 ... \
    --dataset.repo_id=harrison-powe/hello-hands-pick-place_20260721_163414 \
    --dataset.root=<lerobot-cache>/harrison-powe/hello-hands-pick-place_20260721_163414 \
    --dataset.single_task="Pick up the Kyogre and drop it in the tray." \
    --dataset.num_episodes=10 \
    --dataset.push_to_hub=false \
    --resume=true
```

## 7. Push a local dataset to the Hub

Recording with `push_to_hub=false` leaves everything local. Publish with:

```bash
python -c "from lerobot.datasets.lerobot_dataset import LeRobotDataset; LeRobotDataset('harrison-powe/hello-hands-pick-place_20260721_163414', root=r'<lerobot-cache>/harrison-powe/hello-hands-pick-place_20260721_163414').push_to_hub()"
```

- `root=` is **required** once the dataset already exists on the Hub —
  without it the constructor resolves the `repo_id` against the Hub copy
  instead of your local folder.
- Needs a logged-in Hugging Face token with write access
  (`huggingface-cli login`); no token lives in this repo.

## 8. Fine-tune SmolVLA (local GPU)

Fine-tuning `smolvla_base` (450M params) trains only the action expert
(~100M); the vision encoder stays frozen. The 20k-step run below took
**~3 h 40 m** on an RTX 2000 Ada 8 GB laptop GPU at batch 16 (≈ 14 epochs over
dataset #1).

One-time: download the base model to a **local folder** (see the
`--policy.path` note below):

```bash
huggingface-cli download lerobot/smolvla_base --local-dir <smolvla_base-dir>
```

**Always shake out first** — 300 steps with `--save_freq=300` proves data
loading, the rename map, and checkpointing in minutes, before committing hours:

```bash
lerobot-train \
    --policy.path=<smolvla_base-dir> \
    --dataset.repo_id=harrison-powe/hello-hands-pick-place_20260721_163414 \
    --dataset.video_backend=pyav \
    --rename_map="{\"observation.images.scene\": \"observation.images.camera1\", \"observation.images.wrist\": \"observation.images.camera2\"}" \
    --policy.push_to_hub=false \
    --batch_size=16 \
    --steps=300 \
    --save_freq=300 \
    --job_name=smolvla_shakeout
```

Real run — same flags, real horizon:

```bash
lerobot-train \
    ... same flags as the shakeout ... \
    --steps=20000 \
    --save_freq=2500 \
    --job_name=<run-name>
```

Why each non-obvious flag exists:

- `--policy.path=<smolvla_base-dir>` — a **local directory**, not the hub id
  `lerobot/smolvla_base`: Windows flips the `/` in the hub id to `\` and the
  Hub rejects the mangled id.
- `--dataset.video_backend=pyav` — the default backend is torchcodec, whose
  DLLs are absent on Windows.
- `--rename_map` — dataset camera keys are frozen at creation (`scene`/`wrist`
  here), but `smolvla_base` expects `camera1/2/3`; this remaps them at train
  time. The quoting shown (`\"`) is **cmd-escaped**, exactly as run on this
  machine; from bash, single-quote the JSON instead.
- `--policy.push_to_hub=false` — defaults `true`, and then demands a
  `--policy.repo_id`.
- `--save_freq=2500` — the default (**20000**) checkpoints only at the very
  end, so a crash at step 19,999 loses everything.

`outputs/` lands **wherever training was launched from** — launch from the
repo root and checkpoints appear under
`outputs/train/<job_name>/checkpoints/<step>/pretrained_model/` (git-ignored
here).

## 9. Autonomous rollout

The policy drives the follower alone: **the leader stays disconnected** — no
`--teleop.*` flags. Re-verify camera indices first (⚠️ section above).

```bash
lerobot-rollout \
    --robot.type=so101_follower \
    --robot.port=COM4 \
    --robot.id=my_follower \
    --robot.cameras="{ camera1: {type: opencv, index_or_path: 0, width: 640, height: 480, fps: 30}, camera2: {type: opencv, index_or_path: 2, width: 640, height: 480, fps: 30}}" \
    --policy.path=outputs/train/<run-name>/checkpoints/<step>/pretrained_model \
    --inference.type=rtc \
    --task="Pick up the Kyogre and drop it in the tray." \
    --duration=30
```

- **Use RTC** (`--inference.type=rtc`, shown above). The sync form is the same
  command without that flag — it runs, but default synchronous inference was
  **severely jittery** on this hardware; keep sync only for A/B debugging.
- Cameras must be named **`camera1`/`camera2` directly** — rollout has **no
  `--rename_map`**. The name→index mapping must reproduce training:
  `scene` → `camera1` (index `0`), `wrist` → `camera2` (index `2`), or the
  policy runs on swapped views.
- `--task` must match the training instruction **verbatim**, punctuation
  included.
- First run with a new checkpoint: start the arm near the training start pose,
  clear the workspace, and keep `--duration=30` short.

# hello-hands

An [SO-101](https://github.com/TheRobotStudio/SO-ARM100) leader–follower robot
arm running Hugging Face's [LeRobot](https://github.com/huggingface/lerobot),
built toward collecting my own demonstration data and fine-tuning Physical
Intelligence's **π0** and **π0.5** models via
[openpi](https://github.com/Physical-Intelligence/openpi). Everything here is
imitation learning — behavior cloning from teleoperated demonstrations. No
reinforcement learning is involved.

This repository is **code + docs only**. No training data, video, or model
checkpoints live here. The datasets are published to the Hugging Face Hub; see
[Datasets & models](#datasets--models) for dataset links and checkpoint status.

## Status

Both arms are assembled and calibrated, six joints each on Feetech STS3215
servos, with the calibration committed under [`calibration/`](calibration/) as
reproducibility evidence. Teleoperation works across all six joints; getting
there required diagnosing an encoder wraparound on the base joint, described in
[the base-joint encoder bug](#the-base-joint-encoder-bug). Both cameras are
installed and recording at 640×480.

Two datasets have been recorded and published, and four policies fine-tuned and
evaluated — two SmolVLA runs locally, plus π0 and π0.5 LoRA runs via openpi. The
π0 policy remains the best measured policy at 56%, and
[`eval_pi0.py`](eval_pi0.py) is the client used to evaluate both PI policies on
the same grid as the local policies. See [Results](#results) for what those
numbers do and do not show.

Nothing here is robust. The best policy fails just under half its trials, and
the failure patterns are visible but not yet fully resolved.

## Results

Four policies were each scored over an eighteen-trial, nine-position grid with
two laps and a 20-second binary success criterion. The controlled comparisons
are narrower than that shared outline:

| Policy | Model     | Dataset                               | Success     |
| ------ | --------- | ------------------------------------- | ----------- |
| #1     | SmolVLA   | #1 — Kyogre plush, 50 episodes        | 4/18 — 22%  |
| #2a    | SmolVLA   | #2 — 35 mm printed cube, 100 episodes | 2/18 — 11%  |
| #2b    | π0 LoRA   | #2 — same dataset                     | 10/18 — 56% |
| #3     | π0.5 LoRA | #2 — same dataset                     | 7/18 — 39%  |

Policy #1's 22% is **not** comparable to the dataset-#2 rates. Different object,
different camera framing, different start region. It is recorded for history,
not for comparison. The cleanest controlled comparison remains SmolVLA #2a
against π0 #2b: same dataset, grid, day, camera pose, cube, task string, and
success criterion.

π0.5 #3 was evaluated later, on 2026-08-18. It used the same dataset, cube,
camera pose, grid, task string, and criterion, with `--chunk-exec 25`, but the
official grid used the corrected arm clamp: 6.51°/step at chunk indices 1+, with
index 0 exempt. The 15.0 gripper clamp was unchanged. It is therefore a close
same-dataset benchmark, not a literal same-day run-conditions control. Within
its 7/18 total, π0.5 scored 5/8 across trained-region positions 5/6/8/9, 1/2 at
position 4 (not sampled in dataset #2), and 0/6 in column A.

The clearest controlled finding is model-side: at four positions where SmolVLA
#2a managed 2/8 and never closed the gripper, π0 #2b went 8/8 with the data and
hardware held constant. Column A remains unresolved. All three dataset-#2
policies are 0/6 there, which strengthens the data-coverage hypothesis but does
not rule out camera framing or reach geometry.

## The pipeline

- [x] **Assemble** the leader and follower arms
- [x] **Calibrate** every joint (per-motor range + homing offset)
- [x] **Teleoperate** — leader drives follower across all 6 joints
- [x] **Install cameras**
- [x] **Collect demonstrations** — teleoperate while recording camera + joint
      data into a `LeRobotDataset`
- [x] **Validate the full loop locally** — fine-tune SmolVLA and deploy it
      autonomously via `lerobot-rollout`
- [x] **Fine-tune π0 and π0.5** with LoRA on rented GPUs via openpi
- [x] **Deploy and evaluate both PI policies** behind an openpi policy server —
      [`eval_pi0.py`](eval_pi0.py)
- [x] **Preserve working SO-101 openpi support** —
      [`harrison-powe/openpi`, branch `so101-support`](https://github.com/harrison-powe/openpi/tree/so101-support)
      at commit [`d237709`](https://github.com/harrison-powe/openpi/commit/d237709),
      not upstream-merged or claimed upstream-ready
- [ ] **Close the coverage gap** — demonstrations in the far column, where every
      dataset-#2 policy so far has gone 0/6

Exact commands for the completed steps are in
[`scripts/commands.md`](scripts/commands.md).

## Hardware

| Role     | Arm type         | Port   | LeRobot id    |
| -------- | ---------------- | ------ | ------------- |
| Follower | `so101_follower` | `COM4` | `my_follower` |
| Leader   | `so101_leader`   | `COM5` | `my_leader`   |

- 6× Feetech STS3215 servos per arm (12-bit absolute encoders).
- Wrist camera: InnoMaker 32×32 UVC on a printed plug mount (follower gripper),
  640×480 @ 30 fps, MJPG forced.
- Scene camera: Logitech C920s on a desk clamp, 640×480 @ 30 fps, MJPG forced.

## The base-joint encoder bug

The follower's base joint (`shoulder_pan`) would drive into a hard stop under
torque. Root cause: its encoder zero landed on the **0 / 4096 wraparound seam**
of the 12-bit absolute encoder, which pinned `homing_offset` at its rail (±2047)
and pushed the joint's forward target outside its usable swept range.

Fix, without disassembly: hold the arm at forward-center and issue the Feetech
**"one-key middle"** command (write `128` to the `Torque_Enable` register) so the
servo re-homes its center to 2048, then recalibrate.

→ [`scripts/fix_base_encoder.py`](scripts/fix_base_encoder.py) — small,
heavily-commented, runnable. The header documents the bug in full.

The committed follower calibration is the post-fix state — its `shoulder_pan`
homing_offset (-2014) sits off the ±2047 rail — while the leader's railed base
offset (-2047) is a benign torque-off artifact, since the leader is never driven
under power.

## Repository layout

```
hello-hands/
├── .gitignore
├── README.md
├── LICENSE                         # MIT
├── eval_pi0.py                     # SO-101 ↔ openpi policy server eval client
├── reference/                      # openpi additions (Apache 2.0, see its README)
│   ├── README.md
│   ├── so101_policy.py             # openpi transforms for the SO-101
│   ├── config_so101_additions.py   # openpi training-config excerpt
│   └── LOCAL_PATCHES.md            # patches to the openpi checkout
├── print/
│   ├── README.md                   # Bambu A1 print settings
│   └── Cube Pick and Place Objects.3mf   # cube + tray, the dataset #2 objects
├── scripts/
│   ├── camera_stress_test.py       # standalone camera/USB diagnostic
│   ├── fix_base_encoder.py         # base-joint encoder one-key-middle fix
│   └── commands.md                 # LeRobot CLI reference for this hardware
└── calibration/
    ├── my_follower.json            # follower calibration (reproducibility evidence)
    └── my_leader.json              # leader calibration
```

## Datasets & models

The datasets are published to the Hugging Face Hub; checkpoints remain local.

- **Dataset #1** —
  [`harrison-powe/hello-hands-pick-place_20260721_163414`](https://huggingface.co/datasets/harrison-powe/hello-hands-pick-place_20260721_163414)
  — 50 episodes / 22,500 frames, two camera views, Kyogre plush
- **Dataset #2** —
  [`harrison-powe/hello-hands-cube-pick-place_20260804_190811`](https://huggingface.co/datasets/harrison-powe/hello-hands-cube-pick-place_20260804_190811)
  — 100 episodes / 45,000 frames, two camera views,
  [35 mm printed cube](print/)

No model checkpoints are published to the Hub. The SmolVLA checkpoints remain
local-only. Inference-complete local copies of both PI checkpoints are available
at:

- **π0** — `C:\Users\harri\models\pi0_so101_cube_lora\9999`
- **π0.5** — `C:\Users\harri\models\pi05_so101_cube_lora\9999`

## Upstream

- [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) — arm hardware (SO-100 / SO-101)
- [huggingface/lerobot](https://github.com/huggingface/lerobot) — robotics library, and SmolVLA
- [Physical-Intelligence/openpi](https://github.com/Physical-Intelligence/openpi) — π0 model + serving
- [harrison-powe/openpi](https://github.com/harrison-powe/openpi/tree/so101-support) — preserved working SO-101 support; not upstream-merged

## License

[MIT](LICENSE) © 2026 Harrison Powe

The files under [`reference/`](reference/) are derived from openpi and remain
under the [Apache License, Version
2.0](http://www.apache.org/licenses/LICENSE-2.0); see
[`reference/README.md`](reference/README.md).

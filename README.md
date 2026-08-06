# hello-hands

An [SO-101](https://github.com/TheRobotStudio/SO-ARM100) leader–follower robot
arm running Hugging Face's [LeRobot](https://github.com/huggingface/lerobot),
built toward collecting my own demonstration data and fine-tuning Physical
Intelligence's **π0** model via
[openpi](https://github.com/Physical-Intelligence/openpi). Everything here is
imitation learning — behavior cloning from teleoperated demonstrations. No
reinforcement learning is involved.

This repository is **code + docs only**. No training data, video, or model
checkpoints live here — those are published to the Hugging Face Hub (see
[Datasets & models](#datasets--models)).

## Status

Both arms are assembled and calibrated, six joints each on Feetech STS3215
servos, with the calibration committed under [`calibration/`](calibration/) as
reproducibility evidence. Teleoperation works across all six joints; getting
there required diagnosing an encoder wraparound on the base joint, described in
[the base-joint encoder bug](#the-base-joint-encoder-bug). Both cameras are
installed and recording at 640×480.

Two datasets have been recorded and published, and three policies fine-tuned and
evaluated against a fixed protocol — two SmolVLA runs locally, and one π0 LoRA
run on a rented A100 via openpi. The π0 policy is the best of the three at 56%,
and [`eval_pi0.py`](eval_pi0.py) is the client that evaluates it against the same
grid the local policies were scored on. See [Results](#results) for what those
numbers do and do not show.

Nothing here is robust. The best policy fails just under half its trials, and
the failures are understood well enough to name but not yet fixed.

## Results

Three policies, one fixed protocol: nine marked positions on the workspace, two
laps each, eighteen trials, binary success meaning the cube ends up in the tray
within 20 seconds.

| Policy | Model   | Dataset                               | Success     |
| ------ | ------- | ------------------------------------- | ----------- |
| #1     | SmolVLA | #1 — Kyogre plush, 50 episodes        | 4/18 — 22%  |
| #2a    | SmolVLA | #2 — 35 mm printed cube, 100 episodes | 2/18 — 11%  |
| #2b    | π0 LoRA | #2 — same dataset                     | 10/18 — 56% |

Policy #1's 22% is **not** comparable to the other two. Different object,
different camera framing, different start region. It is recorded for history,
not for comparison. The 11% and 56% are directly comparable: identical dataset,
grid, camera pose, cube, and success criterion, run on the same day.

The result worth leading with is where those two diverge. At the four positions
where SmolVLA managed 2/8 and never once closed the gripper, π0 went 8/8. At a
position the dataset never sampled, π0 went 2/2. In the far column both models
went 0/6.

Those are two different failures with two different causes. The grasp failure
was model capacity: same data, same framing, same everything, and π0 closed the
gripper where SmolVLA could not. The coverage failure is data: the far column is
absent from the demonstrations, and neither model reaches what it was never
shown.

Going in, the prediction was that both failures were data problems and that a
better dataset would fix them. Half of that was wrong. Swapping the model fixed
the grasp with the dataset held constant, which is not what a data problem looks
like. The coverage gap survived the model swap unchanged, which is.

## The pipeline

- [x] **Assemble** the leader and follower arms
- [x] **Calibrate** every joint (per-motor range + homing offset)
- [x] **Teleoperate** — leader drives follower across all 6 joints
- [x] **Install cameras**
- [x] **Collect demonstrations** — teleoperate while recording camera + joint
      data into a `LeRobotDataset`
- [x] **Validate the full loop locally** — fine-tune SmolVLA and deploy it
      autonomously via `lerobot-rollout`
- [x] **Fine-tune π0** with LoRA on a rented A100 via openpi
- [x] **Deploy** the trained policy behind an openpi policy server and evaluate
      it on the same grid — [`eval_pi0.py`](eval_pi0.py)
- [ ] **Close the coverage gap** — demonstrations in the far column, where every
      policy so far has gone 0/6

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

Published to the Hugging Face Hub as the project reaches each step.

- **Dataset #1** —
  [`harrison-powe/hello-hands-pick-place_20260721_163414`](https://huggingface.co/datasets/harrison-powe/hello-hands-pick-place_20260721_163414)
  — 50 episodes / 22,500 frames, two camera views, Kyogre plush
- **Dataset #2** —
  [`harrison-powe/hello-hands-cube-pick-place_20260804_190811`](https://huggingface.co/datasets/harrison-powe/hello-hands-cube-pick-place_20260804_190811)
  — 100 episodes, two camera views, [35 mm printed cube](print/)

No model checkpoints are published. The SmolVLA checkpoints are local-only and
the π0 LoRA checkpoint lives on the rented GPU's volume; neither has been pushed
to the Hub.

## Upstream

- [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) — arm hardware (SO-100 / SO-101)
- [huggingface/lerobot](https://github.com/huggingface/lerobot) — robotics library, and SmolVLA
- [Physical-Intelligence/openpi](https://github.com/Physical-Intelligence/openpi) — π0 model + serving

## License

[MIT](LICENSE) © 2026 Harrison Powe

The files under [`reference/`](reference/) are derived from openpi and remain
under the [Apache License, Version
2.0](http://www.apache.org/licenses/LICENSE-2.0); see
[`reference/README.md`](reference/README.md).

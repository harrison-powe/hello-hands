# hello-hands

An [SO-101](https://github.com/TheRobotStudio/SO-ARM100) leader–follower robot
arm running [LeRobot](https://github.com/huggingface/lerobot), built toward
collecting my own demonstration data and fine-tuning Physical Intelligence's
**π0** model via [openpi](https://github.com/Physical-Intelligence/openpi).

This repository is **code + docs only**. No training data, video, or model
checkpoints live here — those are published to the Hugging Face Hub (see
[Datasets & models](#datasets--models)).

## Status

- ✅ **Both arms assembled and calibrated** — leader and follower, 6 joints each
  (Feetech STS3215 servos). Calibration is committed under
  [`calibration/`](calibration/).
- ✅ **Teleoperation works on all 6 joints.** Along the way the base joint
  (`shoulder_pan`) had an encoder **wraparound bug** — diagnosed and fixed; see
  [the base-joint encoder bug](#the-base-joint-encoder-bug).
- ✅ **Both cameras installed** — wrist (InnoMaker 32×32 UVC, on the follower
  gripper) and scene (Logitech C920s), 640×480 @ 30 fps.
- ✅ **50 demonstrations recorded and published** — 22,500 frames, two camera
  views — [dataset on the Hub](https://huggingface.co/datasets/harrison-powe/hello-hands-pick-place_20260721_163414).
- ✅ **SmolVLA fine-tuned locally** on that dataset and deployed autonomously
  via `lerobot-rollout` (leader disconnected, RTC inference).
- 🔧 **The policy approaches the correct object but fails the grasp** — the
  task is not yet completed autonomously. Dataset #2 (rigid object, denser
  start region) is the next pass.
- ⬜ **π0 fine-tuning via openpi — not started.**

A fine-tuned policy now exists and pursues the right object, but the task is
not yet completed autonomously and π0 is untouched; this README claims only
what is actually complete.

## The pipeline

- [x] **Assemble** the leader and follower arms
- [x] **Calibrate** every joint (per-motor range + homing offset)
- [x] **Teleoperate** — leader drives follower across all 6 joints
- [x] **Install cameras**
- [x] **Collect demonstrations** — teleoperate while recording camera + joint
      data into a
      [`LeRobotDataset`](https://huggingface.co/datasets/harrison-powe/hello-hands-pick-place_20260721_163414)
- [x] **Validate the full loop locally** — fine-tune SmolVLA and deploy it
      autonomously (approaches the object; grasp not yet reliable)
- [ ] **Fine-tune π0** with LoRA on a rented GPU (via openpi) — imitation learning (behavior cloning), not RL
- [ ] **Deploy** the trained policy behind an openpi policy server
- [ ] **Iterate on data quality** — more/better demonstrations, retrain —
      dataset #2 (rigid object, denser start region) is the planned next pass

Exact commands for the completed and in-progress steps are in
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
├── LICENSE                     # MIT
├── scripts/
│   ├── camera_stress_test.py   # standalone camera/USB diagnostic
│   ├── fix_base_encoder.py     # base-joint encoder one-key-middle fix
│   └── commands.md             # LeRobot CLI reference for this hardware
└── calibration/
    ├── my_follower.json        # follower calibration (reproducibility evidence)
    └── my_leader.json          # leader calibration
```

_(A `docs/` folder with longer build write-ups is planned but not yet written.)_

## Datasets & models

Published to the Hugging Face Hub as the project reaches each step. **The
dataset is live; the π0 policy does not exist yet:**

- **Demonstration dataset** —
  [`harrison-powe/hello-hands-pick-place_20260721_163414`](https://huggingface.co/datasets/harrison-powe/hello-hands-pick-place_20260721_163414)
  — 50 episodes / 22,500 frames, two camera views
- **Fine-tuned π0 policy** — _TODO:_ `https://huggingface.co/<hf-username>/<model-name>`

_(The interim SmolVLA checkpoints are local-only and not published.)_

## Upstream

- [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) — arm hardware (SO-100 / SO-101)
- [huggingface/lerobot](https://github.com/huggingface/lerobot) — robotics library
- [Physical-Intelligence/openpi](https://github.com/Physical-Intelligence/openpi) — π0 model + serving

## License

[MIT](LICENSE) © 2026 Harrison Powe

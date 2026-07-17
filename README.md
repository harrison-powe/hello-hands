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
  [the debugging highlight](#debugging-highlight-the-base-joint-encoder).
- 🔧 **Currently installing cameras** (640×480).
- ⬜ **Data collection and π0 fine-tuning are next — not started.**

Nothing below the camera step has been done yet; this README claims only what
is actually complete.

## The pipeline

- [x] **Assemble** the leader and follower arms
- [x] **Calibrate** every joint (per-motor range + homing offset)
- [x] **Teleoperate** — leader drives follower across all 6 joints
- [ ] **Install cameras** — _in progress_
- [ ] **Collect demonstrations** — teleoperate while recording camera + joint
      data into a `LeRobotDataset` — _next_
- [ ] **Fine-tune π0** with LoRA on a rented GPU (via openpi) — imitation learning (behavior cloning), not RL
- [ ] **Deploy** the trained policy behind an openpi policy server
- [ ] **Iterate on data quality** — more/better demonstrations, retrain

Exact commands for the completed and in-progress steps are in
[`scripts/commands.md`](scripts/commands.md).

## Hardware

| Role     | Arm type         | Port   | LeRobot id    |
| -------- | ---------------- | ------ | ------------- |
| Follower | `so101_follower` | `COM4` | `my_follower` |
| Leader   | `so101_leader`   | `COM5` | `my_leader`   |

- 6× Feetech STS3215 servos per arm (12-bit absolute encoders).
- Cameras at 640×480 (installation in progress).

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
│   ├── fix_base_encoder.py     # base-joint encoder one-key-middle fix
│   └── commands.md             # LeRobot CLI reference for this hardware
└── calibration/
    ├── my_follower.json        # follower calibration (reproducibility evidence)
    └── my_leader.json          # leader calibration
```

_(A `docs/` folder with longer build write-ups is planned but not yet written.)_

## Datasets & models

Published to the Hugging Face Hub as the project reaches each step. **Neither
exists yet:**

- **Demonstration dataset** — _TODO:_ `https://huggingface.co/datasets/<hf-username>/<dataset-name>`
- **Fine-tuned π0 policy** — _TODO:_ `https://huggingface.co/<hf-username>/<model-name>`

## Upstream

- [TheRobotStudio/SO-ARM100](https://github.com/TheRobotStudio/SO-ARM100) — arm hardware (SO-100 / SO-101)
- [huggingface/lerobot](https://github.com/huggingface/lerobot) — robotics library
- [Physical-Intelligence/openpi](https://github.com/Physical-Intelligence/openpi) — π0 model + serving

## License

[MIT](LICENSE) © 2026 Harrison Powe

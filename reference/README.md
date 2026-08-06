# openpi additions for the SO-101

openpi ships no SO-100 or SO-101 support. It has policy transforms and training configs
for ALOHA, DROID and LIBERO, and nothing for the SO-ARM family. Fine-tuning π0 on data
recorded from this arm therefore required writing the robot-specific pieces from scratch
and patching openpi's dependency pins to accept a v3.0-format LeRobot dataset.

These files are that work, kept here so the training run is reproducible. They are not
importable from this repository — they belong inside an openpi checkout, at the paths
named in each file.

## Upstream version

Everything here was written against openpi at commit
[`15a9616a00943ada6c20a0f158e3adb39df2ccac`](https://github.com/Physical-Intelligence/openpi/commit/15a9616a00943ada6c20a0f158e3adb39df2ccac)
("update output objects to support batching", 2026-06-16). The placement instructions in
`config_so101_additions.py` were re-checked against that commit and anchor on
neighbouring symbol names rather than line numbers, since line numbers drift.

The behavior [`eval_pi0.py`](../eval_pi0.py) depends on was verified at the same commit:
`Group.push` prepends to the output transform list, `AbsoluteActions` adds state back to
the masked dimensions, `Policy.infer` carries `state` into the output chain,
`create_trained_policy` runs `Unnormalize` before the data transform outputs, and
`Pi0Config.action_horizon` defaults to 50. Those five facts are what make the policy
server return absolute joint positions rather than deltas. If you move to a newer openpi,
re-check them before trusting the client.

`so101_policy.py` is the observation and action transform pair. It maps the SO-101's six
joints and two cameras onto what π0 expects: the scene camera fills the third-person
image slot, the wrist camera fills the left-wrist slot, and the unused right-wrist slot
is zero-padded and masked off. Copy it to `src/openpi/policies/so101_policy.py`. The keys
it reads are the wire contract for anything talking to a policy server serving this
checkpoint, which is why [`eval_pi0.py`](../eval_pi0.py) reads them from here rather than
guessing.

`config_so101_additions.py` is an excerpt, not a module — the `LeRobotSO101DataConfig`
class and the `pi0_so101_cube_lora` TrainConfig, with placement instructions for the
three points where they get pasted into openpi's `src/openpi/training/config.py`. The
whole upstream file is not vendored here; only the additions are.

`LOCAL_PATCHES.md` records the changes made to the openpi checkout itself. The
substantial one is a dependency chain: openpi pins lerobot to a revision whose dataset
format predates v3.0, the obvious upgrade requires a Python version openpi does not pin,
and the version that satisfies both drags in a `rerun-sdk` release that conflicts with
openpi's numpy pin. Two loader fixes and a system ffmpeg install sit on top of that.

The single detail most likely to produce a policy that moves plausibly and is completely
wrong is the delta-action conversion. π0 trains on delta actions; teleoperated LeRobot
data records absolute joint positions. The config converts the five arm joints to deltas
and leaves the gripper absolute, and declares the inverse transform so the policy server
returns absolute positions at inference time. Both halves have to be present, and
`compute_norm_stats` is the check that they are.

## Attribution

`so101_policy.py` and `config_so101_additions.py` are derived from
[openpi](https://github.com/Physical-Intelligence/openpi), Copyright Physical
Intelligence, licensed under the [Apache License, Version
2.0](http://www.apache.org/licenses/LICENSE-2.0). Each file carries the notice and a
description of what was changed. The rest of this repository is MIT.

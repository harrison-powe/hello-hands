"""
Additions to openpi's `src/openpi/training/config.py` for the SO-101.

NOT A STANDALONE MODULE. This is an excerpt, kept here so the SO-101 training setup is
reproducible without vendoring openpi's whole 47 KB config file. Nothing here imports or
runs on its own -- the names it references (`DataConfigFactory`, `_transforms`,
`pi0_config`, `weight_loaders`, `DataConfig`, `AssetsConfig`) are openpi's, and it is
meant to be pasted into openpi's config.py at the three points marked below.

Derived from `src/openpi/training/config.py` in openpi
(https://github.com/Physical-Intelligence/openpi), Copyright Physical Intelligence,
licensed under the Apache License, Version 2.0:

    http://www.apache.org/licenses/LICENSE-2.0

Modifications: the `LeRobotSO101DataConfig` class and the `pi0_so101_cube_lora`
TrainConfig below are new additions written for this project; openpi ships no SO-100 or
SO-101 support. Line numbers refer to openpi at base commit 15a9616.


PLACEMENT -- three edits to openpi's config.py
==============================================

Find the neighbouring SYMBOLS, not the line numbers. Line numbers drift with every
upstream change; they are given only as a hint, and they are the numbers in openpi at
commit 15a9616 (the commit these additions were written against -- see
`reference/README.md`). The symbol anchors are what to search for.

1. The import. Insert after the last `openpi.policies.*` import, which upstream is
   `import openpi.policies.libero_policy as libero_policy`, and before
   `import openpi.shared.download as _download`. The block is alphabetically sorted and
   `so101_policy` belongs there. (Hint: ~line 23.)

       import openpi.policies.so101_policy as so101_policy

2. `LeRobotSO101DataConfig`. Insert after the end of the `LeRobotLiberoDataConfig` class
   body, and before the `@dataclasses.dataclass(frozen=True)` decorator belonging to
   `RLDSDroidDataConfig`. (Hint: ~line 356.)

3. The `TrainConfig` entry, inside the `_CONFIGS` list. Insert after the `pi05_libero`
   entry's closing `),` and before the comment block reading `# Fine-tuning Aloha
   configs.` that introduces `pi0_aloha_pen_uncap`. The snippet below includes its own
   `# Fine-tuning SO-101 configs.` banner to match the surrounding style.
   (Hint: ~line 764 upstream. Note this is NOT where it ends up in the patched file --
   edits 1 and 2 push it down by roughly 80 lines.)

The companion file `so101_policy.py` goes in as `src/openpi/policies/so101_policy.py`.
The dependency and loader patches this config depends on are in `LOCAL_PATCHES.md`.
"""


# =============================================================================
# EDIT 2 -- data config. After LeRobotLiberoDataConfig, before RLDSDroidDataConfig.
# =============================================================================

@dataclasses.dataclass(frozen=True)
class LeRobotSO101DataConfig(DataConfigFactory):
    """Data config for an SO-101 LeRobot dataset recorded with `lerobot-record`.

    Assumes the dataset was recorded with two cameras named `scene` and `wrist`,
    giving the feature keys `observation.images.scene` / `observation.images.wrist`.
    """

    # LeRobot datasets store the action under the singular key "action", while the
    # DataConfig default is "actions". Override so the loader builds the action
    # sequence from the right key.
    action_sequence_keys: Sequence[str] = ("action",)

    @override
    def create(self, assets_dirs: pathlib.Path, model_config: _model.BaseModelConfig) -> DataConfig:
        # Maps the dataset's keys to the keys SO101Inputs expects.
        # Format is {target_key: source_key}.
        repack_transform = _transforms.Group(
            inputs=[
                _transforms.RepackTransform(
                    {
                        "observation/image": "observation.images.scene",
                        "observation/wrist_image": "observation.images.wrist",
                        "observation/state": "observation.state",
                        "actions": "action",
                        "prompt": "prompt",
                    }
                )
            ]
        )

        data_transforms = _transforms.Group(
            inputs=[so101_policy.SO101Inputs(model_type=model_config.model_type)],
            outputs=[so101_policy.SO101Outputs()],
        )

        # pi0 is trained on DELTA actions. LeRobot teleoperation records ABSOLUTE
        # joint positions (the leader's angles copied to the follower), so this
        # conversion is required -- unlike LIBERO, whose data is already delta.
        # make_bool_mask(5, -1) => [True]*5 + [False]: the 5 arm joints become
        # deltas, the gripper stays absolute.
        delta_action_mask = _transforms.make_bool_mask(5, -1)
        data_transforms = data_transforms.push(
            inputs=[_transforms.DeltaActions(delta_action_mask)],
            outputs=[_transforms.AbsoluteActions(delta_action_mask)],
        )

        model_transforms = ModelTransformFactory()(model_config)

        return dataclasses.replace(
            self.create_base_config(assets_dirs, model_config),
            repack_transforms=repack_transform,
            data_transforms=data_transforms,
            model_transforms=model_transforms,
            action_sequence_keys=self.action_sequence_keys,
        )


# =============================================================================
# EDIT 3 -- train config. In _CONFIGS, after pi05_libero, before pi0_aloha_pen_uncap.
# =============================================================================

    #
    # Fine-tuning SO-101 configs.
    #
    TrainConfig(
        name="pi0_so101_cube_lora",
        # pi0 with LoRA on both the VLM backbone and the action expert.
        model=pi0_config.Pi0Config(paligemma_variant="gemma_2b_lora", action_expert_variant="gemma_300m_lora"),
        data=LeRobotSO101DataConfig(
            repo_id="harrison-powe/hello-hands-cube-pick-place_20260804_190811",
            # Pulls the instruction from the dataset's task string.
            base_config=DataConfig(prompt_from_task=True),
        ),
        weight_loader=weight_loaders.CheckpointWeightLoader("gs://openpi-assets/checkpoints/pi0_base/params"),
        num_train_steps=30_000,
        # Must match the model config above.
        freeze_filter=pi0_config.Pi0Config(
            paligemma_variant="gemma_2b_lora", action_expert_variant="gemma_300m_lora"
        ).get_freeze_filter(),
        # EMA is turned off for LoRA finetuning.
        ema_decay=None,
    ),


# =============================================================================
# Notes on two settings that would fail silently
# =============================================================================
#
# `action_sequence_keys=("action",)` -- the base DataConfig defaults to the plural
# "actions". LeRobot datasets store the singular "action". LeRobotAlohaDataConfig
# overrides this; LeRobotLiberoDataConfig does not, because their converted dataset
# uses the plural. Copying the LIBERO config verbatim means the action sequence is
# never found.
#
# The delta-action conversion is REQUIRED and is commented out in openpi's LIBERO
# example, because LIBERO's data is already delta. Teleoperated LeRobot data is not.
# `compute_norm_stats` is the check: with the mask applied, the five arm dimensions
# should come out with mean near zero while the gripper stays absolute. Large arm
# means mean the transform is not being applied.
#
# `action_horizon` is not set here, so it takes the Pi0Config default of 50. Any
# client executing these chunks should expect 50 actions per inference call.

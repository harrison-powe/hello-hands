"""
SO-101 policy transforms for openpi.

Save as: src/openpi/policies/so101_policy.py

Derived from `src/openpi/policies/libero_policy.py` in openpi
(https://github.com/Physical-Intelligence/openpi), Copyright Physical Intelligence,
licensed under the Apache License, Version 2.0:

    http://www.apache.org/licenses/LICENSE-2.0

Modified for the SO-101: action dimension, camera slot assignment, and the output
slice. Key differences from the LIBERO original:
  - 6 action dimensions (shoulder_pan, shoulder_lift, elbow_flex, wrist_flex,
    wrist_roll, gripper) instead of LIBERO's 7.
  - Two cameras: a scene camera (third-person) and a wrist camera.
    pi0 supports three image slots (one third-person + two wrist views), so the
    right-wrist slot is zero-padded and masked off.
"""

import dataclasses

import einops
import numpy as np

from openpi import transforms
from openpi.models import model as _model

# The SO-101 has 6 joints: 5 arm joints + 1 gripper.
SO101_ACTION_DIM = 6


def make_so101_example() -> dict:
    """Creates a random input example for the SO-101 policy (used for smoke tests)."""
    return {
        "observation/state": np.random.rand(SO101_ACTION_DIM),
        "observation/image": np.random.randint(256, size=(224, 224, 3), dtype=np.uint8),
        "observation/wrist_image": np.random.randint(256, size=(224, 224, 3), dtype=np.uint8),
        "prompt": "Pick up the cube and drop it in the tray.",
    }


def _parse_image(image) -> np.ndarray:
    """LeRobot stores images as float32 (C,H,W); the model wants uint8 (H,W,C)."""
    image = np.asarray(image)
    if np.issubdtype(image.dtype, np.floating):
        image = (255 * image).astype(np.uint8)
    if image.shape[0] == 3:
        image = einops.rearrange(image, "c h w -> h w c")
    return image


@dataclasses.dataclass(frozen=True)
class SO101Inputs(transforms.DataTransformFn):
    """Converts SO-101 data into the format the model expects.

    Used for BOTH training and inference, so the keys here must match what the
    policy server receives at inference time as well as what the repack transform
    produces during training.
    """

    # Determines which model will be used. Do not change.
    model_type: _model.ModelType

    def __call__(self, data: dict) -> dict:
        base_image = _parse_image(data["observation/image"])
        wrist_image = _parse_image(data["observation/wrist_image"])

        inputs = {
            "state": data["observation/state"],
            "image": {
                # Scene camera -> third-person slot.
                "base_0_rgb": base_image,
                # Wrist camera -> left wrist slot.
                "left_wrist_0_rgb": wrist_image,
                # No second wrist camera on the SO-101: pad with zeros.
                "right_wrist_0_rgb": np.zeros_like(base_image),
            },
            "image_mask": {
                "base_0_rgb": np.True_,
                "left_wrist_0_rgb": np.True_,
                # pi0 masks padding images; pi0-FAST does not. Do not change.
                "right_wrist_0_rgb": np.True_ if self.model_type == _model.ModelType.PI0_FAST else np.False_,
            },
        }

        # Actions are only present during training.
        if "actions" in data:
            inputs["actions"] = data["actions"]

        # The language instruction. Pulled from the dataset's task string when
        # prompt_from_task=True is set in the DataConfig.
        if "prompt" in data:
            inputs["prompt"] = data["prompt"]

        return inputs


@dataclasses.dataclass(frozen=True)
class SO101Outputs(transforms.DataTransformFn):
    """Converts model outputs back to the SO-101 action format. Inference only."""

    def __call__(self, data: dict) -> dict:
        # Actions were padded up to the model's action dimension on the way in,
        # so slice back down to the SO-101's 6 real dimensions.
        return {"actions": np.asarray(data["actions"][..., :SO101_ACTION_DIM])}
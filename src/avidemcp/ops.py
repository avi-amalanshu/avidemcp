"""Decoded-domain edit ops: the vocabulary of render(ops).

Each op is a pydantic model, so render's JSON schema documents itself; graph.link compiles
each one into filtergraph lines. Adding an op = one model here + one link() rule there.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

Sound = Literal["pitch", "tape", "none"]


class Trim(BaseModel):
    """Keep only [start, end) seconds of the current timeline."""

    op: Literal["trim"]
    start: float = Field(0.0, ge=0)
    end: float | None = Field(None, gt=0, description="omit to keep through the end")


class Cut(BaseModel):
    """Remove [start, end) seconds from the current timeline."""

    op: Literal["cut"]
    start: float = Field(ge=0)
    end: float = Field(gt=0)


class Speed(BaseModel):
    """Play `factor` times as fast; factor < 1 is slow motion (frames are repeated)."""

    op: Literal["speed"]
    factor: float = Field(ge=0.01, le=100)
    audio: Sound = Field("pitch", description="pitch: keep pitch; tape: pitch follows speed; none: drop audio")


class Reverse(BaseModel):
    """Play the current timeline backwards (buffers it in RAM, so keep it short)."""

    op: Literal["reverse"]


class Crop(BaseModel):
    """Keep a width x height window of the frame, top-left corner at (x, y) display pixels."""

    op: Literal["crop"]
    width: int = Field(gt=0, multiple_of=2)
    height: int = Field(gt=0, multiple_of=2)
    x: int | None = Field(None, ge=0, description="omit to center horizontally")
    y: int | None = Field(None, ge=0, description="omit to center vertically")


class Scale(BaseModel):
    """Resize the frame to width x height (omit height to keep the aspect ratio)."""

    op: Literal["scale"]
    width: int = Field(gt=0, multiple_of=2)
    height: int | None = Field(None, gt=0, multiple_of=2)


Op = Annotated[Trim | Cut | Speed | Reverse | Crop | Scale, Field(discriminator="op")]

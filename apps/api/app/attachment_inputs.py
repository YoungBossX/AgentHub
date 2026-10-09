"""Private binary inputs: never serialized into request/history evidence."""

import base64
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImageInput(BaseModel):
    model_config = ConfigDict(frozen=True)
    attachment_id: str
    sha256: str
    media_type: str
    data: bytes = Field(exclude=True, repr=False)

    def anthropic_block(self) -> dict:
        return {"type": "image", "source": {"type": "base64", "media_type": self.media_type,
                "data": base64.b64encode(self.data).decode("ascii")}}

    def data_url(self) -> str:
        return f"data:{self.media_type};base64,{base64.b64encode(self.data).decode('ascii')}"


class PlannerPayload(dict):
    def __init__(self, value: dict[str, Any], images: tuple[ImageInput, ...] = ()) -> None:
        super().__init__(value)
        self.images = images


def image_inputs(payload: object) -> tuple[ImageInput, ...]:
    return payload.images if isinstance(payload, PlannerPayload) else ()


def claude_input(prompt: str, images: tuple[ImageInput, ...]) -> str:
    content: list[dict] = [{"type": "text", "text": prompt}]
    for image in images:
        content.extend([{"type": "text", "text": f"Attachment image {image.attachment_id}, normalized SHA-256 {image.sha256}:"}, image.anthropic_block()])
    return json.dumps({"type": "user", "message": {"role": "user", "content": content}}, ensure_ascii=False) + "\n"

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from .chat import (
    MAX_IMAGE_SIZE_MB, MAX_WIDTH, MAX_HEIGHT, SUPPORTED_FORMATS,
    validate_image_data, decode_base64_image
)


class ImageGenerationRequest(BaseModel):
    model: str = Field(default="dall-e-3")
    prompt: str = Field(min_length=1, max_length=4000)
    n: Optional[int] = Field(default=1, ge=1, le=10)
    size: Optional[str] = Field(default="1024x1024", pattern=r'^\d+x\d+$')
    quality: Optional[str] = Field(default="standard", pattern=r'^(standard|hd)$')
    style: Optional[str] = Field(default="vivid", pattern=r'^(vivid|natural)$')
    response_format: Optional[str] = Field(default="url", pattern=r'^(url|b64_json)$')


class ImageData(BaseModel):
    b64_json: Optional[str] = None
    url: Optional[str] = None
    revised_prompt: Optional[str] = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: List[ImageData]


class ImageValidationRequest(BaseModel):
    image_data: str


class ImageUploadResponse(BaseModel):
    success: bool
    message: str
    image_info: Optional[Dict[str, Any]] = None

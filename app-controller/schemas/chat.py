from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Union, Tuple
import os
import re
import base64
import io
from PIL import Image

MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
MAX_WIDTH = 8192
MAX_HEIGHT = 8192
SUPPORTED_FORMATS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}


def validate_image_data(image_data: bytes) -> Dict[str, Any]:
    try:
        image = Image.open(io.BytesIO(image_data))
        width, height = image.size
        format = image.format.lower() if image.format else 'unknown'

        if format not in SUPPORTED_FORMATS:
            return {
                'valid': False,
                'error': f"Unsupported image format: {format}. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
            }

        if width > MAX_WIDTH or height > MAX_HEIGHT:
            return {
                'valid': False,
                'error': f"Image dimensions exceed maximum allowed size. Max: {MAX_WIDTH}x{MAX_HEIGHT}, Got: {width}x{height}"
            }

        return {
            'valid': True,
            'width': width,
            'height': height,
            'format': format,
            'size_bytes': len(image_data)
        }
    except Exception as e:
        return {
            'valid': False,
            'error': f"Invalid image data: {str(e)}"
        }


def decode_base64_image(base64_string: str) -> Optional[bytes]:
    try:
        match = re.match(r'^data:image/([\w-]+);base64,(.+)$', base64_string)
        if match:
            base64_data = match.group(2)
        else:
            base64_data = base64_string

        decoded = base64.b64decode(base64_data)

        if len(decoded) > MAX_IMAGE_SIZE_BYTES:
            return None

        return decoded
    except Exception:
        return None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    stop: Optional[List[str]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    stream_options: Optional[Dict[str, Any]] = None

    @field_validator('messages')
    def validate_messages_with_images(cls, v):
        for message in v:
            if 'content' in message:
                content = message['content']
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and 'image_url' in part:
                            image_url = part['image_url']
                            if isinstance(image_url, dict) and 'url' in image_url:
                                url = image_url['url']
                                if url.startswith('data:image/'):
                                    decoded = decode_base64_image(url)
                                    if decoded is None:
                                        raise ValueError("Invalid or oversized base64 image data")
                                    validation = validate_image_data(decoded)
                                    if not validation['valid']:
                                        raise ValueError(validation['error'])
        return v


class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: Dict[str, str]
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{os.urandom(12).hex()}")
    object: str = "chat.completion"
    created: int = 0
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Optional[Dict[str, int]] = None


class ChatCompletionChunk(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{os.urandom(12).hex()}")
    object: str = "chat.completion.chunk"
    created: int = 0
    model: str
    choices: List[Dict[str, Any]]


MULTIMODAL_MODELS = {
    'gemma-2-vision', 'llava', 'qwen-vl', 'internvl', 'cogvlm',
    'gemma-4-31b-abliterated', 'qwen3-235b-a22b-instruct-2507-awq'
}


def count_image_content(request_data: Dict[str, Any]) -> Tuple[bool, int]:
    has_image = False
    total_size = 0

    if request_data.get('messages'):
        for message in request_data['messages']:
            content = message.get('content')
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get('image_url'):
                        has_image = True
                        image_url = part['image_url']
                        if isinstance(image_url, dict):
                            url = image_url.get('url', '')
                        else:
                            url = str(image_url)
                        if url.startswith('data:image/'):
                            comma_pos = url.find(',')
                            if comma_pos > 0:
                                base64_data = url[comma_pos+1:]
                                total_size += int((len(base64_data) * 3) / 4)
    return has_image, total_size


def is_multimodal_model(model_name: str) -> bool:
    return model_name.lower() in MULTIMODAL_MODELS


MULTIMODAL_MODELS = {
    'gemma-2-vision', 'llava', 'qwen-vl', 'internvl', 'cogvlm',
    'gemma-4-31b-abliterated', 'qwen3-235b-a22b-instruct-2507-awq'
}

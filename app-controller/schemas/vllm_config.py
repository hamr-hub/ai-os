from pydantic import BaseModel, Field
from typing import Optional


class VLLMConfigParams(BaseModel):
    gpu_memory_utilization: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=0.99,
        description="GPU memory utilization (0.1-0.99)"
    )
    max_model_len: Optional[int] = Field(
        default=None,
        ge=512,
        description="Maximum model context length"
    )
    max_num_seqs: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of sequences"
    )
    max_num_batched_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of batched tokens"
    )
    tensor_parallel_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Tensor parallel size for multi-GPU"
    )


class VLLMConfigResponse(BaseModel):
    model_name: str
    gpu_memory_utilization: Optional[float] = None
    max_model_len: Optional[int] = None
    max_num_seqs: Optional[int] = None
    max_num_batched_tokens: Optional[int] = None
    tensor_parallel_size: Optional[int] = None
    has_custom_config: bool = False


class VLLMConfigUpdateRequest(BaseModel):
    gpu_memory_utilization: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=0.99,
        description="GPU memory utilization (0.1-0.99)"
    )
    max_model_len: Optional[int] = Field(
        default=None,
        ge=512,
        description="Maximum model context length"
    )
    max_num_seqs: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of sequences"
    )
    max_num_batched_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of batched tokens"
    )
    tensor_parallel_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Tensor parallel size for multi-GPU"
    )
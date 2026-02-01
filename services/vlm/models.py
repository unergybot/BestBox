"""
Pydantic models for VLM API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from datetime import datetime


class JobStatus(str, Enum):
    """VLM job status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisDepth(str, Enum):
    """Analysis depth levels"""
    QUICK = "quick"
    STANDARD = "standard"
    DETAILED = "detailed"


class VLMJobOptions(BaseModel):
    """Options for VLM job submission"""
    extract_images: bool = True
    analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD
    output_language: str = "zh"
    max_tokens: int = 1024
    include_ocr: bool = True


class VLMJobResponse(BaseModel):
    """Response from job submission"""
    job_id: str
    status: JobStatus
    estimated_duration: Optional[str] = None
    check_status_url: Optional[str] = None
    submitted_at: datetime


class BoundingBox(BaseModel):
    """Bounding box for detected regions"""
    x: int
    y: int
    width: int
    height: int


class ExtractedImage(BaseModel):
    """VLM-extracted image information"""
    image_id: str
    page: int = 1
    description: str
    insights: Optional[str] = None
    defect_type: Optional[str] = None
    bounding_box: Optional[BoundingBox] = None
    confidence: float = 0.0


class EntityInfo(BaseModel):
    """Entity information from VLM analysis"""
    name: str
    type: Optional[str] = None
    mentions: Optional[int] = None

    class Config:
        extra = "allow"


class VLMAnalysis(BaseModel):
    """Analysis results from VLM"""
    sentiment: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    entities: List[Any] = Field(default_factory=list)  # Can be strings or EntityInfo objects
    complexity_score: float = 0.0

    class Config:
        extra = "allow"


class VLMMetadata(BaseModel):
    """Metadata about VLM processing"""
    confidence_score: float = 0.0
    processing_model: str = "Qwen3-VL-8B"
    tokens_used: int = 0
    processing_time_ms: int = 0


class VLMResult(BaseModel):
    """Complete VLM analysis result"""
    job_id: Optional[str] = None
    document_summary: str = ""

    class Config:
        extra = "allow"  # Allow extra fields from API response
    key_insights: List[str] = Field(default_factory=list)
    analysis: VLMAnalysis = Field(default_factory=VLMAnalysis)
    extracted_images: List[ExtractedImage] = Field(default_factory=list)
    text_content: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: VLMMetadata = Field(default_factory=VLMMetadata)

    # Mold-specific fields (from mold_defect_analysis template)
    defect_type: Optional[str] = None
    defect_details: Optional[str] = None
    equipment_part: Optional[str] = None
    text_in_image: Optional[str] = None
    visual_annotations: Optional[str] = None
    severity: Optional[str] = None
    root_cause_hints: List[str] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)


class VLMJobStatusResponse(BaseModel):
    """Response from job status check"""
    job_id: str
    status: JobStatus
    progress: Optional[float] = None
    estimated_remaining: Optional[str] = None
    result: Optional[VLMResult] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


class VLMHealthStatus(BaseModel):
    """VLM service health status"""
    status: str
    model: str = "Qwen3-VL-8B"
    version: str = "1.0.0"
    gpu_memory_used: Optional[str] = None
    gpu_memory_total: Optional[str] = None
    queue_depth: int = 0
    average_processing_time_ms: int = 0


class VLMWebhookPayload(BaseModel):
    """Payload received from VLM webhook callback"""
    event: str  # e.g., "job.completed"
    job_id: str
    status: JobStatus
    result: Optional[VLMResult] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


class VLMError(BaseModel):
    """VLM error response"""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ImageComparisonResult(BaseModel):
    """Result from image comparison API"""
    image_index: int
    filename: Optional[str] = None
    similarity_score: float
    matching_defects: List[str] = Field(default_factory=list)
    matching_regions: List[Dict[str, Any]] = Field(default_factory=list)
    differences: List[str] = Field(default_factory=list)


class VLMCompareResult(BaseModel):
    """Complete result from defect comparison"""
    job_id: str
    status: JobStatus
    reference_analysis: Optional[Dict[str, Any]] = None
    similarities: List[ImageComparisonResult] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class BatchJobResult(BaseModel):
    """Result for a single file in batch processing"""
    file_index: int
    filename: Optional[str] = None
    analysis: Optional[VLMResult] = None
    error: Optional[str] = None


class VLMBatchResult(BaseModel):
    """Complete batch processing result"""
    batch_job_id: str
    status: JobStatus
    results: List[BatchJobResult] = Field(default_factory=list)
    cross_reference: Optional[Dict[str, Any]] = None

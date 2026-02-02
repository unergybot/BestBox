"""
Document Analysis Tools for VLM Integration

Tools for analyzing images and documents in real-time during chat,
and for batch knowledge base enrichment.

Usage:
    from tools.document_tools import (
        analyze_image_realtime,
        analyze_document_realtime,
        compare_images
    )
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from langchain_core.tools import tool
from typing import Optional, List
import json
import logging
import tempfile
from typing import Optional, List, Union
from PIL import Image as PILImage


logger = logging.getLogger(__name__)

# Try importing VLM components
try:
    from services.vlm import VLMServiceClient, VLMResult
    from services.vlm.models import VLMJobOptions, AnalysisDepth
    VLM_AVAILABLE = True
except ImportError:
    VLM_AVAILABLE = False
    logger.warning("VLM service client not available")

# Try importing PDF tools
try:
    from pdf2image import convert_from_path
    PDF_TOOLS_AVAILABLE = True
except ImportError:
    PDF_TOOLS_AVAILABLE = False
    logger.warning("pdf2image not available")



def _get_vlm_client() -> "VLMServiceClient":
    """Get configured VLM client"""
    if not VLM_AVAILABLE:
        raise RuntimeError("VLM service not available. Install with: pip install httpx")
    return VLMServiceClient()


def _run_async(coro):
    """Run async coroutine in sync context"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in async context, create task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result(timeout=180)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@tool
def analyze_image_realtime(
    image_path: str,
    analysis_prompt: str = "分析此图像中的缺陷和设备问题"
) -> str:
    """
    实时分析图像（用于聊天对话）。
    Analyze image in real-time for chat conversation.

    Use this tool when users share images of defects or equipment issues
    during conversation. The VLM will analyze the image and extract:
    - Defect types and descriptions
    - Equipment parts visible
    - Text/annotations in the image
    - Severity assessment
    - Suggested corrective actions

    Results typically take 15-30 seconds.

    Args:
        image_path: 图像文件路径 / Path to image file
            Can be a path from file upload or local file
        analysis_prompt: 分析提示 / Analysis prompt (optional)
            Customize what to focus on in the analysis

    Returns:
        JSON string with detailed image analysis including:
        - defect_type: Primary defect category
        - defect_details: Detailed description
        - severity: high/medium/low
        - suggested_actions: Corrective actions
        - key_insights: Important observations

    Examples:
        - analyze_image_realtime("/path/to/defect.jpg")
        - analyze_image_realtime(image_path, "检查表面划痕")
    """
    if not VLM_AVAILABLE:
        return json.dumps({
            "error": "VLM service not available",
            "message": "图像分析服务不可用"
        }, ensure_ascii=False)

    try:
        image_path = Path(image_path)
        if not image_path.exists():
            return json.dumps({
                "error": f"Image not found: {image_path}",
                "message": f"图像文件未找到: {image_path}"
            }, ensure_ascii=False)

        logger.info(f"Analyzing image: {image_path}")

        async def _analyze():
            client = _get_vlm_client()
            try:
                options = VLMJobOptions(
                    analysis_depth=AnalysisDepth.DETAILED,
                    output_language="zh",
                    include_ocr=True
                )

                result = await client.analyze_file(
                    image_path,
                    prompt_template="mold_defect_analysis",
                    options=options,
                    timeout=120
                )

                return {
                    "status": "success",
                    "image_path": str(image_path),
                    "analysis": {
                        "defect_type": result.defect_type or "未检测到明确缺陷",
                        "defect_details": result.defect_details or result.document_summary,
                        "equipment_part": result.equipment_part,
                        "text_in_image": result.text_in_image,
                        "visual_annotations": result.visual_annotations,
                        "severity": result.severity or "unknown",
                        "key_insights": result.key_insights,
                        "suggested_actions": result.suggested_actions,
                        "tags": result.tags,
                        "confidence": result.metadata.confidence_score
                    }
                }
            finally:
                await client.close()

        result = _run_async(_analyze())
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Image analysis failed: {e}")
        return json.dumps({
            "error": str(e),
            "message": f"图像分析失败: {e}"
        }, ensure_ascii=False)



def _convert_document_to_images(file_path: Path, max_pages: int = 3) -> List[Path]:
    """Convert document (PDF/Excel) to list of image paths"""
    images = []
    suffix = file_path.suffix.lower()
    
    if suffix == '.pdf':
        if not PDF_TOOLS_AVAILABLE:
            raise RuntimeError("PDF tools not available (pip install pdf2image)")
            
        with tempfile.TemporaryDirectory() as temp_dir:
            # Convert first few pages
            pil_images = convert_from_path(str(file_path), first_page=1, last_page=max_pages)
            
            for i, img in enumerate(pil_images):
                img_path = file_path.parent / f"{file_path.stem}_page{i+1}.jpg"
                img.save(img_path, 'JPEG')
                images.append(img_path)
                
    elif suffix in ['.xlsx', '.xls']:
        # For Excel, we use the existing extractor logic to extract embedded images
        # Or simplistic approach: just fail if no images?
        # Better: Tell user we extracted images if any, otherwise VLM can't "read" the grid visually easily.
        # However, we can try to extract images using openpyxl directly here or reuse Extractor.
        # Reusing Extractor is safer but circular import risk if tools -> services -> tools.
        # Let's import inside function.
        try:
            from services.troubleshooting.excel_extractor import ExcelTroubleshootingExtractor
            # Create a temp dir for extraction
            # But we want to return paths.
            # Let's just use the extractor to get images to a temp folder adjacent to file
            output_dir = file_path.parent / f"{file_path.stem}_extracted"
            output_dir.mkdir(exist_ok=True)
            
            extractor = ExcelTroubleshootingExtractor(output_dir=output_dir)
            # We don't want full case extraction, just images usually.
            # But extract_case processes everything.
            # Let's assume we extract images and pick the first few.
            # This is heavy. Alternatively, just text analysis?
            # VLM tool implies "Visual".
            # Let's extract images from Excel as "visuals" to analyze.
            case = extractor.extract_case(file_path)
            
            # Find extracted images
            for issue in case.get('issues', []):
                for img_data in issue.get('images', []):
                    # These paths are relative or absolute? Extractor saves them.
                    # issue['images'] usually has 'path' or similar if we modify extractor.
                    # Looking at extractor code: it saves images to `output_dir / images`.
                    pass
            
            # Extractor `_extract_images` saves to `self.images_dir`.
            # `extract_case` sets `self.images_dir`.
            # So looking into `output_dir / "images"`
            img_dir = output_dir / "images"
            if img_dir.exists():
                images = list(img_dir.glob("*.jpg")) + list(img_dir.glob("*.png"))
                images = sorted(images)[:max_pages] # Limit count
            
        except ImportError:
            logger.warning("Excel extractor not available")
    
    return images


@tool
def analyze_document_realtime(
    file_path: str,
    focus_areas: Optional[str] = None
) -> str:
    """
    实时分析文档（用于聊天对话）。
    Analyze document in real-time for chat conversation.

    Use this tool when users share PDF or Excel files during conversation.
    The VLM will extract and analyze:
    - Document summary
    - Key insights and findings
    - Embedded images and their analysis
    - Topics and entities mentioned
    - Relevant tags

    Results typically take 30-60 seconds depending on document size.

    Args:
        file_path: 文档文件路径 / Path to document file
            Supports: PDF, Excel (.xlsx), images
        focus_areas: 关注领域 / Comma-separated focus areas (optional)
            Examples: "披锋,表面质量" or "mold defects,surface quality"

    Returns:
        JSON string with document analysis including:
        - summary: Document summary
        - key_insights: Important findings
        - extracted_images: Analysis of images in document
        - topics: Main topics covered
        - recommendations: Suggested actions

    Examples:
        - analyze_document_realtime("/path/to/report.pdf")
        - analyze_document_realtime(file_path, "模具问题,缺陷分析")
    """
    if not VLM_AVAILABLE:
        return json.dumps({
            "error": "VLM service not available",
            "message": "文档分析服务不可用"
        }, ensure_ascii=False)

    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return json.dumps({
                "error": f"Document not found: {file_path}",
                "message": f"文档文件未找到: {file_path}"
            }, ensure_ascii=False)

        logger.info(f"Analyzing document: {file_path}")

        # Check if conversion is needed
        suffix = file_path.suffix.lower()
        converted_images = []
        
        async def _analyze():
            client = _get_vlm_client()
            try:
                # Handle Non-Image Files
                target_file = file_path
                analysis_mode = "document" # or "images"
                
                if suffix in ['.pdf', '.xlsx', '.xls']:
                    try:
                        # Convert to images
                        images = await asyncio.to_thread(_convert_document_to_images, file_path)
                        if not images:
                            return {
                                "status": "failed",
                                "message": "无法从文档中提取图像或内容 (Could not extract images/content)"
                            }
                        
                        # Analyze the first image as the "document" (e.g. first page of PDF)
                        # OR submit multiple? VLM analyze_file takes one path.
                        # We'll analyze the first converted image.
                        target_file = images[0]
                        converted_images.extend(images) # Keep track to clean up? Or keep?
                        analysis_mode = "converted_document"
                        
                    except Exception as conv_err:
                        return {
                            "status": "failed",
                            "error": str(conv_err),
                            "message": f"文档转换失败: {conv_err}"
                        }

                options = VLMJobOptions(
                    analysis_depth=AnalysisDepth.DETAILED,
                    output_language="zh",
                    include_ocr=True,
                    extract_images=True
                )

                result = await client.analyze_file(
                    target_file,
                    prompt_template="mold_defect_analysis",
                    options=options,
                    timeout=180  # Longer timeout for documents
                )

                # Format extracted images
                extracted_images = []
                for img in result.extracted_images:
                    extracted_images.append({
                        "image_id": img.image_id,
                        "page": img.page,
                        "description": img.description,
                        "defect_type": img.defect_type,
                        "insights": img.insights
                    })

                return {
                    "status": "success",
                    "file_path": str(file_path),
                    "original_type": suffix,
                    "analysis": {
                        "summary": result.document_summary,
                        "key_insights": result.key_insights,
                        "extracted_images": extracted_images,
                        "topics": result.analysis.topics if result.analysis else [],
                        "entities": result.analysis.entities if result.analysis else [],
                        "tags": result.tags,
                        "suggested_actions": result.suggested_actions,
                        "confidence": result.metadata.confidence_score
                    }
                }
            finally:
                await client.close()
                # Cleanup converted images? Maybe keep them for user inspection?
                # For chat, we might want to keep the one we analyzed.

        result = _run_async(_analyze())
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Document analysis failed: {e}")
        return json.dumps({
            "error": str(e),
            "message": f"文档分析失败: {e}"
        }, ensure_ascii=False)


@tool
def compare_images(
    reference_image: str,
    comparison_images: str,
    comparison_type: str = "defect_similarity"
) -> str:
    """
    比较多张图像识别相似缺陷模式。
    Compare multiple images to identify similar defect patterns.

    Use this tool to correlate new issues with known cases by comparing:
    - Defect similarity between images
    - Common defect patterns
    - Equipment/mold part matching
    - Visual similarity

    This helps identify if a new issue matches previously solved problems.

    Args:
        reference_image: 参考图像路径 / Path to reference image (the new/unknown defect)
        comparison_images: 对比图像路径 / Comma-separated paths to comparison images
            These should be images from known cases for correlation
        comparison_type: 比较类型 / Type of comparison
            Options: "defect_similarity", "equipment_match", "visual_similarity"

    Returns:
        JSON string with comparison results including:
        - similarities: Similarity scores and matching defects for each image
        - recommendations: Suggested actions based on similar cases

    Examples:
        - compare_images("/new/defect.jpg", "/case1/img.jpg,/case2/img.jpg")
        - compare_images(ref_img, comp_imgs, "defect_similarity")
    """
    if not VLM_AVAILABLE:
        return json.dumps({
            "error": "VLM service not available",
            "message": "图像比较服务不可用"
        }, ensure_ascii=False)

    try:
        reference_path = Path(reference_image)
        if not reference_path.exists():
            return json.dumps({
                "error": f"Reference image not found: {reference_image}",
                "message": f"参考图像未找到: {reference_image}"
            }, ensure_ascii=False)

        # Parse comparison images (comma-separated)
        comparison_paths = [
            Path(p.strip())
            for p in comparison_images.split(',')
            if p.strip()
        ]

        # Validate comparison images exist
        for path in comparison_paths:
            if not path.exists():
                return json.dumps({
                    "error": f"Comparison image not found: {path}",
                    "message": f"对比图像未找到: {path}"
                }, ensure_ascii=False)

        if not comparison_paths:
            return json.dumps({
                "error": "No comparison images provided",
                "message": "未提供对比图像"
            }, ensure_ascii=False)

        logger.info(f"Comparing {reference_path} with {len(comparison_paths)} images")

        async def _compare():
            client = _get_vlm_client()
            try:
                result = await client.compare_images(
                    reference_path,
                    comparison_paths,
                    comparison_type,
                    timeout=180
                )

                return {
                    "status": "success",
                    "reference_image": str(reference_path),
                    "comparison_count": len(comparison_paths),
                    "comparison_type": comparison_type,
                    "reference_analysis": result.reference_analysis,
                    "similarities": [
                        {
                            "image_path": str(comparison_paths[s.image_index]),
                            "similarity_score": s.similarity_score,
                            "matching_defects": s.matching_defects,
                            "differences": s.differences
                        }
                        for s in result.similarities
                    ],
                    "recommendations": result.recommendations
                }
            finally:
                await client.close()

        result = _run_async(_compare())
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Image comparison failed: {e}")
        return json.dumps({
            "error": str(e),
            "message": f"图像比较失败: {e}"
        }, ensure_ascii=False)


@tool
def upload_and_analyze_document(
    file_path: str,
    document_type: str = "auto",
    analysis_depth: str = "detailed"
) -> str:
    """
    上传文档并通过VLM进行分析（用于知识库索引）。
    Upload document for VLM analysis (for knowledge base indexing).

    This is a batch operation tool for enriching the knowledge base.
    For real-time chat analysis, use analyze_document_realtime instead.

    Args:
        file_path: 文档文件路径 / Path to document file
        document_type: 文档类型 / Document type (auto, pdf, excel, image)
        analysis_depth: 分析深度 / Analysis depth (quick, standard, detailed)

    Returns:
        JSON string with job_id for tracking the analysis
    """
    if not VLM_AVAILABLE:
        return json.dumps({
            "error": "VLM service not available",
            "message": "VLM服务不可用"
        }, ensure_ascii=False)

    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return json.dumps({
                "error": f"File not found: {file_path}",
                "message": f"文件未找到: {file_path}"
            }, ensure_ascii=False)

        logger.info(f"Submitting document for analysis: {file_path}")

        async def _submit():
            client = _get_vlm_client()
            try:
                depth_map = {
                    "quick": AnalysisDepth.QUICK,
                    "standard": AnalysisDepth.STANDARD,
                    "detailed": AnalysisDepth.DETAILED
                }
                options = VLMJobOptions(
                    analysis_depth=depth_map.get(analysis_depth, AnalysisDepth.DETAILED),
                    output_language="zh",
                    include_ocr=True,
                    extract_images=True
                )

                job = await client.submit_file(
                    file_path,
                    prompt_template="mold_defect_analysis",
                    options=options
                )

                return {
                    "status": "submitted",
                    "job_id": job.job_id,
                    "file_path": str(file_path),
                    "estimated_duration": job.estimated_duration,
                    "message": f"文档已提交分析，作业ID: {job.job_id}"
                }
            finally:
                await client.close()

        result = _run_async(_submit())
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Document submission failed: {e}")
        return json.dumps({
            "error": str(e),
            "message": f"文档提交失败: {e}"
        }, ensure_ascii=False)


@tool
def get_document_analysis(job_id: str) -> str:
    """
    获取文档分析结果。
    Get document analysis results.

    Use this to check the status of a previously submitted analysis job.

    Args:
        job_id: 作业ID / Job ID from upload_and_analyze_document

    Returns:
        JSON string with analysis results or status
    """
    if not VLM_AVAILABLE:
        return json.dumps({
            "error": "VLM service not available",
            "message": "VLM服务不可用"
        }, ensure_ascii=False)

    try:
        logger.info(f"Getting analysis results for job: {job_id}")

        async def _get_result():
            client = _get_vlm_client()
            try:
                status = await client.get_job_status(job_id)

                if status.status.value == "completed" and status.result:
                    result = status.result
                    return {
                        "status": "completed",
                        "job_id": job_id,
                        "analysis": {
                            "summary": result.document_summary,
                            "key_insights": result.key_insights,
                            "defect_type": result.defect_type,
                            "severity": result.severity,
                            "suggested_actions": result.suggested_actions,
                            "tags": result.tags,
                            "confidence": result.metadata.confidence_score
                        }
                    }
                elif status.status.value == "failed":
                    return {
                        "status": "failed",
                        "job_id": job_id,
                        "error": status.error or "Unknown error"
                    }
                else:
                    return {
                        "status": status.status.value,
                        "job_id": job_id,
                        "progress": status.progress,
                        "estimated_remaining": status.estimated_remaining,
                        "message": "分析进行中..."
                    }
            finally:
                await client.close()

        result = _run_async(_get_result())
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Failed to get analysis results: {e}")
        return json.dumps({
            "error": str(e),
            "message": f"获取分析结果失败: {e}"
        }, ensure_ascii=False)


# Export tools list for easy import
document_tools = [
    analyze_image_realtime,
    analyze_document_realtime,
    compare_images,
    upload_and_analyze_document,
    get_document_analysis
]

# Real-time analysis tools (for mold agent)
realtime_analysis_tools = [
    analyze_image_realtime,
    analyze_document_realtime,
    compare_images
]


if __name__ == "__main__":
    # Test tools
    print("Testing Document Analysis Tools")
    print("=" * 70)
    print()

    # Check VLM availability
    print(f"VLM Available: {VLM_AVAILABLE}")

    if VLM_AVAILABLE:
        print("\nTesting VLM client health check...")
        try:
            client = _get_vlm_client()
            result = _run_async(client.is_available())
            print(f"VLM Service Available: {result}")
            _run_async(client.close())
        except Exception as e:
            print(f"Health check failed: {e}")

    print("\n✅ Document tools test complete")

"""
Processor: OCR 画面文字识别

优化版策略：

支持四种 OCR_METHOD：

1. fast_hybrid（推荐默认）
   - 先用 image hash 对关键帧做视觉去重
   - 限制最多送 OCR 的帧数
   - 对代表帧调用 Doubao batch OCR
   - batch 之间并发
   - 被跳过的帧复用代表帧结果
   - 速度最快，中文效果较好，适合 demo 和主流程

2. hybrid（保留原方案）
   - 先用 Tesseract 快速扫描所有关键帧
   - 相邻帧文字相似的去重
   - 去重后的帧送 Doubao
   - 被跳过的帧复用前一帧结果
   - 准确但 Tesseract 前置较慢

3. llm
   - 所有关键帧全部送 Doubao
   - 最准但最慢

4. tesseract
   - 所有关键帧全部用本地 Tesseract
   - 最快但中文效果一般

推荐 .env：
OCR_METHOD=rapid_then_doubao
RAPID_OCR_MIN_CONF=0.45
RAPID_FALLBACK_ON_EMPTY=false
OCR_WATERMARK_MIN_RATIO=0.35
OCR_WATERMARK_MIN_COUNT=5
DOUBAO_FALLBACK_MAX_FRAMES=12
RAPID_FALLBACK_ON_TITLE_FRAME=true
"""

from __future__ import annotations

import os
# from concurrent.futures import ThreadPoolExecutor, as_completed

from src.stage1.utils.file_utils import write_json
from src.stage1.utils.logger import get_logger

logger = get_logger(__name__)


def run(input_path: str, output_dir: str, context: dict) -> dict:
    """
    OCR processor 入口。

    input_path:
        原视频路径，这里不直接使用，保留统一 processor 接口。

    output_dir:
        当前 video_id 的输出目录。

    context:
        需要包含：
        - keyframes
        - metadata

    返回:
        {"ocr_results": list[dict]}
    """
    keyframes = context.get("keyframes", [])
    if isinstance(keyframes, dict):
        keyframes = keyframes.get("keyframes", [])

    if not keyframes:
        write_json(os.path.join(output_dir, "ocr.json"), [])
        return {"ocr_results": []}

    metadata = context.get("metadata") or {}
    width = int(metadata.get("width", 1) or 1)
    height = int(metadata.get("height", 1) or 1)

    method = os.getenv("OCR_METHOD", "rapid_then_doubao").lower().strip()


    if method == "rapid":
        ocr_results = _run_rapid_ocr(keyframes, width, height, fallback_to_doubao=False)
    elif method == "rapid_then_doubao":
        ocr_results = _run_rapid_ocr(keyframes, width, height, fallback_to_doubao=True)
    elif method == "fast_hybrid":
        ocr_results = _run_fast_hybrid_ocr(keyframes, width, height)
    elif method == "llm" or method == "doubao":
        ocr_results = _run_doubao_ocr(keyframes, width, height)
    else:
        ocr_results = _run_fast_hybrid_ocr(keyframes, width, height)

    ocr_results = _filter_watermarks(ocr_results)
    ocr_results = _merge_consecutive_duplicates(ocr_results)
    ocr_results = _add_display_texts(ocr_results)

    write_json(os.path.join(output_dir, "ocr.json"), ocr_results)
    return {"ocr_results": ocr_results}

# ============================================================
# Rapid 模式：推荐默认
# ============================================================


def _run_rapid_ocr(
    keyframes: list[dict],
    width: int,
    height: int,
    fallback_to_doubao: bool = True,
) -> list[dict]:
    """
    RapidOCR 主流程。

    优点：
    - 本地 OCR，速度快
    - 有真实 bbox
    - 不会像多模态 batch 那样串图

    fallback_to_doubao:
    - True: RapidOCR 结果质量差时，用 Doubao 单图兜底
    - False: 只用 RapidOCR
    """
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "rapidocr-onnxruntime is not installed. Run: "
            "pip install rapidocr-onnxruntime onnxruntime"
        ) from exc

    engine = RapidOCR()

    ocr_results: list[dict] = []
    fallback_count = 0
    fallback_max_frames = int(os.getenv("DOUBAO_FALLBACK_MAX_FRAMES", "12"))

    for idx, frame in enumerate(keyframes):
        fid = frame["frame_id"]
        frame_path = frame.get("path")

        if not frame_path or not os.path.exists(frame_path):
            ocr_results.append({
                "frame_id": fid,
                "timestamp": frame.get("timestamp", 0.0),
                "texts": [],
                "ocr_source": "rapid",
                "ocr_source_frame_id": None,
                "ocr_reused": False,
                "ocr_skipped_reason": "missing_frame_file",
            })
            continue

        logger.info("RapidOCR: %s (%d/%d)", fid, idx + 1, len(keyframes))

        try:
            raw_result = engine(frame_path)
            result = _unwrap_rapidocr_result(raw_result)
            texts = _parse_rapidocr_result(result, width, height)
        except Exception as exc:
            logger.warning("RapidOCR failed for %s: %s", fid, exc)
            texts = []

        should_fallback, fallback_reason = _should_fallback_to_doubao(
            texts=texts,
            frame=frame,
            frame_index=idx,
        )

        if fallback_to_doubao and should_fallback and (fallback_max_frames <= 0 or fallback_count < fallback_max_frames):
            logger.info(
                "RapidOCR fallback to Doubao: %s reason=%s (%d/%d)",
                fid,
                fallback_reason,
                fallback_count + 1,
                fallback_max_frames,
            )

            rapid_texts = texts
            doubao_texts = _run_doubao_single_frame(frame, width, height)

            # Doubao 兜底失败时，不要用空结果覆盖 RapidOCR 结果。
            if doubao_texts:
                texts = doubao_texts
                ocr_source = "doubao_fallback"
                fallback_count += 1
            else:
                texts = rapid_texts
                ocr_source = "rapid_fallback_failed"
        else:
            ocr_source = "rapid"
            if fallback_to_doubao and should_fallback:
                logger.info(
                    "Skip Doubao fallback for %s because fallback budget is used up. reason=%s",
                    fid,
                    fallback_reason,
                )

        ocr_results.append({
            "frame_id": fid,
            "timestamp": frame.get("timestamp", 0.0),
            "texts": texts,
            "ocr_source": ocr_source,
            "ocr_fallback_reason": fallback_reason if fallback_to_doubao and should_fallback else None,
            "ocr_source_frame_id": fid,
            "ocr_reused": False,
        })

    return ocr_results


def _unwrap_rapidocr_result(raw_result):
    """
    兼容不同版本 RapidOCR 的返回格式。

    常见格式：
    - (result, elapse)
    - (result, elapse, something)
    - result
    """
    if isinstance(raw_result, tuple):
        return raw_result[0] if raw_result else []
    return raw_result


def _parse_rapidocr_result(
    result,
    width: int,
    height: int,
) -> list[dict]:
    texts: list[dict] = []

    if not result:
        return texts

    for item in result:
        try:
            box = item[0]
            content = str(item[1]).strip()
            confidence = float(item[2])
        except Exception:
            continue

        if not content:
            continue

        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]

        x1 = int(max(0, min(xs)))
        y1 = int(max(0, min(ys)))
        x2 = int(min(width, max(xs)))
        y2 = int(min(height, max(ys)))

        bbox = [x1, y1, x2, y2]

        texts.append({
            "content": content,
            "bbox": bbox,
            "normalized_bbox": _normalize_bbox(bbox, width, height),
            "confidence": round(confidence, 4),
            "text_type": "rapidocr",
        })

    return texts

def _should_fallback_to_doubao(
    texts: list[dict],
    frame: dict | None = None,
    frame_index: int | None = None,
) -> tuple[bool, str | None]:
    """
    判断 RapidOCR 是否需要 Doubao 兜底。

    这里不再使用针对某条测试视频的错词硬编码。
    只使用通用 OCR 质量信号：
    - 平均置信度
    - 文本是否为空
    - 文本是否乱码
    - 中文结果是否过度碎片化
    - bbox 是否异常重叠
    - 标题/开头 hook 页是否高价值
    - 综合 OCR quality score
    """
    if not texts:
        if os.getenv("RAPID_FALLBACK_ON_EMPTY", "false").lower().strip() == "true":
            return True, "empty_result"
        return False, None

    confidences = [float(t.get("confidence", 0.0) or 0.0) for t in texts]
    avg_conf = sum(confidences) / max(len(confidences), 1)
    min_conf = float(os.getenv("RAPID_OCR_MIN_CONF", "0.55"))

    if avg_conf < min_conf:
        return True, f"low_avg_conf:{avg_conf:.3f}"

    joined = "".join(t.get("content", "") for t in texts).strip()
    normalized = _normalize_ocr_quality_text(joined)

    if len(normalized) <= 1:
        return True, "too_short"

    if _looks_like_ocr_garbage(joined):
        return True, "ocr_garbage"

    if _is_probable_title_or_hook_frame(texts, frame, frame_index):
        return True, "title_or_hook_frame"

    if _is_fragmented_chinese_result(texts):
        return True, "fragmented_chinese"

    if os.getenv("RAPID_FALLBACK_ON_LOW_QUALITY", "true").lower().strip() == "true":
        score, reasons = _score_rapid_ocr_quality(texts)
        min_score = float(os.getenv("RAPID_OCR_MIN_QUALITY_SCORE", "0.42"))
        if score < min_score:
            reason = "+".join(reasons) if reasons else "low_quality_score"
            return True, f"low_quality_score:{score:.3f}:{reason}"

    return False, None


def _normalize_ocr_quality_text(text: str) -> str:
    """用于 OCR 质量判断的轻量文本归一化。"""
    if not text:
        return ""
    text = text.lower().strip()
    for ch in [" ", "\n", "\t", "，", ",", "。", ".", "：", ":", "、", "!", "！", "?", "？"]:
        text = text.replace(ch, "")
    return text


def _score_rapid_ocr_quality(texts: list[dict]) -> tuple[float, list[str]]:
    """
    给 RapidOCR 结果一个通用质量分，不依赖具体错词表。

    分数越低，越应该用 Doubao 兜底。
    这不是最终字幕质量评估，只是控制 fallback 成本的启发式指标。
    """
    if not texts:
        return 0.0, ["empty"]

    contents = [str(t.get("content", "")).strip() for t in texts if str(t.get("content", "")).strip()]
    joined = "".join(contents)
    if not joined:
        return 0.0, ["empty_text"]

    total_chars = len(joined)
    chinese_count = sum(1 for ch in joined if "\u4e00" <= ch <= "\u9fff")
    alnum_count = sum(1 for ch in joined if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    symbol_count = max(total_chars - alnum_count, 0)

    avg_conf = sum(float(t.get("confidence", 0.0) or 0.0) for t in texts) / max(len(texts), 1)
    valid_char_ratio = alnum_count / max(total_chars, 1)
    symbol_ratio = symbol_count / max(total_chars, 1)
    short_block_ratio = sum(1 for c in contents if len(c) <= 2) / max(len(contents), 1)
    avg_block_len = total_chars / max(len(contents), 1)
    overlap_ratio = _bbox_overlap_ratio(texts)

    score = 0.0
    reasons: list[str] = []

    # confidence 是最主要信号，但不能单独决定，因为 OCR 可能高置信错识别。
    score += max(0.0, min(1.0, avg_conf)) * 0.42

    # 合法字符占比高说明不像乱码。
    score += max(0.0, min(1.0, valid_char_ratio)) * 0.20

    # 文本长度太短时不稳定；但不要惩罚 BGM、CTA、X3 这类短标签太多。
    length_score = min(total_chars / 8.0, 1.0)
    if total_chars <= 3 and len(texts) <= 1:
        length_score = max(length_score, 0.55)
    score += length_score * 0.15

    # 中文 OCR 常见问题是被切成很多单字/双字碎片。
    fragmentation_penalty = 0.0
    if len(texts) >= 3 and short_block_ratio >= 0.70 and chinese_count >= 3:
        fragmentation_penalty += 0.18
        reasons.append("fragmented_blocks")
    if len(texts) >= 2 and avg_block_len < 2.2 and chinese_count >= 4:
        fragmentation_penalty += 0.10
        reasons.append("short_avg_block")

    # 符号过多通常是乱码或检测框异常。
    symbol_penalty = 0.0
    if symbol_ratio > 0.35:
        symbol_penalty += 0.16
        reasons.append("many_symbols")

    # bbox 大量重叠通常说明检测/解析不稳定。
    overlap_penalty = 0.0
    if overlap_ratio > 0.35:
        overlap_penalty += 0.12
        reasons.append("overlap_boxes")

    score -= fragmentation_penalty + symbol_penalty + overlap_penalty
    score = max(0.0, min(1.0, score))

    if avg_conf < 0.60:
        reasons.append("mid_low_conf")
    if valid_char_ratio < 0.70:
        reasons.append("low_valid_char_ratio")

    return score, reasons


def _bbox_overlap_ratio(texts: list[dict]) -> float:
    """计算 OCR 文本框的平均重叠程度，用于发现异常 bbox。"""
    boxes = []
    for t in texts:
        bbox = t.get("bbox") or []
        if len(bbox) != 4:
            continue
        try:
            x1, y1, x2, y2 = [float(v) for v in bbox]
        except Exception:
            continue
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append((x1, y1, x2, y2))

    if len(boxes) < 2:
        return 0.0

    overlaps = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            overlaps.append(_bbox_iou(boxes[i], boxes[j]))

    if not overlaps:
        return 0.0
    return sum(1 for x in overlaps if x > 0.25) / len(overlaps)


def _bbox_iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _is_probable_title_or_hook_frame(
    texts: list[dict],
    frame: dict | None,
    frame_index: int | None,
) -> bool:
    """
    标题/开头 hook 页对 Stage 2 很重要，RapidOCR 容易漏“2/你”等关键字。
    默认只对前 3 秒或前 3 帧里的多文本块页面做 Doubao 兜底。
    """
    if os.getenv("RAPID_FALLBACK_ON_TITLE_FRAME", "true").lower().strip() != "true":
        return False

    timestamp = float((frame or {}).get("timestamp", 999999.0) or 999999.0)
    index = frame_index if frame_index is not None else 999999
    early = timestamp <= float(os.getenv("RAPID_TITLE_FRAME_MAX_TIME", "3.0")) or index <= int(os.getenv("RAPID_TITLE_FRAME_MAX_INDEX", "2"))
    if not early:
        return False

    joined = "".join(t.get("content", "") for t in texts).strip()
    chinese_count = sum(1 for ch in joined if "\u4e00" <= ch <= "\u9fff")
    return len(texts) >= 2 and chinese_count >= 6


def _is_fragmented_chinese_result(texts: list[dict]) -> bool:
    """
    识别结果很碎时让 Doubao 兜底。
    但保留“鼓点X3 / BGM / CTA”等短标签，不要过度触发。
    """
    joined = "".join(t.get("content", "") for t in texts).strip()
    chinese_count = sum(1 for ch in joined if "\u4e00" <= ch <= "\u9fff")
    alpha_digit_count = sum(1 for ch in joined if ch.isalpha() or ch.isdigit())

    if chinese_count == 0:
        return False

    # 单个短标签通常是有效结构提示，不兜底，例如“鼓点X3”“BGM”。
    if len(texts) <= 1 and alpha_digit_count > 0:
        return False

    # 多个很短中文碎片，常见于 RapidOCR 漏识别/切碎。
    short_blocks = [t for t in texts if len(t.get("content", "").strip()) <= 2]
    if len(texts) >= 2 and len(short_blocks) / max(len(texts), 1) >= 0.65 and chinese_count <= 6:
        return True

    return False


def _looks_like_ocr_garbage(text: str) -> bool:
    if not text:
        return True

    # 大量奇怪符号
    symbol_count = sum(1 for ch in text if not ch.isalnum() and not "\u4e00" <= ch <= "\u9fff")
    if symbol_count / max(len(text), 1) > 0.5:
        return True

    # 英文超长无意义串
    import re
    letters = re.findall(r"[A-Za-z]", text)
    if len(letters) >= 12:
        words = re.findall(r"[A-Za-z]+", text)
        if words:
            avg_word_len = sum(len(w) for w in words) / len(words)
            if avg_word_len > 14:
                return True

    return False

def _run_doubao_single_frame(
    frame: dict,
    width: int,
    height: int,
) -> list[dict]:
    try:
        from src.stage1.utils.doubao import call_ocr
    except Exception as exc:
        logger.warning("Doubao OCR unavailable: %s", exc)
        return []

    try:
        raw_texts = call_ocr(frame["path"])
        texts = _parse_doubao_items(
            raw_texts=raw_texts,
            width=width,
            height=height,
        )
        return texts
    except Exception as exc:
        logger.warning("Doubao fallback failed for %s: %s", frame.get("frame_id"), exc)
        return []
        
# ============================================================
# Fast Hybrid 模式：推荐默认
# ============================================================


def _run_fast_hybrid_ocr(
    keyframes: list[dict],
    width: int,
    height: int,
) -> list[dict]:
    """
    Fast hybrid OCR 修正版。

    修复点：
    1. Doubao 改为逐帧调用，避免 batch 多图串图。
    2. 只允许 image hash 近似重复帧复用 OCR。
    3. 不再允许“未被采样代表帧复用最近 OCR 帧”。
    4. 被 OCR_MAX_FRAMES 跳过的代表帧返回空 texts，而不是复用错误文本。
    """

    try:
        from src.stage1.utils.doubao import call_ocr
    except Exception as exc:
        logger.warning(
            "Doubao OCR unavailable, fallback to Tesseract: %s", exc)
        return _run_tesseract_ocr(keyframes, width, height)

    max_frames = int(os.getenv("OCR_MAX_FRAMES", "24"))
    hash_threshold = int(os.getenv("OCR_HASH_THRESHOLD", "4"))

    valid_frames = [
        frame for frame in keyframes
        if os.path.exists(frame.get("path", ""))
    ]

    missing_frame_ids = {
        frame.get("frame_id") for frame in keyframes
        if not os.path.exists(frame.get("path", ""))
    }

    if not valid_frames:
        return [
            {
                "frame_id": frame["frame_id"],
                "timestamp": frame.get("timestamp", 0.0),
                "texts": [],
                "ocr_source_frame_id": None,
                "ocr_reused": False,
            }
            for frame in keyframes
        ]

    logger.info("Fast hybrid OCR: valid keyframes %d/%d",
                len(valid_frames), len(keyframes))

    # Step 1: 更保守的图像去重
    # 只有真正相似的帧才允许复用 OCR
    representative_frames, frame_to_rep = _dedup_by_image_hash_strict(
        valid_frames,
        hash_threshold=hash_threshold,
    )

    logger.info(
        "Image hash dedup: representative frames %d/%d",
        len(representative_frames),
        len(valid_frames),
    )

    # Step 2: 控制实际 OCR 帧数
    # 注意：没被选中的 representative 不再复用最近 OCR 帧
    if max_frames > 0 and len(representative_frames) > max_frames:
        frames_to_ocr = _sample_frames_evenly(
            representative_frames, max_frames)
    else:
        frames_to_ocr = representative_frames

    frames_to_ocr_ids = {frame["frame_id"] for frame in frames_to_ocr}

    logger.info(
        "Frames sent to single-image Doubao OCR: %d/%d",
        len(frames_to_ocr),
        len(representative_frames),
    )

    # Step 3: 逐帧调用 Doubao OCR
    frame_id_to_result: dict[str, list[dict]] = {}

    for idx, frame in enumerate(frames_to_ocr):
        fid = frame["frame_id"]
        frame_path = frame["path"]

        logger.info("Doubao single OCR: %s (%d/%d)",
                    fid, idx + 1, len(frames_to_ocr))

        try:
            raw_texts = call_ocr(frame_path)
            frame_id_to_result[fid] = _parse_doubao_items(
                raw_texts=raw_texts,
                width=width,
                height=height,
            )
        except Exception as exc:
            logger.warning("Doubao OCR failed for %s: %s", fid, exc)
            frame_id_to_result[fid] = []

    # Step 4: 组装所有 keyframe 的 OCR 结果
    ocr_results: list[dict] = []

    for frame in keyframes:
        fid = frame["frame_id"]

        if fid in missing_frame_ids:
            ocr_results.append({
                "frame_id": fid,
                "timestamp": frame.get("timestamp", 0.0),
                "texts": [],
                "ocr_source_frame_id": None,
                "ocr_reused": False,
                "ocr_skipped_reason": "missing_frame_file",
            })
            continue

        rep_id = frame_to_rep.get(fid, fid)

        # 情况 A：代表帧被真实 OCR 过
        if rep_id in frame_id_to_result:
            texts = frame_id_to_result.get(rep_id, [])
            ocr_results.append({
                "frame_id": fid,
                "timestamp": frame.get("timestamp", 0.0),
                "texts": texts,
                "ocr_source_frame_id": rep_id,
                "ocr_reused": fid != rep_id,
            })
            continue

        # 情况 B：这个 frame 本身是 representative，
        # 但因为 OCR_MAX_FRAMES 预算限制没被 OCR。
        # 这里绝对不要复用最近 OCR 帧。
        ocr_results.append({
            "frame_id": fid,
            "timestamp": frame.get("timestamp", 0.0),
            "texts": [],
            "ocr_source_frame_id": None,
            "ocr_reused": False,
            "ocr_skipped_reason": "skipped_by_ocr_budget",
        })

    return ocr_results


def _parse_doubao_items(
    raw_texts: list[dict],
    width: int,
    height: int,
) -> list[dict]:
    """
    解析 Doubao OCR 返回结果。
    Doubao 当前返回 position 字段时，bbox 只能估算。
    后续如果 Doubao 返回真实坐标，可在这里替换为真实 bbox。
    """
    texts: list[dict] = []

    for item in raw_texts:
        content = item.get("content", "").strip()
        if not content:
            continue

        position = item.get("position", "")
        estimated_bbox = _estimate_bbox_from_position(position, width, height)
        confidence = float(item.get("confidence", 0.8))

        texts.append({
            "content": content,
            "bbox": estimated_bbox["bbox"],
            "normalized_bbox": estimated_bbox["normalized_bbox"],
            "confidence": round(confidence, 4),
            "text_type": item.get("type", "other"),
        })

    return texts


def _dedup_by_image_hash_strict(
    frames: list[dict],
    hash_threshold: int = 4,
) -> tuple[list[dict], dict[str, str]]:
    """
    更保守的 OCR 图像去重。

    只有在 whole / center / bottom / top 多个区域都相似时，
    才认为两帧可以复用 OCR。

    这样可以避免：
    - 黑底白字画面因为大面积黑色背景被误判为重复
    - 不同字幕页被错误复用
    """
    try:
        from PIL import Image
        import imagehash
    except ImportError as exc:
        logger.warning(
            "Pillow/imagehash not available, skip image dedup: %s", exc)
        return frames, {frame["frame_id"]: frame["frame_id"] for frame in frames}

    representative_frames: list[dict] = []
    representative_hashes: list[dict] = []
    frame_to_rep: dict[str, str] = {}

    for frame in frames:
        frame_path = frame.get("path")
        fid = frame["frame_id"]

        try:
            hashes = _compute_multi_roi_hash(frame_path)
        except Exception as exc:
            logger.debug(
                "Failed to compute multi ROI hash for %s: %s", frame_path, exc)
            representative_frames.append(frame)
            representative_hashes.append({})
            frame_to_rep[fid] = fid
            continue

        matched_rep_id = None

        for rep_frame, rep_hashes in zip(representative_frames, representative_hashes):
            if not rep_hashes:
                continue

            if _is_multi_roi_hash_similar(
                hashes,
                rep_hashes,
                threshold=hash_threshold,
            ):
                matched_rep_id = rep_frame["frame_id"]
                break

        if matched_rep_id is None:
            representative_frames.append(frame)
            representative_hashes.append(hashes)
            frame_to_rep[fid] = fid
        else:
            frame_to_rep[fid] = matched_rep_id

    return representative_frames, frame_to_rep


def _compute_multi_roi_hash(image_path: str) -> dict:
    """
    为 OCR 去重计算多区域 hash。

    区域：
    - whole: 整体画面
    - top: 顶部区域，常见 logo / 标题
    - center: 中央大字
    - bottom: 底部字幕
    """
    from PIL import Image
    import imagehash

    image = Image.open(image_path).convert("RGB")
    w, h = image.size

    rois = {
        "whole": image,
        "top": image.crop((0, 0, w, int(h * 0.25))),
        "center": image.crop((0, int(h * 0.25), w, int(h * 0.75))),
        "bottom": image.crop((0, int(h * 0.65), w, h)),
    }

    hashes = {}

    for name, roi in rois.items():
        roi = roi.resize((320, 180))
        hashes[name] = imagehash.phash(roi)

    return hashes


def _is_multi_roi_hash_similar(
    a: dict,
    b: dict,
    threshold: int = 4,
) -> bool:
    """
    多区域都相似，才判定为重复帧。

    这里故意保守：
    - whole 相似还不够
    - center / bottom 至少要相似
    """
    required_keys = ["whole", "center", "bottom"]

    for key in required_keys:
        if key not in a or key not in b:
            return False

    whole_dist = a["whole"] - b["whole"]
    center_dist = a["center"] - b["center"]
    bottom_dist = a["bottom"] - b["bottom"]

    if whole_dist <= threshold and center_dist <= threshold and bottom_dist <= threshold:
        return True

    return False


def _sample_frames_evenly(frames: list[dict], max_frames: int) -> list[dict]:
    """
    从代表帧中均匀采样，保证覆盖视频前、中、后。

    不随机采样，保证同一个视频多次运行结果稳定。
    """
    if len(frames) <= max_frames:
        return frames

    if max_frames <= 1:
        return [frames[0]]

    n = len(frames)
    selected: list[dict] = []
    seen_indices = set()

    for i in range(max_frames):
        idx = round(i * (n - 1) / (max_frames - 1))
        if idx not in seen_indices:
            selected.append(frames[idx])
            seen_indices.add(idx)

    return selected


# def _map_representatives_to_ocr_frames(
#     representative_frames: list[dict],
#     frames_to_ocr: list[dict],
# ) -> dict[str, str]:
#     """
#     当代表帧数量超过 OCR_MAX_FRAMES 时，只有部分代表帧会被 OCR。
#     未被 OCR 的代表帧需要复用最近的 OCR 帧结果。

#     返回:
#     {
#       representative_frame_id: nearest_ocr_frame_id
#     }
#     """
#     if not frames_to_ocr:
#         return {
#             frame["frame_id"]: frame["frame_id"]
#             for frame in representative_frames
#         }

#     ocr_candidates = [
#         {
#             "frame_id": frame["frame_id"],
#             "timestamp": float(frame.get("timestamp", 0.0)),
#         }
#         for frame in frames_to_ocr
#     ]

#     mapping: dict[str, str] = {}

#     for rep_frame in representative_frames:
#         rep_id = rep_frame["frame_id"]
#         rep_ts = float(rep_frame.get("timestamp", 0.0))

#         nearest = min(
#             ocr_candidates,
#             key=lambda item: abs(item["timestamp"] - rep_ts),
#         )

#         mapping[rep_id] = nearest["frame_id"]

#     return mapping


# ============================================================
# Hybrid 模式：保留原方案
# ============================================================

def _run_hybrid_ocr(keyframes: list[dict], width: int, height: int) -> list[dict]:
    from src.stage1.utils.doubao import call_ocr_batch

    logger.info("Step 1: Tesseract scan frames with text...")
    tesseract_available = _check_tesseract()

    frames_with_text = []
    frames_without_text = []
    frame_raw_texts = {}

    for frame in keyframes:
        frame_path = frame["path"]
        if not os.path.exists(frame_path):
            frames_without_text.append(frame)
            continue

        if tesseract_available:
            has_text, raw_text = _tesseract_has_text(frame_path)
            frame_raw_texts[frame["frame_id"]] = raw_text
        else:
            has_text = True
            frame_raw_texts[frame["frame_id"]] = ""

        if has_text:
            frames_with_text.append(frame)
        else:
            frames_without_text.append(frame)

    logger.info("Tesseract filter: %d/%d frames with text",
                len(frames_with_text), len(keyframes))

    if tesseract_available and len(frames_with_text) > 1:
        frames_to_ocr = _dedup_frames(frames_with_text, frame_raw_texts)
    else:
        frames_to_ocr = frames_with_text

    logger.info("Text dedup: %d/%d frames sent to Doubao",
                len(frames_to_ocr), len(frames_with_text))

    doubao_results: dict[str, list[dict]] = {}
    batch_size = int(os.getenv("OCR_BATCH_SIZE", "4"))

    for i in range(0, len(frames_to_ocr), batch_size):
        batch = frames_to_ocr[i:i + batch_size]
        batch_paths = [frame["path"] for frame in batch]
        batch_ids = [frame["frame_id"] for frame in batch]

        logger.info(
            "Doubao batch OCR: %s (%d/%d)",
            batch_ids,
            i + len(batch),
            len(frames_to_ocr),
        )

        batch_results = call_ocr_batch(batch_paths)

        for frame in batch:
            raw_texts = batch_results.get(frame["path"], [])
            doubao_results[frame["frame_id"]] = _parse_doubao_items(
                raw_texts=raw_texts,
                width=width,
                height=height,
            )

    ocr_results = []
    last_texts = []
    frames_with_text_ids = {frame["frame_id"] for frame in frames_with_text}

    for frame in keyframes:
        fid = frame["frame_id"]

        if fid in doubao_results:
            last_texts = doubao_results[fid]
        elif fid in frames_with_text_ids:
            # 被去重跳过，复用上一帧
            pass
        else:
            last_texts = []

        ocr_results.append({
            "frame_id": fid,
            "timestamp": frame.get("timestamp", 0.0),
            "texts": last_texts,
            "ocr_source_frame_id": fid if fid in doubao_results else None,
            "ocr_reused": fid not in doubao_results,
        })

    return ocr_results


# ============================================================
# 纯 Doubao 模式
# ============================================================

def _run_doubao_ocr(keyframes: list[dict], width: int, height: int) -> list[dict]:
    from src.stage1.utils.doubao import call_ocr

    ocr_results = []

    for frame in keyframes:
        frame_path = frame["path"]

        if not os.path.exists(frame_path):
            ocr_results.append({
                "frame_id": frame["frame_id"],
                "timestamp": frame.get("timestamp", 0.0),
                "texts": [],
                "ocr_source_frame_id": None,
                "ocr_reused": False,
            })
            continue

        logger.info("Doubao OCR: %s", frame["frame_id"])
        raw_texts = call_ocr(frame_path)

        texts = _parse_doubao_items(
            raw_texts=raw_texts,
            width=width,
            height=height,
        )

        ocr_results.append({
            "frame_id": frame["frame_id"],
            "timestamp": frame.get("timestamp", 0.0),
            "texts": texts,
            "ocr_source_frame_id": frame["frame_id"],
            "ocr_reused": False,
        })

    return ocr_results


# ============================================================
# 纯 Tesseract 模式
# ============================================================

def _run_tesseract_ocr(keyframes: list[dict], width: int, height: int) -> list[dict]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("pytesseract/Pillow not installed.") from exc

    ocr_results = []

    for frame in keyframes:
        frame_path = frame["path"]

        if not os.path.exists(frame_path):
            ocr_results.append({
                "frame_id": frame["frame_id"],
                "timestamp": frame.get("timestamp", 0.0),
                "texts": [],
                "ocr_source_frame_id": None,
                "ocr_reused": False,
            })
            continue

        image = Image.open(frame_path)
        img_w, img_h = image.size if image.size else (width, height)

        data = pytesseract.image_to_data(
            image,
            lang=os.getenv("TESSERACT_LANG", "chi_sim+eng"),
            output_type=pytesseract.Output.DICT,
        )

        texts = []
        n = len(data.get("text", []))

        for i in range(n):
            content = (data["text"][i] or "").strip()
            if not content:
                continue

            try:
                conf = float(data["conf"][i])
            except Exception:
                conf = -1.0

            if conf < 0:
                continue

            x = int(data["left"][i])
            y = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])

            bbox = [x, y, x + w, y + h]

            texts.append({
                "content": content,
                "bbox": bbox,
                "normalized_bbox": _normalize_bbox(bbox, img_w, img_h),
                "confidence": round(conf / 100 if conf > 1 else conf, 4),
                "text_type": "tesseract",
            })

        ocr_results.append({
            "frame_id": frame["frame_id"],
            "timestamp": frame.get("timestamp", 0.0),
            "texts": texts,
            "ocr_source_frame_id": frame["frame_id"],
            "ocr_reused": False,
        })

    return ocr_results


# ============================================================
# 工具函数
# ============================================================
def _check_tesseract() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        logger.warning("Tesseract unavailable, all frames will go to Doubao")
        return False


def _tesseract_has_text(image_path: str) -> tuple[bool, str]:
    """
    用 Tesseract 快速判断一张图片是否有文字。

    返回:
    - has_text: 是否有文字
    - raw_text: 粗识别结果，用于相邻帧文本去重
    """
    try:
        import pytesseract
        from PIL import Image

        image = Image.open(image_path)
        text = pytesseract.image_to_string(
            image,
            lang=os.getenv("TESSERACT_LANG", "chi_sim+eng"),
            timeout=int(os.getenv("TESSERACT_TIMEOUT", "5")),
        )

        cleaned = text.strip().replace("\n", "").replace(" ", "")
        return len(cleaned) >= 2, cleaned

    except Exception as exc:
        logger.debug("Tesseract quick scan failed %s: %s", image_path, exc)
        return True, ""


def _dedup_frames(
    frames: list[dict],
    frame_raw_texts: dict,
    similarity_threshold: float = 0.8,
) -> list[dict]:
    """
    对比相邻帧的文字内容，跳过相似帧。

    这是原 hybrid 模式的文本去重逻辑。
    fast_hybrid 不依赖这个函数。
    """
    if len(frames) <= 1:
        return frames

    result = [frames[0]]

    for i in range(1, len(frames)):
        prev_text = frame_raw_texts.get(frames[i - 1]["frame_id"], "")
        curr_text = frame_raw_texts.get(frames[i]["frame_id"], "")
        sim = _text_similarity(prev_text, curr_text)

        if sim < similarity_threshold:
            result.append(frames[i])

    return result


def _text_similarity(a: str, b: str) -> float:
    """
    简单文本相似度。
    当前只用于原 hybrid 模式的粗略去重。
    """
    if not a and not b:
        return 1.0

    if not a or not b:
        return 0.0

    common = sum(1 for ca, cb in zip(a, b) if ca == cb)
    return common / max(len(a), len(b))


def _normalize_bbox(bbox: list[int], width: int, height: int) -> list[float]:
    """
    像素坐标转归一化坐标。

    bbox:
        [x1, y1, x2, y2]

    return:
        [x1 / width, y1 / height, x2 / width, y2 / height]
    """
    if width <= 0 or height <= 0:
        return [0.0, 0.0, 0.0, 0.0]

    x1, y1, x2, y2 = bbox

    return [
        round(max(0.0, min(1.0, x1 / width)), 6),
        round(max(0.0, min(1.0, y1 / height)), 6),
        round(max(0.0, min(1.0, x2 / width)), 6),
        round(max(0.0, min(1.0, y2 / height)), 6),
    ]


def _estimate_bbox_from_position(position: str, width: int, height: int) -> dict:
    """
    根据 Doubao 返回的位置描述估算 bbox。

    当前 Doubao OCR 如果只返回 “顶部 / 底部 / 中间 / 左侧 / 右侧”
    这类语义位置，就先用估算框。

    后续如果 API 返回真实坐标，可以替换这个函数。
    """
    nx1, ny1, nx2, ny2 = 0.2, 0.4, 0.8, 0.6

    pos = position.lower() if position else ""

    if "顶" in pos or "上" in pos or "top" in pos:
        ny1, ny2 = 0.02, 0.15
    elif "底" in pos or "下" in pos or "bottom" in pos:
        ny1, ny2 = 0.80, 0.95
    elif "中" in pos or "center" in pos or "middle" in pos:
        ny1, ny2 = 0.40, 0.60

    if "左" in pos or "left" in pos:
        nx1, nx2 = 0.02, 0.45
    elif "右" in pos or "right" in pos:
        nx1, nx2 = 0.55, 0.98
    elif "居中" in pos or "center" in pos:
        nx1, nx2 = 0.15, 0.85

    bbox = [
        int(nx1 * width),
        int(ny1 * height),
        int(nx2 * width),
        int(ny2 * height),
    ]

    return {
        "bbox": bbox,
        "normalized_bbox": [
            round(nx1, 6),
            round(ny1, 6),
            round(nx2, 6),
            round(ny2, 6),
        ],
    }


def _filter_watermarks(ocr_results: list[dict]) -> list[dict]:
    """
    为每帧增加 clean_texts，过滤平台水印、账号信息等低价值 OCR 文本。

    判断逻辑：
    1. 命中平台/账号关键词：删除
    2. 高频重复 + 角落位置：删除
    3. 角落位置 + 像账号/Logo：删除

    注意：不删除原始 texts。
    - texts: 原始 OCR 结果，用于调试和前端画 bbox
    - clean_texts: 过滤后的主内容，供 Stage 2 使用
    - removed_watermarks: 被过滤掉的水印/平台信息
    """
    repeated_watermarks = _detect_repeated_watermark_texts(ocr_results)

    for item in ocr_results:
        texts = item.get("texts", [])

        clean_texts = []
        removed_texts = []

        for text_item in texts:
            reason = _get_watermark_reason(text_item, repeated_watermarks)

            if reason:
                removed_item = dict(text_item)
                removed_item["watermark_reason"] = reason
                removed_texts.append(removed_item)
            else:
                clean_texts.append(text_item)

        item["clean_texts"] = clean_texts
        item["removed_watermarks"] = removed_texts
        item["has_meaningful_text"] = len(clean_texts) > 0

    return ocr_results


def _detect_repeated_watermark_texts(ocr_results: list[dict]) -> set[str]:
    """
    找出在大量帧中反复出现的文本。

    高频文本不一定都是水印，所以后续还会结合位置判断。
    """
    from collections import Counter

    total_frames = len(ocr_results)
    if total_frames < 3:
        return set()

    min_ratio = float(os.getenv("OCR_WATERMARK_MIN_RATIO", "0.35"))
    min_count = int(os.getenv("OCR_WATERMARK_MIN_COUNT", "5"))

    counter: Counter[str] = Counter()

    for item in ocr_results:
        seen_in_frame = set()

        for text_item in item.get("texts", []):
            content = text_item.get("content", "").strip()
            norm = _normalize_watermark_text(content)
            if norm:
                seen_in_frame.add(norm)

        for norm in seen_in_frame:
            counter[norm] += 1

    repeated = {
        text for text, count in counter.items()
        if count >= min_count and count / max(total_frames, 1) >= min_ratio
    }

    if repeated:
        logger.info("Detected repeated OCR texts as watermark candidates: %s", repeated)

    return repeated


def _get_watermark_reason(text_item: dict, repeated_watermarks: set[str]) -> str | None:
    content = text_item.get("content", "").strip()

    if not content:
        return "empty_text"

    # 强平台/账号关键词可以直接删除，例如抖音号、douyin、FENDA。
    if _matches_strong_platform_watermark(content):
        return "platform_keyword"

    norm = _normalize_watermark_text(content)

    # 弱平台提示词只在角落/边缘区域删除，避免误删正文中的“关注/搜索”。
    if _matches_weak_platform_hint(content) and _is_corner_or_edge_text(text_item):
        return "weak_platform_hint_at_edge"

    # 高频 + 角落/边缘，才判定为水印。避免误删中央重复 CTA。
    if norm in repeated_watermarks and _is_corner_or_edge_text(text_item):
        return "repeated_corner_text"

    # 角落 + 像账号/Logo，也判定为水印。
    if _is_corner_or_edge_text(text_item) and _looks_like_account_or_logo(content):
        return "corner_account_or_logo"

    return None


def _matches_strong_platform_watermark(content: str) -> bool:
    text = _normalize_watermark_text(content)

    strong_patterns = [
        "抖音",
        "抖音号",
        "douyin",
        "fenda2452236",
        "fenda",
        "venda",
        "芬达",
    ]

    return any(_normalize_watermark_text(pattern) in text for pattern in strong_patterns)


def _matches_weak_platform_hint(content: str) -> bool:
    text = _normalize_watermark_text(content)

    weak_patterns = [
        "来抖音",
        "发现更多",
        "发现更多创作者",
        "搜索",
        "关注",
    ]

    return any(_normalize_watermark_text(pattern) in text for pattern in weak_patterns)


# Backward-compatible alias.
def _matches_platform_watermark(content: str) -> bool:
    return _matches_strong_platform_watermark(content) or _matches_weak_platform_hint(content)


def _normalize_watermark_text(text: str) -> str:
    """
    水印匹配用归一化。
    保留中英文和数字，去掉常见空格/标点差异。
    """
    if not text:
        return ""

    text = text.lower().strip()
    remove_chars = [" ", "\n", "\t", "：", ":", "，", ",", "。", ".", "、", "-", "_", "@"]
    for ch in remove_chars:
        text = text.replace(ch, "")

    return text


def _is_corner_or_edge_text(text_item: dict) -> bool:
    """
    判断文字是否位于角落/边缘区域。

    这版故意保守：
    - 右下角：平台水印高发区
    - 左下角：只有非常贴边/很低的位置才算，避免误删左下字幕
    - 顶部边缘：账号/平台提示高发区
    """
    bbox = text_item.get("normalized_bbox") or []
    if len(bbox) != 4:
        return False

    x1, y1, x2, y2 = bbox

    # 右下角，典型平台水印位置。
    if x1 > 0.58 and y1 > 0.66:
        return True

    # 左下角靠边且很低，避免把左下字幕当水印。
    if x1 < 0.08 and x2 < 0.42 and y1 > 0.82:
        return True

    # 顶部边缘，常见平台条/账号信息。
    if y2 < 0.11:
        return True

    return False


def _looks_like_account_or_logo(content: str) -> bool:
    """
    判断是否像账号名、Logo、平台标识。

    关键原则：
    - 中文短句不要当 logo。
    - 不使用 len(text)<=1，避免误删 OCR 拆开的有效单字。
    """
    if not content:
        return True

    text = content.strip()
    lower = text.lower()

    # 明确平台/账号。
    if _matches_strong_platform_watermark(text):
        return True

    # 中文短句更可能是字幕，不按 logo 删除。
    chinese_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    if chinese_count >= 2:
        return False

    if text.startswith("@"):
        return True

    if any(ch.isdigit() for ch in text) and any(ch.isalpha() for ch in text):
        return True

    if "号" in text or "id" in lower:
        return True

    # 英文/拼音短品牌名，位于角落时大概率是 logo/账号。
    alpha_chars = [ch for ch in text if ch.isalpha()]
    if len(alpha_chars) >= 3 and len(text) <= 16:
        return True

    return False


def _add_display_texts(ocr_results: list[dict]) -> list[dict]:
    """
    给前端和 Stage 2 添加推荐读取字段。

    - display_texts: 推荐读取的结构化文本列表
    - display_text: 拼接后的字符串，适合前端直接展示
    """
    for item in ocr_results:
        if item.get("is_duplicate_text_frame", False):
            display_texts = item.get("unique_clean_texts", [])
        else:
            display_texts = item.get("unique_clean_texts") or item.get("clean_texts", [])

        item["display_texts"] = display_texts
        item["display_text"] = " ".join(
            t.get("content", "").strip()
            for t in display_texts
            if t.get("content", "").strip()
        )

    return ocr_results


def _merge_consecutive_duplicates(ocr_results: list[dict]) -> list[dict]:
    """
    标记连续重复 OCR 内容。

    不删除 frame 本身，避免破坏 keyframe 对齐。
    只增加字段：
    - is_duplicate_text_frame
    - duplicate_of_frame_id
    - unique_clean_texts

    Stage 2 可以优先读取 unique_clean_texts。
    """
    prev_signature = None
    prev_frame_id = None

    for item in ocr_results:
        clean_texts = item.get("clean_texts", [])
        signature = _make_text_signature(clean_texts)

        if signature and signature == prev_signature:
            item["is_duplicate_text_frame"] = True
            item["duplicate_of_frame_id"] = prev_frame_id
            item["unique_clean_texts"] = []
        else:
            item["is_duplicate_text_frame"] = False
            item["duplicate_of_frame_id"] = None
            item["unique_clean_texts"] = clean_texts

            if signature:
                prev_signature = signature
                prev_frame_id = item.get("frame_id")
            else:
                # 空文本帧打断连续重复链，避免 A / 空 / A 被误判为连续重复。
                prev_signature = None
                prev_frame_id = None

    return ocr_results


def _make_text_signature(texts: list[dict]) -> str:
    """
    把一帧的 clean_texts 变成可比较签名。
    """
    contents = []

    for item in texts:
        content = item.get("content", "").strip()
        if content:
            contents.append(_normalize_text_for_dedup(content))

    if not contents:
        return ""

    return "|".join(contents)


def _normalize_text_for_dedup(text: str) -> str:
    """
    用于去重的文本归一化。
    """
    text = text.strip()
    text = text.replace(" ", "")
    text = text.replace("\n", "")
    text = text.replace("，", ",")
    text = text.replace("。", ".")
    text = text.replace("：", ":")
    text = text.replace("！", "!")
    text = text.replace("？", "?")
    return text.lower()

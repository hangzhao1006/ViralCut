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
OCR_METHOD=fast_hybrid
OCR_MAX_FRAMES=12
OCR_BATCH_SIZE=4
OCR_MAX_WORKERS=2
OCR_HASH_THRESHOLD=6
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

    method = os.getenv("OCR_METHOD", "fast_hybrid").lower().strip()

    logger.info("OCR method: %s, keyframes: %d", method, len(keyframes))

    if method == "fast_hybrid":
        ocr_results = _run_fast_hybrid_ocr(keyframes, width, height)
    elif method == "hybrid":
        ocr_results = _run_hybrid_ocr(keyframes, width, height)
    elif method == "llm":
        ocr_results = _run_doubao_ocr(keyframes, width, height)
    elif method == "tesseract":
        ocr_results = _run_tesseract_ocr(keyframes, width, height)
    else:
        logger.warning("Unknown OCR_METHOD=%s, fallback to fast_hybrid", method)
        ocr_results = _run_fast_hybrid_ocr(keyframes, width, height)

    ocr_results = _filter_watermarks(ocr_results)
    write_json(os.path.join(output_dir, "ocr.json"), ocr_results)
    return {"ocr_results": ocr_results}


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
        logger.warning("Doubao OCR unavailable, fallback to Tesseract: %s", exc)
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

    logger.info("Fast hybrid OCR: valid keyframes %d/%d", len(valid_frames), len(keyframes))

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
        frames_to_ocr = _sample_frames_evenly(representative_frames, max_frames)
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

        logger.info("Doubao single OCR: %s (%d/%d)", fid, idx + 1, len(frames_to_ocr))

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
        logger.warning("Pillow/imagehash not available, skip image dedup: %s", exc)
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
            logger.debug("Failed to compute multi ROI hash for %s: %s", frame_path, exc)
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

    logger.info("Tesseract filter: %d/%d frames with text", len(frames_with_text), len(keyframes))

    if tesseract_available and len(frames_with_text) > 1:
        frames_to_ocr = _dedup_frames(frames_with_text, frame_raw_texts)
    else:
        frames_to_ocr = frames_with_text

    logger.info("Text dedup: %d/%d frames sent to Doubao", len(frames_to_ocr), len(frames_with_text))

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
def _filter_watermarks(ocr_results: list[dict], threshold: float = 0.5) -> list[dict]:
    """
    过滤水印文字：统计所有帧的文字出现频率，
    出现在超过 threshold 比例的帧中的文字视为水印，自动去除。
    """
    total_frames = len(ocr_results)
    if total_frames < 3:
        return ocr_results

    # 统计每段文字出现在多少帧里
    text_freq = {}
    for result in ocr_results:
        seen = set()
        for t in result.get("texts", []):
            content = t["content"].strip()
            if content not in seen:
                text_freq[content] = text_freq.get(content, 0) + 1
                seen.add(content)

    # 出现频率超过阈值的是水印
    watermarks = {
        text for text, count in text_freq.items()
        if count / total_frames >= threshold
    }

    if watermarks:
        logger.info("检测到水印文字（已过滤）: %s", watermarks)

    # 从每帧结果中去除水印
    filtered = []
    for result in ocr_results:
        new_texts = [
            t for t in result.get("texts", [])
            if t["content"].strip() not in watermarks
        ]
        filtered.append({
            **result,
            "texts": new_texts,
        })

    return filtered

    
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
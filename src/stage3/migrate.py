"""Stage 3 structure migration engine.

Takes a transfer blueprint (from Stage 2) + new content + user assets,
produces a migration plan with gap identification and fill strategies.

Usage:
    from src.stage3.migrate import run_migration
    result = run_migration(blueprint, new_content, user_assets)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.stage2.llm_client import create_llm_client
from src.stage3.asset_matcher import precheck_assets

PROMPT_PATH = Path(__file__).parent / "prompts" / "migration.md"


def run_migration(
    blueprint: dict[str, Any],
    new_content: dict[str, Any],
    user_assets: dict[str, Any],
) -> dict[str, Any]:
    """Run structure migration. Single LLM call.

    Args:
        blueprint: transfer_blueprint from video_structure.json
        new_content: {topic, target_type, selling_points, description}
        user_assets: {videos: [...], images: [...], texts: [...], has_bgm: bool}

    Returns:
        Migration result with migrated_slots, gap_summary, fill strategies.
    """
    client = create_llm_client()
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    # Code-level pre-check
    precheck = precheck_assets(blueprint, user_assets)

    user_prompt = f"""## 样例视频的可迁移结构（transfer blueprint）
{json.dumps(blueprint, ensure_ascii=False, indent=2)}

## 用户的新内容
{json.dumps(new_content, ensure_ascii=False, indent=2)}

## 用户拥有的素材
{json.dumps(user_assets, ensure_ascii=False, indent=2)}

## 素材预检查（代码层初步判断，供参考）
{json.dumps(precheck, ensure_ascii=False, indent=2)}

请把样例结构迁移到新内容，识别素材缺口并给出补全策略，最终只输出JSON。"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat(messages=messages, tools=None)
    content = response.get("content", "{}")
    result = _parse_json(content)

    # Attach precheck for transparency
    result["_precheck"] = precheck
    return result


def _parse_json(content: str) -> dict[str, Any]:
    """Parse JSON from LLM response, handling markdown code blocks."""
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {"error": "failed to parse migration result", "raw_text": content}


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    import argparse

    parser = argparse.ArgumentParser(description="Stage 3 structure migration")
    parser.add_argument("video_structure", help="Path to video_structure.json")
    parser.add_argument("--topic", required=True, help="New content topic")
    parser.add_argument("--type", default="product_ad", help="target_type (matches adaptation_guidance key)")
    parser.add_argument("--points", default="", help="Comma-separated selling points")
    parser.add_argument("--videos", type=int, default=0, help="Number of user video clips")
    parser.add_argument("--images", type=int, default=0, help="Number of user images")
    parser.add_argument("--texts", type=int, default=0, help="Number of user text snippets")
    parser.add_argument("--bgm", action="store_true", help="User has BGM")
    parser.add_argument("--out", help="Output JSON path")
    args = parser.parse_args()

    with open(args.video_structure, "r", encoding="utf-8") as f:
        vs = json.load(f)
    blueprint = vs.get("transfer_blueprint", {}).get("transfer_blueprint", {})
    if not blueprint:
        blueprint = vs.get("transfer_blueprint", {})

    new_content = {
        "topic": args.topic,
        "target_type": args.type,
        "selling_points": [p.strip() for p in args.points.split(",") if p.strip()],
        "description": "",
    }
    user_assets = {
        "videos": [{"id": f"v{i+1}", "duration": 5.0, "description": ""} for i in range(args.videos)],
        "images": [{"id": f"i{i+1}", "description": ""} for i in range(args.images)],
        "texts": [f"text_{i+1}" for i in range(args.texts)],
        "has_bgm": args.bgm,
    }

    result = run_migration(blueprint, new_content, user_assets)

    out_path = args.out or "migration_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"Migration result saved to {out_path}")
    print(f"Feasibility: {result.get('overall_feasibility')}")
    gs = result.get("gap_summary", {})
    print(f"Slots: {gs.get('filled')}/{gs.get('total_slots')} filled, {gs.get('gaps')} gaps")

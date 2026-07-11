import aiohttp
import asyncio
import json
import os
import re

GEOJSON_URL = "https://www.data.gouv.fr/fr/datasets/r/bfba7898-aed3-40ec-aa74-abb73b92a363"


async def main():
    async with aiohttp.ClientSession() as session:
        resp = await session.get(GEOJSON_URL)
        if resp.status != 200:
            raise Exception(f"Unable to get dataset from vigieau: {resp.status}")
        data = await resp.json(content_type="binary/octet-stream")

    descriptions = {}
    for feature in data["features"]:
        for r in feature["properties"].get("restrictions", []):
            desc = r.get("description", "").strip()
            if not desc:
                continue
            if desc not in descriptions:
                descriptions[desc] = {
                    "description": desc,
                    "has_time_pattern": bool(re.search(r"\d+\s*h", desc)),
                    "has_uniquement": bool(re.search(r"uniquement", desc, re.IGNORECASE)),
                    "example_usage": r.get("nom", ""),
                    "example_thematique": r.get("thematique", ""),
                }

    result = {
        "descriptions": sorted(descriptions.values(), key=lambda d: d["description"])
    }

    file = os.path.join(os.path.dirname(__file__), "full_descriptions_list.json")
    with open(file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(descriptions)} unique descriptions to {file}")


if __name__ == "__main__":
    asyncio.run(main())

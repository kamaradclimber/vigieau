import aiohttp
import asyncio
import os
import json
from frozendict import frozendict
import sys

current_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(current_dir)
sys.path.append(".")
sys.path.append(parent_dir)

from custom_components.vigieau.api import InseeApi, VigieauApi, VigieauApiError


async def main():
    restriction_list = {"restrictions": []}
    usages = set()
    async with aiohttp.ClientSession() as session:

        resp = await session.get("https://www.data.gouv.fr/fr/datasets/r/bfba7898-aed3-40ec-aa74-abb73b92a363")
        if resp.status != 200:
            raise Exception(f"Unable to get dataset from vigieau: {resp.status}")
        data = await resp.json(content_type="binary/octet-stream")

        # jq '.features | .[].properties.restrictions' ~/Downloads/zones_arretes_en_vigueur.geojson   |less
        for feature in data["features"]:
            for restriction in feature["properties"]["restrictions"]:
                usages.add(frozendict({"usage": restriction["nom"], "thematique": restriction["thematique"]}))

        print(f"Found {len(usages)} different usages")
        dump_restrictions(restriction_list, usages)


def dump_restrictions(restriction_list, usages):
    restriction_list["restrictions"] = sorted(
        list(usages), key=lambda h: h["usage"]
    )

    finaldata = json.dumps(restriction_list, ensure_ascii=False, indent=2)
    file = os.path.join(os.path.dirname(__file__), "full_usage_list.json")

    with open(file, "w", encoding="utf-8") as outfile:
        outfile.write(finaldata)


if __name__ == "__main__":
    asyncio.run(main())

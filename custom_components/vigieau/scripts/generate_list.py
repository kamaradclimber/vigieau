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

from custom_components.vigieau.api import InseeAPI, VigieauAPI, VigieauAPIError


async def main():
    usages = set()
    async with aiohttp.ClientSession() as session:

        resp = await session.get("https://www.data.gouv.fr/fr/datasets/r/bfba7898-aed3-40ec-aa74-abb73b92a363")
        if resp.status != 200:
            raise Exception(f"Unable to get dataset from vigieau: {resp.status}")
        data = await resp.json(content_type="binary/octet-stream")

        # jq '.features | .[].properties.restrictions' ~/Downloads/zones_arretes_en_vigueur.geojson   |less
        for feature in data["features"]:
            for restriction in feature["properties"]["restrictions"]:
                usages.add(frozendict({
                    "usage": restriction["nom"],
                    "thematique": restriction["thematique"],
                    "concerneParticulier": restriction.get("concerneParticulier", False),
                    "concerneCollectivite": restriction.get("concerneCollectivite", False),
                    "concerneEtablissement": restriction.get("concerneEtablissement", False),
                    "concerneActivite": restriction.get("concerneActivite", False),
                    "concerneExploitation": restriction.get("concerneExploitation", False),
                    "concerneInstallation": restriction.get("concerneInstallation", False),
                }))

        print(f"Found {len(usages)} different usages")
        dump_restrictions(usages)


def dump_restrictions(new_usages):
    file = os.path.join(os.path.dirname(__file__), "full_usage_list.json")

    with open(file, "r", encoding="utf-8") as infile:
        usage_list = json.load(infile)["restrictions"]
    known_usages = set()
    for r in usage_list:
        known_usages.add(r["usage"])
    for r in new_usages:
        if r["usage"] not in known_usages:
            usage_list.append(r)
    restriction_list = {}

    restriction_list["restrictions"] = sorted(
        list(usage_list), key=lambda h: h["usage"]
    )

    finaldata = json.dumps(restriction_list, ensure_ascii=False, indent=2)

    with open(file, "w", encoding="utf-8") as outfile:
        outfile.write(finaldata)


if __name__ == "__main__":
    asyncio.run(main())

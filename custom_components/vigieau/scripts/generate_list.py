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
        vigieau = VigieauApi(session)
        commune_list = await InseeApi(session).get_insee_list()
        for i, commune in enumerate(commune_list):
            print(f"{i}/{len(commune_list)}: {commune['nom']}")
            try:
                restriction = await vigieau.get_data(
                    insee_code=commune["code"],
                    profil="particulier",
                    lat=commune["centre"]["coordinates"][1],
                    long=commune["centre"]["coordinates"][0],
                )
            except VigieauApiError as e:
                print(e.text)
            # FIXME: Sometimes insee is enough to call vigieau Api, sometimes not exclude the one where it's not enough , for the moment
            if restriction:
                for usage in restriction.get("usages", []):
                    usages.add(
                        frozendict(
                            {"usage": usage["nom"], "thematique": usage["thematique"]}
                        )
                    )
            if i % 10 == 0:
                dump_restrictions(restriction_list, usages)
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

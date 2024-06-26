from homeassistant.components.sensor import (
    SensorEntityDescription,
)
from dataclasses import dataclass

DOMAIN = "vigieau"

VIGIEAU_API_URL = "https://api.vigieau.gouv.fr"
GEOAPI_GOUV_URL = "https://geo.api.gouv.fr/communes?&fields=code,nom,centre"
ADDRESS_API_URL = "https://api-adresse.data.gouv.fr"
CONF_LOCATION_MODE = "location_mode"
HA_COORD = 0
ZIP_CODE = 1
SELECT_COORD = 2
LOCATION_MODES = {
    HA_COORD: "Coordonnées Home Assistant",
    ZIP_CODE: "Code Postal",
    SELECT_COORD: "Sélection sur carte",
}
CONF_INSEE_CODE = "INSEE"
CONF_CITY = "city"
CONF_CODE_POSTAL = "Code postal"
CONF_LOCATION_MAP = "location_map"
NAME = "Vigieau"
DEVICE_ID_KEY = "device_id"


@dataclass
class VigieEauRequiredKeysMixin:
    """Mixin for required keys."""

    category: str
    matchers: list[str]


@dataclass
class VigieEauSensorEntityDescription(
    SensorEntityDescription, VigieEauRequiredKeysMixin
):
    """Describes VigieEau sensor entity."""


SENSOR_DEFINITIONS: tuple[VigieEauSensorEntityDescription, ...] = (
    VigieEauSensorEntityDescription(
        name="Alimentation des fontaines",
        icon="mdi:fountain",
        category="fountains",
        key="fountains",
        matchers=[
            "alimentation des fontaines.+",
            "douches .+ plage.+",
            "fontaines",
            "jeux d'eau",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage des jardins potagers",
        icon="mdi:watering-can",
        category="potagers",
        key="potagers",
        matchers=[
            "Arrosage des .*potagers",
            "arrosage.+arbres.+",
            "arrosage.+plant.+",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage voirie et trottoirs",
        icon="mdi:road",
        category="roads",
        key="roads",
        matchers=[
            "trottoirs",
            "voiries|voieries",
            "Arrosage de surfaces de .+ générant de la poussière",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage des pelouses",
        icon="mdi:sprinkler-variant",
        category="lawn",
        key="lawn",
        matchers=[
            "pelouses",
            "jardins d'agrément",
            "massifs fleuris",
            "Arrosage des espaces verts",
            "Arrosage des jeunes plantations d'arbres",
            "surface.+sportives.+",
            "arrosage.+massif.+",
            "Nettoyage / arrosage des sites de manifestations temporaires sportives et culturelles",
            "Dispositifs de récupération des eaux de pluie",
            "Arrosage, arbustes et arbres",
            "Arrosage des jardinières et suspensions",
            "Arrosage des espaces arborés",
            "Arrosage.+terrains de sport",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Lavage des véhicules",
        icon="mdi:car-wash",
        category="car_wash",
        key="car_wash",
        matchers=[
            "lavage.+particuliers",
            "lavage.+professionnels.+portique",
            "lavage.+professionnels.+haute pression",
            "lavage.+(station|véhicules)",
            "lavage.+professionnel.+",
            "Nettoyage des véhicules et bateaux",
            "Nettoyage des véhicules, des bateaux Y compris par dispositifs mobiles",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Lavage des engins nautiques",
        icon="mdi:sail-boat",
        category="nautical_vehicules",
        key="nautical_vehicules",
        matchers=[
            "Activités nautiques : cas général",
            "lavage.+engins nautiques.+professionnels",
            "Nettoyage.+embarcation",
            "lavage.+bateau.+",
            "nettoyage.+bateau.+",
            "engins nautiques",
            "Lavage des embarcations, motorisées ou non, par tout moyen branché sur le réseau public",
            "Lavage de véhicule disposant d’un système équipé d’un recyclage de l’eau",
            "Carénage des bateaux",
            "Lavage et entretien des embarcations .+ en aire de carénage.",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Lavage des toitures, façades",
        icon="mdi:home-roof",
        category="roof_clean",
        key="roof_clean",
        matchers=[
            "toitures",
            "façades",
            "nettoyage.+bâtiments.+",
            "nettoyage.+terrasse.+",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Vidange et remplissage des piscines",
        icon="mdi:pool",
        category="pool",
        key="pool",
        matchers=[
            "remplissage.+piscines.+(familial|privé)",
            "vidange.+piscines",
            "piscines privées",  # Piscines privées et bains à remous de plus de 1m3
            "piscines non collectives",  # Remplissage et vidange de piscines non collectives (de plus de 1 m3)
            "baignades.+",
            "Remise à niveau des piscines à usage privé",
            "Remplissage des jeux d'eau",
            "Remplissage des piscine privées",
            "Remplissage des piscines individuelles",
            "remise à niveau des piscines",
            "Remplissage de piscines.+",
            "Piscines ouvertes au public",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Remplissage/Vidange des plans d'eau",
        icon="mdi:waves",
        category="ponds",
        key="ponds",
        matchers=[
            "remplissage.+plan.* d.eau",
            "vidange.+plan.* d.eau",
            "Alimentation de plan d'eau",  # Alimentation de plan d'eau en dérivation de cours d'eau à usage domestique
            "alimentation.+plan.* d.eau",
            "alimentation.+bassin.+",
            "lestage pour stabilité",
            "Alimentation d’étangs",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Travaux sur cours d'eau",
        icon="mdi:hydro-power",
        category="river_rate",
        key="river_rate",
        matchers=[
            "ouvrage.+cours d.eau",
            "travaux.+cours d.eau",
            "manoeuvre.+vannes",  # Manoeuvre de vannes des seuils et barrages
            "Gestion des ouvrages",  # FIXME: we should probably match with the category as well
            "travaux.+rivière",
            "rabattement.+nappe.+",
            "faucardage.+",
            "Faucardement",
            "manoeuvre.+d.ouvrage.+",
            "rejet direct d’eaux polluées",
            "orpaillage",
            "Manœuvres des vannes d.installations hydrauliques",
            "Manœuvres d’ouvrages hydrauliques",
            "Tout usage domestique non sanitaire de l’eau",
            "Réalisation d'un seuil provisoire",
            "Rejets directs en cours d’eau",
            "Pratiques ou activités dans le lit pouvant avoir un impact sur les milieux aquatiques",
            "Perturbations physiques du lit des cours d’eau",
            "Entretien de cours d'eau",
            "Travaux et rejets",
            "Travaux sur les systèmes d’assainissement occasionnant des rejets",
            ".+installations hydrauliques.+",
            "production.+origine.+hydraulique.*",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Navigation fluviale",
        icon="mdi:ferry",
        category="river_movement",
        key="river_movement",
        matchers=[
            "Navigation fluviale",
            "Pratique du canyoning sur matériaux alluvionnaires",
            "Pratique de la navigation de loisir",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage des golfs",
        icon="mdi:golf",
        category="golfs",
        key="golfs",
        matchers=["arrosage des golfs"],
    ),
    VigieEauSensorEntityDescription(
        name="Prélèvement en canaux",
        icon="mdi:water-pump",
        category="canals",
        key="canals",
        matchers=[
            "Prélèvement en canaux",
            "Prélèvements dans le milieu naturel.+",
            "prélèvements.+cours d.eau.+",
            "prélèvement.+hydraulique.+",
            "alimentation.+canaux.+",
            "Prélèvements domestiques directs dans les milieux hydrauliques, hors usage professionnel identifié",
            "Prélèvement d’eau domestique en milieu",
            "Prélèvement d’eau domestique dans un canal existant",
            "Prélèvements énergétiques",
            "Prélèvement.* en cours d'eau",
            "Prélèvements destinés au fonctionnement des milieux naturels",
            "Prélèvement sur le site des Marais de Sacy",
            "Tout nouveau prélèvement",
            "Nouvelles demandes de prélèvement d'eau et création de forages",
            "Création de prélèvements",
            "Prélèvement en cours d’eau",
            "alimentation en eau potable des populations.+",
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Restriction spécifique",
        category="misc",
        key="misc",
        matchers=[
            "Remplissage tonne de chasse",
            "Activités cynégétiques",
            "Structures gonflables/tubulaires privées à usage collectif > 1m3 nécessitant 1 vidange quotidienne",
            "Abreuvement et hygiène des animaux",
            "Abreuvement des animaux",
            "Irrigation par aspersion des cultures",
            # ICPE means "Installation classée pour la protection de l'environment"
            "ICPE soumises à un APC relatif à la sécheresse",
            "Usages récréatifs collectifs à partir d’eau potable.+",
            "Réalisation de seuils provisoires",
            "Activités industrielles et commerciales",
        ],
    ),
)

from homeassistant.components.sensor import (
    SensorEntityDescription,
)
from dataclasses import dataclass

DOMAIN = "vigieau"

BASE_URL = "https://api.vigieau.beta.gouv.fr"
GEOAPI_GOUV_URL = "https://geo.api.gouv.fr/communes?"
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
            "alimentation des fontaines publiques et privées",
            "Alimentation des fontaines",  # Alimentation des fontaines/lavoirs sans arrêt technique possible
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage des jardins potagers",
        icon="mdi:watering-can",
        category="potagers",
        key="potagers",
        matchers=["Arrosage des jardins potagers", "Arrosage des potagers"],
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage voirie et trottoirs",
        icon="mdi:road",
        category="roads",
        key="roads",
        matchers=["trottoirs", "voiries"],
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
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Lavage des engins nautiques",
        icon="mdi:sail-boat",
        category="nautical_vehicules",
        key="nautical_vehicules",
        matchers=["lavage.+engins nautiques.+professionnels", "Nettoyage.+embarcation"],
    ),
    VigieEauSensorEntityDescription(
        name="Lavage des toitures",
        icon="mdi:home-roof",
        category="roof_clean",
        key="roof_clean",
        matchers=["toitures"],
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
        ],
    ),
    VigieEauSensorEntityDescription(
        name="Navigation fluviale",
        icon="mdi:ferry",
        category="river_movement",
        key="river_movement",
        matchers=["Navigation fluviale"],
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
        matchers=["Prélèvement en canaux", "Prélèvements dans le milieu naturel.+"],
    ),
)

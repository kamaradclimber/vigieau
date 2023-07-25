from homeassistant.components.sensor import (
    SensorEntityDescription,
)
from dataclasses import dataclass

DOMAIN = "vigieau"

BASE_URL = "https://api.vigieau.beta.gouv.fr"
GEOAPI_GOUV_URL = "https://geo.api.gouv.fr/communes?"
ADRESSE_URL= "https://api-adresse.data.gouv.fr"
CONF_LOCATION_MODE="location_mode"
HA_COORD=0
ZIP_CODE=1
SELECT_COORD=2
LOCATION_MODES= {HA_COORD:"Coordonnées Home Assistant",ZIP_CODE:"Code Postal", SELECT_COORD:"Selection sur carte"}
CONF_INSEE_CODE = "INSEE"
CONF_CITY = "city"
CONF_CODE_POSTAL = "Code postal"
CONF_LOCATION_MAP = "location_map"
NAME= "Vigieau"

DEBUG_DATA = {
    "idZone": "11083",
    "type": "SUP",
    "nom": "EURE Moyen haut",
    "departement": "28",
    "arrete": {
        "idArrete": "33014",
        "dateDebutValidite": "2023-07-12",
        "dateFinValidite": "2023-10-31",
        "cheminFichier": "https://propluvia-data.s3.gra.io.cloud.ovh.net/pdf/ArretesRestriction/2023_227_arrete_mesures_restriction.pdf",
        "cheminFichierArreteCadre": "https://propluvia-data.s3.gra.io.cloud.ovh.net/pdf/ArretesCadres/2023_056_arrete_cadre_secheresse_eaux_sup.pdf",
    },
    "niveauAlerte": "Crise",
    "usages": [
        {
            "thematique": "Alimentation des fontaines publiques et privées",
            "usage": "Alimentation des fontaines publiques et privées d'ornement ",
            "niveauRestriction": "Interdiction sauf exception",
            "details": "L'alimentation des fontaines publiques et privées en circuit ouvert est interdite.",
        },
        {
            "thematique": "Arrosage",
            "usage": "Arrosage des jardins potagers",
            "niveauRestriction": "Interdiction sur plage horaire",
            "heureDebut": "09:00",
            "heureFin": "20:00",
        },
        {
            "thematique": "Arrosage",
            "usage": "Arrosage des pelouses, massifs fleuris",
            "niveauRestriction": "Interdiction",
            "details": "Interdiction",
        },
        {
            "thematique": "Nettoyage",
            "usage": "Lavage de véhicules par les particuliers",
            "niveauRestriction": "Interdiction",
            "details": "Interdit au domicile",
        },
        {
            "thematique": "Nettoyage",
            "usage": "Lavage de véhicules par les professionnels avec portique à rouleaux",
            "niveauRestriction": "Interdiction sauf exception",
            "details": "Interdiction sauf avec une installation équipée d’un système de recyclage d’eau ou en mode ECO",
        },
        {
            "thematique": "Nettoyage",
            "usage": "Lavage de véhicules par les professionnels avec du matériel haute pression",
            "niveauRestriction": "Interdiction sauf exception",
            "details": "Autorisé uniquement avec 50 % du matériel haute pression (les postes non utilisés doivent être neutralisés)  ",
        },
        {
            "thematique": "Nettoyage",
            "usage": "Nettoyage des façades, toitures, trottoirs et autres surfaces imperméabilisées",
            "niveauRestriction": "Interdiction sauf exception",
            "details": "Interdit sauf impératif sanitaire ou sécuritaire, et réalisé par une collectivité ou une entreprise de nettoyage professionnelle.",
        },
        {
            "thematique": "Remplissage vidange",
            "usage": "Remplissage et vidange de piscines privées (de plus d'1 m3)",
            "niveauRestriction": "Interdiction",
            "details": "Interdiction",
        },
        {
            "thematique": "Remplissage vidange",
            "usage": "Remplissage / vidange des plans d'eau",
            "niveauRestriction": "Interdiction sauf exception",
            "details": "Interdiction sauf pour les piscicultures et les usages commerciaux.",
        },
        {
            "thematique": "Travaux en cours d’eau",
            "usage": "Manoeuvre d’ouvrage sur le cours d’eau et affluents (biefs de moulin) hors plan d'eau",
            "niveauRestriction": "Interdiction",
            "details": "Interdiction de toute manœuvre susceptible d’influencer le débit ou le niveau de l’eau, dont ouverture et fermeture, sauf dérogation délivrée par la Direction Départementale des Territoires pour le maintien de zones humides, pour les travaux déclarés d’intérêt général et impératifs liés à la sécurité publique.",
        },
        {
            "thematique": "Travaux en cours d’eau",
            "usage": "Travaux en cours d'eau",
            "niveauRestriction": "Interdiction sauf exception",
            "details": "Report des travaux sauf dérogation délivrée par la Direction Départementale des Territoires en cas d’assec total, pour des raisons de sécurité, dans le cas d’une restauration ou renaturation du cours d’eau.",
        },
    ],
    "usagesHash": "e0cef7962",
}



@dataclass
class VigieEauRequiredKeysMixin:
    """Mixin for required keys."""
    category: str
    matchers: list

@dataclass
class VigieEauSensorEntityDescription(
    SensorEntityDescription, VigieEauRequiredKeysMixin
):
    """Describes VigieEau sensor entity."""

SENSOR_DEFINITIONS: tuple[VigieEauSensorEntityDescription,...]=(
    VigieEauSensorEntityDescription(
        name= "Alimentation des fontaines",
        icon="mdi:fountain",
        category="fountains",
        key="fountains",
        matchers=["alimentation des fontaines publiques et privées"]
    ),
        VigieEauSensorEntityDescription(
        name= "Arrosage des jardins potagers",
        icon="mdi:watering-can",
        category="potagers",
        key="potagers",
        matchers=["Arrosage des jardins potagers","Arrosage des potagers"]
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage voirie et trottoirs",
        icon="mdi:road",
        category="roads",
        key="roads",
        matchers=["trottoirs"]
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage des pelouses",
        icon="mdi:sprinkler-variant",
        category="lawn",
        key="lawn",
        matchers=["pelouses#jardins d'agrément","massifs fleuris"]
    ),
    VigieEauSensorEntityDescription(
        name="Lavage des véhicules",
        icon="mdi:car-wash",
        category="car_wash",
        key="car_wash",
        matchers=["lavage.+particuliers","lavage.+professionnels.+portique","lavage.+professionnels.+haute pression","lavage.+(station|véhicules)"]
    ),
    VigieEauSensorEntityDescription(
        name="Lavage des engins nautiques",
        icon="mdi:sail-boat",
        category="nautical_vehicules",
        key="nautical_vehicules",
        matchers=["(lavage.+engins nautiques.+professionnels)|(Nettoyage.+embarcation)"]
    ),
    VigieEauSensorEntityDescription(
        name="Lavage des toitures",
        icon="mdi:home-roof",
        category="roof_clean",
        key="roof_clean",
        matchers=["toitures"]
    ),
    VigieEauSensorEntityDescription(
        name="Vidange et remplissage des piscines",
        icon="mdi:pool",
        category="pool",
        key="pool",
        matchers=["remplissage.+piscines.+(familial|privé)","vidange.+piscines","piscines privées","piscines non collectives"]
    ),
    VigieEauSensorEntityDescription(
        name="Remplissage des plans d'eau",
        icon="mdi:waves",
        category="ponds",
        key="ponds",
        matchers=["remplissage.+plan.* d.eau"]
    ),
    VigieEauSensorEntityDescription(
        name="Travaux sur cours d'eau",
        icon="mdi:hydro-power",
        category="river_rate",
        key="river_rate",
        matchers=["ouvrage.+cours d.eau","travaux.+cours d.eau"]
    ),
    VigieEauSensorEntityDescription(
        name="Arrosage des golfs",
        icon="mdi:golf",
        category="golfs",
        key="golfs",
        matchers=["arrosage des golfs"]
    ),
    VigieEauSensorEntityDescription(
        name="Prélèvement en canaux",
        icon="mdi:water-pump",
        category="canals",
        key="canals",
        matchers=["Prélèvement en canaux"]
    )
)

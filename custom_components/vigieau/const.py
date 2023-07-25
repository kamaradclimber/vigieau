DOMAIN = "vigieau"

BASE_URL = "https://api.vigieau.beta.gouv.fr"

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

SENSOR_DEFINITIONS = {
    "fountains": {
        "matchers": ["alimentation des fontaines publiques et privées"],
        "icon": "mdi:fountain",
        "name": "Alimentation des fontaines",
    },
    "potagers": {
        "matchers": ["Arrosage des jardins potagers", "Arrosage des potagers"],
        "icon": "mdi:watering-can",
        "name": "Arrosage des jardins potagers",
    },
    "roads": {
        "matchers": ["trottoirs"],
        "icon": "mdi:road",
        "name": "Arrosage voirie et trottoirs",
    },
    "lawn": {
        "matchers": ["pelouses", "jardins d'agrément", "massifs fleuris"],
        "icon": "mdi:sprinkler-variant",
        "name": "Arrosage des pelouses",
    },
    "car_wash": {
        "icon": "mdi:car-wash",
        "name": "Lavage des véhicules",
        "matchers": [
            "lavage.+particuliers",
            "lavage.+professionnels.+portique",
            "lavage.+professionnels.+haute pression",
            "lavage.+(station|véhicules)",
        ],
    },
    "nautical_vehicules": {
        "matchers": [
            "(lavage.+engins nautiques.+professionnels)|(Nettoyage.+embarcation)"
        ],
        "icon": "mdi:sail-boat",
        "name": "Lavage des engins nautiques",
    },
    "roof_clean": {
        "matchers": ["toitures"],
        "name": "Lavage des toitures",
        "icon": "mdi:home-roof",
    },
    "pool": {
        "matchers": [
            "remplissage.+piscines.+(familial|privé)",
            "vidange.+piscines",
            "piscines privées",  # "Piscines privées et bains à remous de plus de 1m3"
            "piscines non collectives",  # "Remplissage et vidange de piscines non collectives (de plus de 1 m3)"
        ],
        "icon": "mdi:pool",
        "name": "Vidange et remplissage des piscines",
    },
    "ponds": {
        "matchers": ["remplissage.+plan.* d.eau", "vidange.+plan.* d.eau"],
        "name": "Remplissage/Vidange des plans d'eau",
        "icon": "mdi:waves",
    },
    "river_rate": {
        "matchers": [
            "ouvrage.+cours d.eau",
            "travaux.+cours d.eau",
            "manoeuvre.+vannes",  # Manoeuvre de vannes des seuils et barrages
        ],
        "icon": "mdi:hydro-power",
        "name": "Travaux sur cours d'eau",
    },
    "golfs": {
        "matchers": ["arrosage des golfs"],
        "icon": "mdi:golf",
        "name": "Arrosage des golfs",
    },
    "canals": {
        "matchers": ["Prélèvement en canaux"],
        "icon": "mdi:water-pump",
        "name": "Prélèvement en canaux",
    },
}

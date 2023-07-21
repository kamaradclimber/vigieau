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
        "match0": "alimentation des fontaines publiques et privées",
        "icon": "mdi:fountain",
        "name": "Alimentation des fontaines",
    },
    "potagers": {
        "match0": "Arrosage des jardins potagers",
        "match1": "Arrosage des potagers",
        "icon": "mdi:watering-can",
        "name": "Arrosage des jardins potagers",
    },
    "lawn": {
        "match0": "pelouses",
        "match1": "jardins d'agrément",
        "icon": "mdi:sprinkler-variant",
        "name": "Arrosage des pelouses",
    },
    "car_wash": {
        "icon": "mdi:car-wash",
        "name": "Lavage des véhicules",
        "match0": "lavage.+particuliers",
        "match1": "lavage.+professionnels.+portique",
        "match2": "lavage.+professionnels.+haute pression",
        "match3": "lavage.+(station|véhicules)",
    },
    "nautical_vehicules": {
        "match0": "(lavage.+engins nautiques.+professionnels)|(Nettoyage.+embarcation)",
        "icon": "mdi:sail-boat",
        "name": "Lavage des engins nautiques",
    },
    "roof_clean": {
        "match0": "toitures",
        "name": "Lavage des toitures",
        "icon": "mdi:home-roof",
    },
    "pool": {
        "match0": "remplissage.+piscines.+(familial|privé)",
        "match1": "vidange.+piscines",
        "match2": "piscines privées",  # "Piscines privées et bains à remous de plus de 1m3"
        "match3": "piscines non collectives",  # "Remplissage et vidange de piscines non collectives (de plus de 1 m3)"
        "icon": "mdi:pool",
        "name": "Vidange et remplissage des piscines",
    },
    "ponds": {
        "match0": "remplissage.+plan.* d.eau",
        "name": "Remplissage des plans d'eau",
        "icon": "mdi:waves",
    },
    "river_rate": {
        "match0": "ouvrage.+cours d.eau",
        "match1": "travaux.+cours d.eau",
        "icon": "mdi:hydro-power",
        "name": "Travaux sur cours d'eau",
    },
    "golfs": {
        "match0": "arrosage des golfs",
        "icon": "mdi:golf",
        "name": "Arrosage des golfs",
    },
    "canals": {
        "match0": "Prélèvement en canaux",
        "icon": "mdi:water-pump",
        "name": "Prélèvement en canaux",
    },
}

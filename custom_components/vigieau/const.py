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
    "Alimentation des fontaines publiques et privées d'ornement ": {
        "icon": "mdi:fountain"
    },
    "Arrosage des jardins potagers": {"icon": "mdi:watering-can"},
    "Arrosage des pelouses, massifs fleuris": {"icon": "mdi:sprinkler-variant"},
    "Lavage de véhicules par les particuliers": {"icon": "mdi:car-wash"},
    "Lavage de véhicules par les professionnels avec portique à rouleaux": {
        "icon": "mdi:car-wash"
    },
    "Lavage de véhicules par les professionnels avec du matériel haute pression": {
        "icon": "mdi:car-wash"
    },
    "Nettoyage des façades, toitures, trottoirs et autres surfaces imperméabilisées": {},
    "Remplissage et vidange de piscines privées (de plus d'1 m3)": {"icon": "mdi:pool"},
    "Remplissage / vidange des plans d'eau": {},
    "Manoeuvre d’ouvrage sur le cours d’eau et affluents (biefs de moulin) hors plan d'eau": {
        "icon": "mdi:hydro-power"
    },
    "Travaux en cours d'eau": {},
}

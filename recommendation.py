import json

DATA_FILE = 'destinations.json'

def load_destinations_for_algo():
    """Charge dynamiquement les destinations depuis le fichier JSON mis à jour."""
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["destinations"]
    except Exception:
        return []

def calculer_categorie_budget(budget_total: float, nombre_jours: int) -> str:
    if nombre_jours <= 0:
        raise ValueError("La durée doit être d'au moins 1 jour.")
    budget_journalier = budget_total / nombre_jours
    if budget_journalier < 100:
        return 'éco'
    elif budget_journalier <= 300:
        return 'moyen'
    else:
        return 'élevé'

def scorer_destination(destination: dict, categorie_budget: str,
                       type_souhaite: str = None,
                       meteo_souhaitee: str = None) -> int:
    score = 0

    # ── Critère 1 : budget (40 points) ────────────────────────────────────
    ordre = ['éco', 'moyen', 'élevé']
    # Sécurité .get au cas où la catégorie budget est absente ou null
    dest_budget = destination.get('budget_categorie', 'moyen') or 'moyen'
    idx_dest   = ordre.index(dest_budget)
    idx_user   = ordre.index(categorie_budget)
    ecart      = abs(idx_dest - idx_user)

    if ecart == 0:
        score += 40
    elif ecart == 1:
        score += 20

    # ── Critère 2 : type de voyage (35 points) ────────────────────────────
    # Utilisation sécurisée de .get() pour éviter le KeyError: 'type' avec Montreal ou Tunis
    if type_souhaite and destination.get('type') == type_souhaite:
        score += 35

    # ── Critère 3 : météo souhaitée (25 points) ───────────────────────────
    # Utilisation sécurisée de .get() pour éviter le KeyError sur la météo
    if meteo_souhaitee and destination.get('meteo') == meteo_souhaitee:
        score += 25

    return score

def recommander(budget_total: float, nombre_jours: int,
               type_souhaite: str = None,
               meteo_souhaitee: str = None,
               top_n: int = 10) -> list[dict]: # Augmenté par défaut à 10 résultats max
    try:
        categorie_budget = calculer_categorie_budget(budget_total, nombre_jours)
    except ValueError as e:
        return {'erreur': str(e)}

    budget_journalier = budget_total / nombre_jours
    
    # On recharge les destinations fraîches du JSON pour l'algo
    destinations_actuelles = load_destinations_for_algo()

    resultats = []
    for destination in destinations_actuelles:
        score = scorer_destination(
            destination,
            categorie_budget,
            type_souhaite,
            meteo_souhaitee
        )
        resultats.append({
            'nom':               destination.get('nom'),
            'pays':              destination.get('pays'),
            'type':              destination.get('type'),
            'meteo':             destination.get('meteo'),
            'budget_categorie':  destination.get('budget_categorie'),
            'description':       destination.get('description'),
            'activites':         destination.get('activites', []),
            'score':             score,
            'budget_journalier': round(budget_journalier, 2)
        })

    # Tri par score décroissant
    resultats.sort(key=lambda x: x['score'], reverse=True)
    
    # Retourne les résultats sans la bride stricte des 5 premiers
    return resultats[:10]
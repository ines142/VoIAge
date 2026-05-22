from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from models import db, User, Trip
from recommendation import recommander
from flask import Flask, render_template, request, redirect, url_for, session, flash
from recommendation import recommander
import json
from flask import Flask, render_template, request, session, redirect, url_for, flash
from functools import wraps
import os
import json
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel.db'
app.config['SECRET_KEY'] = 'voya_ia_secret_key_99' # Garde une seule clé secrète

ADMIN_EMAIL = "vivelabretagne@22.fr" #mot de passe:stmalocesttropbeau
DATA_FILE = "destinations.json"

def load_destinations():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["destinations"]

def save_destinations(destinations: list):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"destinations": destinations}, f, ensure_ascii=False, indent=2)

def sauvegarder_planning_permanent(username, planning):
    tous_les_plannings = {}
    # Si le fichier existe déjà, on le lit pour ne pas effacer les autres utilisateurs
    if os.path.exists('itineraires_sauvegardes.json'):
        with open('itineraires_sauvegardes.json', 'r', encoding='utf-8') as f:
            tous_les_plannings = json.load(f)
    
    # On ajoute ou met à jour le planning de l'utilisateur actuel
    tous_les_plannings[username] = planning
    
    # On enregistre tout dans le fichier
    with open('itineraires_sauvegardes.json', 'w', encoding='utf-8') as f:
        json.dump(tous_les_plannings, f, indent=4, ensure_ascii=False)

def charger_planning_permanent(username):
    if os.path.exists('itineraires_sauvegardes.json'):
        with open('itineraires_sauvegardes.json', 'r', encoding='utf-8') as f:
            tous_les_plannings = json.load(f)
            return tous_les_plannings.get(username, {})
    return {}

app = Flask(__name__)
app.secret_key = "voya_ia_secret_key_99" # Indispensable pour les sessions
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///travel.db'
app.config['SECRET_KEY'] = 'votre_cle_secrete_ici'

db.init_app(app)
bcrypt = Bcrypt(app)

# Configuration de Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'          # redirige ici si page protégée
login_manager.login_message = "Connectez-vous pour accéder à cette page."

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()


# ─── Routes ───────────────────────────────────────────────
@app.route("/")
def index():
    destinations = load_destinations()
    # On filtre : on ne garde que les villes où a_la_une est True
    villes_vedettes = [d for d in destinations if d.get('a_la_une') == True]
    
    # On envoie ces villes à la page d'accueil
    return render_template("index.html", destinations=villes_vedettes)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name']
        email    = request.form['email']
        password = request.form['password']
        confirm  = request.form['confirm']

        if password != confirm:
            return render_template('register.html', error="Les mots de passe ne correspondent pas.")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template('register.html', error="Cet email est déjà utilisé.")

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(name=name, email=email, password=hashed_password)  # ← name ajouté
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        # Vérifie que l'utilisateur existe ET que le mot de passe correspond
        if not user or not bcrypt.check_password_hash(user.password, password):
            return render_template('login.html', error="Email ou mot de passe incorrect.")

        # L'utilisateur est validé ici
        login_user(user)

        # --- ÉTAPE 3 : ON RÉCUPÈRE SON PLANNING SAUVEGARDÉ ICI ---
        session['planning'] = charger_planning_permanent(user.name) # ou user.username selon ton modèle
        session.modified = True
        # -------------------------------------------------------

        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    # 1. On vide la session Flask-Login (si tu l'utilises)
    try:
        from flask_login import logout_user
        logout_user()
    except ImportError:
        pass # Si tu n'utilises pas Flask-Login, c'est pas grave

    # 2. On vide TOUTE la mémoire (user, planning, etc.)
    session.clear() 

    # 3. Petit message de confirmation
    flash("Vous avez été déconnecté. Votre itinéraire a été mis en sécurité.", "success")
    
    # 4. On finit par la redirection (toujours en dernier !)
    return redirect(url_for('index'))


@app.route('/trips')
@login_required                             # ← page protégée
def trips():
    all_trips = Trip.query.all()
    return render_template('dashboard.html', trips=all_trips)


@app.route('/recommandations', methods=['GET', 'POST'])
@login_required
def recommandations():
    if request.method == 'POST':
        jours_recu = request.form.get('nombre_jours')
        
        if jours_recu:
            session['nb_jours'] = int(jours_recu)
            
        # 1. Récupération des données du formulaire
        budget_brut = request.form.get('budget_total')
        jours_brut = request.form.get('nombre_jours')
        type_souhaite = request.form.get('type')
        meteo_souhaitee = request.form.get('meteo')

        # 2. SAUVEGARDE EN SESSION pour la page destination_detail
        if jours_brut and jours_brut.isdigit():
            session['nb_jours'] = int(jours_brut)
        else:
            session['nb_jours'] = 3

        # On charge les destinations en temps réel depuis le JSON pour le mode inspiration
        villes_disponibles = load_destinations()

        # MODE INSPIRATION (si budget ou jours sont vides)
        if not budget_brut or not jours_brut or budget_brut == "0" or jours_brut == "0":
            resultats = []
            for d in villes_disponibles:
                if meteo_souhaitee and d.get('meteo', '') != meteo_souhaitee:
                    continue
                if type_souhaite and d.get('type', '') != type_souhaite:
                    continue
                resultats.append(d)
            
            if not resultats:
                resultats = villes_disponibles[:10] # Affiche jusqu'à 10 destinations par défaut
                
            return render_template(
                'recommandations.html',
                destinations=resultats,
                mode="inspiration"
            )

        # MODE INTELLIGENT
        try:
            budget = float(budget_brut)
            jours = int(jours_brut)
        except ValueError:
            return render_template(
                'recommandations.html',
                erreur="Veuillez entrer des valeurs numériques valides."
            )

        resultats = recommander(
            budget_total=budget,
            nombre_jours=jours,
            type_souhaite=type_souhaite,
            meteo_souhaitee=meteo_souhaitee,
            top_n=10 # Demande d'afficher jusqu'à 10 villes max
        )

        if isinstance(resultats, dict) and 'erreur' in resultats:
            return render_template(
                'recommandations.html',
                erreur=resultats['erreur']
            )

        return render_template(
            'recommandations.html',
            destinations=resultats,
            mode="intelligent"
        )

    # Si c'est un simple GET (arrivée sur la page)
    return render_template('recommandations.html', destinations=None)
@app.route('/planifier', methods=['GET', 'POST'])
@login_required
def planifier():
    if request.method == 'POST':

        # ── Étape 1 : récupération brute des champs ───────────────────────
        raw_budget = request.form.get('budget_total', '').strip()
        raw_jours  = request.form.get('nombre_jours', '').strip()

        # ── Étape 2 : vérification que les champs ne sont pas vides ───────
        if not raw_budget or not raw_jours:
            flash("Tous les champs sont obligatoires.", 'error')
            return redirect(url_for('planifier'))

        # ── Étape 3 : conversion en nombres (protection texte → crash) ────
        try:
            budget_total = float(raw_budget)
            nombre_jours = int(raw_jours)
        except ValueError:
            flash("Le budget et la durée doivent être des nombres valides.", 'error')
            return redirect(url_for('planifier'))

        # ── Étape 4 : validation métier ───────────────────────────────────
        if nombre_jours <= 0:
            flash("La durée doit être d'au moins 1 jour.", 'error')
            return redirect(url_for('planifier'))

        if budget_total <= 0:
            flash("Le budget doit être supérieur à 0 €.", 'error')
            return redirect(url_for('planifier'))

        # ── Étape 5 : critères optionnels ─────────────────────────────────
        type_souhaite   = request.form.get('type') or None
        meteo_souhaitee = request.form.get('meteo') or None

        # ── Étape 6 : appel à l'algorithme ────────────────────────────────
        resultats = recommander(
            budget_total    = budget_total,
            nombre_jours    = nombre_jours,
            type_souhaite   = type_souhaite,
            meteo_souhaitee = meteo_souhaitee
        )

        # ── Étape 7 : gestion des retours d'erreur de recommander() ───────
        if isinstance(resultats, dict) and 'erreur' in resultats:
            flash(resultats['erreur'], 'error')
            return redirect(url_for('planifier'))

        if isinstance(resultats, dict) and 'aucun_resultat' in resultats:
            flash("Aucune destination ne correspond à vos critères. Essayez d'élargir votre recherche ✈️", 'warning')
            return redirect(url_for('planifier'))

        # ── Étape 8 : tout est bon → affichage des résultats ──────────────
        return render_template('planifier.html',
                               destinations=resultats,
                               budget_total=budget_total,
                               nombre_jours=nombre_jours)

    return render_template('planifier.html')

@app.route('/destination/<nom_ville>')
@login_required
def destination_detail(nom_ville):
    with open('destinations.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ville_trouvee = next((v for v in data['destinations'] if v['nom'].lower() == nom_ville.lower()), None)
    
    if not ville_trouvee:
        return redirect(url_for('index'))

    # --- RÉGLAGE FORCE ---
    # On cherche dans la session, sinon on regarde si l'utilisateur 
    # vient de faire une recherche (via referrer)
    nb_jours = session.get('nb_jours')
    
    if not nb_jours:
        # Si la session a buggé, on met 30 par défaut pour ne pas bloquer l'utilisateur
        nb_jours = 30
    
    return render_template('destination.html', 
                           destination=ville_trouvee, 
                           nb_jours=int(nb_jours))
    
@app.route('/itineraire')
@login_required
def afficher_itineraire():
    # On va chercher le planning directement dans le fichier JSON permanent de l'utilisateur
    planning = charger_planning_permanent(current_user.name) or {}
    
    try:
        with open('destinations.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        destinations_info = {v['nom']: v for v in data['destinations']}
    except Exception as e:
        print(f"Erreur lecture destinations.json : {e}")
        destinations_info = {}

    # On enrichit le planning avec les images et descriptions à la volée pour le template HTML
    for ville_nom, activites_liste in planning.items():
        if ville_nom in destinations_info:
            for act in activites_liste:
                idx = act.get('activite_index')
                if idx is not None and idx < len(destinations_info[ville_nom].get('activites', [])):
                    orig_act = destinations_info[ville_nom]['activites'][idx]
                    act['description'] = orig_act.get('description', '')
                    act['image_url'] = orig_act.get('image_url', '')

    # On remet à jour la session au passage pour garder le site synchro
    session['planning'] = planning

    return render_template('itineraire.html', 
                           planning=planning, 
                           destinations_info=destinations_info)

@app.route('/supprimer_activite/<nom_ville>/<int:activite_index>')
@login_required
def supprimer_activite(nom_ville, activite_index):
    # On vérifie que le planning existe
    if 'planning' in session:
        # On cherche la ville exacte (ex: "Tunis")
        if nom_ville in session['planning']:
            try:
                # On retire l'activité à l'index donné
                session['planning'][nom_ville].pop(activite_index)
                
                # Si la ville n'a plus aucune activité, on supprime la clé de la ville
                if not session['planning'][nom_ville]:
                    del session['planning'][nom_ville]
                
                session.modified = True
                # Sauvegarde dans ton JSON permanent
                sauvegarder_planning_permanent(current_user.name, session['planning'])
                flash(f"Activité de {nom_ville} supprimée.")
            except IndexError:
                flash("Erreur lors de la suppression.")
                
    return redirect(url_for('afficher_itineraire'))
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # On vérifie si l'utilisateur est admin via Flask-Login
        if not current_user.is_authenticated or current_user.email != ADMIN_EMAIL:
            flash("Accès refusé : réservé à l'administrateur.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function

import json

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        destinations = load_destinations()
        nouvelle_ville = {
            "nom": request.form.get("nom"),
            "image_url": request.form.get("image_url"),
            "phrase_accroche": request.form.get("phrase_accroche"),
            "histoire": request.form.get("histoire"),
            "culture": request.form.get("culture"),
            "note": request.form.get("note") or "4.8",
            "prenom_coeur": request.form.get("prenom_coeur"),
            "budget_categorie": request.form.get("budget") or "moyen",
            "a_la_une": True if request.form.get("a_la_une") else False,
            "type": request.form.get("type"),
            "meteo": request.form.get("meteo"),
            "activites": []
        }
        destinations.append(nouvelle_ville)
        save_destinations(destinations)
        return redirect(url_for('admin'))
    
    destinations = load_destinations()
    return render_template("admin.html", destinations=destinations)

@app.route("/admin/supprimer/<int:index>", methods=["POST"])
@admin_required
def admin_supprimer(index):
    destinations = load_destinations()
    if 0 <= index < len(destinations):
        nom = destinations[index]["nom"]
        destinations.pop(index)
        save_destinations(destinations)
        flash(f"🗑️ La destination « {nom} » a été supprimée.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/activites/<nom_ville>")
@admin_required
def admin_voir_activites(nom_ville):
    destinations = load_destinations()
    destination = next((d for d in destinations if d['nom'] == nom_ville), None)
    if not destination:
        return "Ville non trouvée", 404
    return render_template("admin_activites.html", dest=destination)

@app.route("/ajouter_activite/<nom_ville>")
@login_required
def ajouter_activite(nom_ville):
    activite_index = request.args.get("activite_index", type=int)
    jour = request.args.get("jour", default=1, type=int)

    # 1. Charger les destinations pour récupérer les infos de l'activité
    with open('destinations.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    ville_data = next((v for v in data['destinations'] if v['nom'].lower() == nom_ville.lower()), None)
    
    if not ville_data:
        flash("❌ Ville introuvable")
        return redirect(url_for('index'))

    if activite_index is None or activite_index < 0 or activite_index >= len(ville_data.get('activites', [])):
        flash("❌ Cette activité ne peut pas être ajoutée.")
        return redirect(url_for('destination_detail', nom_ville=nom_ville))

    activite = ville_data['activites'][activite_index]
    nom_propre_ville = ville_data['nom']

    # 2. Récupérer le planning PERMANENT existant de l'utilisateur
    # (Remplace 'charger_planning_permanent' par le nom exact de ta fonction si elle est différente)
    planning_global = charger_planning_permanent(current_user.name) or {}

    # Si la ville n'existe pas encore dans son planning, on la crée
    if nom_propre_ville not in planning_global:
        planning_global[nom_propre_ville] = []

    # On prépare l'activité (juste les infos légères, c'est plus propre)
    activite_a_sauver = {
        "nom": activite.get("nom", "Activité sans nom"),
        "tarif": activite.get("tarif", "Gratuit"),
        "intensite": activite.get("intensite", "Calme"),
        "jour": int(jour),
        "ville_nom": nom_propre_ville,
        "ville": nom_ville,
        "activite_index": activite_index
    }

    # On ajoute au planning global
    planning_global[nom_propre_ville].append(activite_a_sauver)
    
    # 3. Sauvegarde IMMEDIATE et permanente dans le fichier JSON global
    sauvegarder_planning_permanent(current_user.name, planning_global)

    # 4. On synchronise quand même la session pour l'affichage, 
    # mais sans risque puisque le vrai fichier prend le relais au besoin
    session['planning'] = planning_global
    session.modified = True
    # On garde le flash au cas où, mais on ajoute un marqueur fort dans l'URL :
    flash(f"✅ {activite_a_sauver['nom']} ajouté au Jour {jour} !")
    return redirect(url_for('destination_detail', nom_ville=nom_ville, succes=1, activite_nom=activite_a_sauver['nom']))

@app.route("/admin/activites/<nom_ville>/supprimer/<int:index>", methods=["POST"])
@admin_required
def admin_supprimer_activite(nom_ville, index):
    destinations = load_destinations()
    for d in destinations:
        if d['nom'] == nom_ville:
            if 0 <= index < len(d['activites']):
                d['activites'].pop(index)
                break
    
    save_destinations(destinations)
    flash("Activité supprimée.", "success")
    return redirect(url_for('admin_voir_activites', nom_ville=nom_ville))

@app.route("/admin/toggle_une/<int:index>")
@admin_required
def admin_toggle_une(index):
    destinations = load_destinations()
    if 0 <= index < len(destinations):
        actuel = destinations[index].get('a_la_une', False)
        destinations[index]['a_la_une'] = not actuel
        save_destinations(destinations)
        flash("Mise à jour de la mise en avant réussie", "success")
    return redirect(url_for('admin'))

@app.route("/admin/supprimer_ville/<int:index>", methods=["POST"])
@admin_required
def admin_supprimer_ville(index):
    destinations = load_destinations()
    if 0 <= index < len(destinations):
        destinations.pop(index)
        save_destinations(destinations)
        flash("Destination supprimée", "success")
    return redirect(url_for('admin'))

@app.route("/admin/modifier/<int:index>", methods=["GET", "POST"])
@admin_required
def admin_modifier_ville(index):
    destinations = load_destinations()
    ville = destinations[index]

    if request.method == "POST":
        ville["nom"] = request.form.get("nom")
        ville["description"] = request.form.get("description")
        ville["phrase_accroche"] = request.form.get("phrase_accroche")
        ville["pays"] = request.form.get("pays")
        ville["budget_categorie"] = request.form.get("budget")
        ville["type"] = request.form.get("type")
        ville["meteo"] = request.form.get("meteo")
        ville["prenom_coeur"] = request.form.get("prenom_coeur")

        bloc_expert_json = request.form.get("bloc_expert")
        if bloc_expert_json:
            try:
                donnees_complexes = json.loads(bloc_expert_json)
                ville["histoire"] = donnees_complexes.get("histoire", "")
                ville["culture"] = donnees_complexes.get("culture", "")
                ville["activites"] = donnees_complexes.get("activites", [])
            except Exception as e:
                print(f"Erreur de syntaxe JSON : {e}")

        save_destinations(destinations)
        return redirect(url_for("admin"))

    dictionnaire_expert = {
        "histoire": ville.get("histoire", ""),
        "culture": ville.get("culture", ""),
        "activites": ville.get("activites", [])
    }
    texte_expert_json = json.dumps(dictionnaire_expert, indent=4, ensure_ascii=False)
    
    # REPARATION DU RETOUR MANQUANT (Le bouton crayon remarche !)
    return render_template("admin_modifier.html", ville=ville, index=index, code_json=texte_expert_json)

@app.route("/admin/gerer-contenu/<string:nom_ville>", methods=["GET", "POST"])
@admin_required
def admin_gerer_contenu(nom_ville):
    destinations = load_destinations()
    
    ville = next((d for d in destinations if d['nom'] == nom_ville), None)
    if not ville:
        return redirect(url_for("admin"))

    if request.method == "POST":
        ville["histoire"] = request.form.get("histoire")
        ville["culture"] = request.form.get("culture")
        
        if "activites" in ville:
            for index, activite in enumerate(ville["activites"]):
                activite["nom"] = request.form.get(f"act_nom_{index}")
                activite["description"] = request.form.get(f"act_desc_{index}")
                activite["tarif"] = request.form.get(f"act_tarif_{index}")
                activite["jour"] = int(request.form.get(f"act_jour_{index}", 1))
                activite["intensite"] = request.form.get(f"act_intensite_{index}")
                # Sécurité : on garde l'image existante si le formulaire ne la modifie pas
                if f"act_image_{index}" in request.form:
                    activite["image_url"] = request.form.get(f"act_image_{index}")

        save_destinations(destinations)
        return redirect(url_for("admin"))

    return render_template("admin_gerer_contenu.html", ville=ville, nom_ville=nom_ville)
if __name__ == '__main__':
    app.run(debug=True)
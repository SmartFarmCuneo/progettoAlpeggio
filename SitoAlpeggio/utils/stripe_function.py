import stripe
from .db_connection import get_db_connection
from datetime import datetime, timedelta

# Solo il piano Free che non è su Stripe
SUBSCRIPTION_PLANS_CONFIG = {
    'free': {
        'name': 'Free',
        'features': [
            'Aggiunta fino a 3 campi',
            'Una irrigazione alla volta permessa',
            'Dati del terreno solamente quando il sensore è attivo',
        ]
    }
}

_stripe_plans_cache = None
_cache_timestamp = None
CACHE_DURATION = timedelta(hours=1)

############################# STRIPE HELPER FUNCTIONS #############################


def get_user_plan_limits(username):
    """Restituisce i limiti del piano dell'utente"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT p.* FROM plan_limits p 
                INNER JOIN users u ON p.plan_name = u.subscription_plan 
                WHERE u.username = %s
            """, (username,))
            return cursor.fetchone()
    except Exception as e:
        print(f"Errore nel recupero limiti piano: {e}")
        return None
    finally:
        conn.close()


def can_user_add_field(username):
    """Controlla se l'utente può aggiungere un nuovo campo"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT u.subscription_plan, p.max_fields,
                       (SELECT COUNT(*) FROM fields f WHERE f.id_user = u.id_u) as current_fields
                FROM users u 
                LEFT JOIN plan_limits p ON p.plan_name = u.subscription_plan 
                WHERE u.username = %s
            """, (username,))
            result = cursor.fetchone()

            if not result:
                return False

            max_fields = result['max_fields']
            current_fields = result['current_fields']

            # -1 significa illimitato
            return max_fields == -1 or current_fields < max_fields

    except Exception as e:
        print(f"Errore nel controllo limiti campi: {e}")
        return False
    finally:
        conn.close()


def get_user_subscription_info(username):
    """Restituisce informazioni complete sull'abbonamento dell'utente (approccio più robusto e debug)"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1) Leggiamo direttamente la riga utente
            cursor.execute(
                "SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            if not user:
                # nessun utente trovato
                print(
                    f"[get_user_subscription_info] user='{username}' non trovato nel DB")
                return None

            # 2) Normalizziamo il valore del piano per evitare mismatch (trim + lower + fallback 'free')
            raw_plan = user.get("subscription_plan") or "free"
            try:
                normalized_plan = str(raw_plan).strip().lower()
            except Exception:
                normalized_plan = "free"

            # 3) Recuperiamo i limiti del piano in maniera case-insensitive / trim
            try:
                cursor.execute(
                    "SELECT max_fields, max_sensors, has_ai_analysis, has_priority_support, has_custom_api "
                    "FROM plan_limits WHERE LOWER(TRIM(plan_name)) = %s",
                    (normalized_plan,)
                )
                plan = cursor.fetchone()
            except Exception as e:
                print(
                    f"[get_user_subscription_info] errore recupero plan_limits per '{normalized_plan}': {e}")
                plan = None

            # 4) Calcoliamo il numero corrente di campi dell'utente
            try:
                cursor.execute(
                    "SELECT COUNT(*) AS cnt FROM fields WHERE id_user = %s", (user['id_u'],))
                cnt_row = cursor.fetchone()
                current_fields = cnt_row['cnt'] if cnt_row else 0
            except Exception as e:
                print(
                    f"[get_user_subscription_info] errore conteggio fields per id_user={user.get('id_u')}: {e}")
                current_fields = 0

            # 5) Costruiamo il risultato coerente
            result = {
                'subscription_plan': normalized_plan,
                'subscription_status': user.get('subscription_status'),
                'subscription_start_date': user.get('subscription_start_date'),
                'subscription_end_date': user.get('subscription_end_date'),
                'stripe_customer_id': user.get('stripe_customer_id'),
                'max_fields': plan.get('max_fields') if plan else None,
                'max_sensors': plan.get('max_sensors') if plan else None,
                'has_ai_analysis': bool(plan.get('has_ai_analysis')) if plan else False,
                'has_priority_support': bool(plan.get('has_priority_support')) if plan else False,
                'has_custom_api': bool(plan.get('has_custom_api')) if plan else False,
                'current_fields': current_fields
            }

            # log utile per debug
            print(
                f"[get_user_subscription_info] user='{username}' raw_plan='{raw_plan}' normalized='{normalized_plan}' result_keys={list(result.keys())}")

            return result

    except Exception as e:
        import traceback
        print("[get_user_subscription_info] eccezione:", e)
        traceback.print_exc()
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def save_payment_history(user_id, payment_intent_id, amount, currency, plan_type, status):
    """Salva la cronologia dei pagamenti nel database"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO payment_history 
                (user_id, stripe_payment_intent_id, amount, currency, plan_type, payment_status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, payment_intent_id, amount, currency, plan_type, status))
            conn.commit()
    except Exception as e:
        print(f"Errore nel salvataggio cronologia pagamenti: {e}")
    finally:
        conn.close()


def get_all_plans_from_stripe(force_refresh=False):
    """
    Recupera TUTTI i piani da Stripe usando i metadata.
    Include cache per evitare troppe chiamate API.
    """
    global _stripe_plans_cache, _cache_timestamp

    now = datetime.now()

    # Usa la cache se valida
    if (not force_refresh and
        _stripe_plans_cache is not None and
        _cache_timestamp is not None and
            now - _cache_timestamp < CACHE_DURATION):
        return _stripe_plans_cache

    try:
        # Recupera tutti i prezzi attivi da Stripe
        prices = stripe.Price.list(
            active=True,
            expand=['data.product'],
            limit=100
        )

        plans = {}

        # Processa ogni prezzo
        for price in prices.data:
            metadata = price.metadata

            # Verifica che abbia il plan_key nei metadata
            plan_key = metadata.get('plan_key')
            if not plan_key:
                continue

            # Estrai le feature dai metadata
            features = []
            i = 1
            while f'feature_{i}' in metadata:
                features.append(metadata[f'feature_{i}'])
                i += 1

            # Costruisci il piano
            plans[plan_key] = {
                'name': metadata.get('plan_name', plan_key.capitalize()),
                'price': price.unit_amount / 100,
                'currency': price.currency,
                'interval': price.recurring['interval'] if price.recurring else 'month',
                'stripe_price_id': price.id,
                'stripe_product_id': price.product if isinstance(price.product, str) else price.product.id,
                'features': features
            }

        # Aggiungi il piano Free (non è su Stripe)
        plans['free'] = {
            'name': SUBSCRIPTION_PLANS_CONFIG['free']['name'],
            'price': 0,
            'currency': 'eur',
            'interval': 'month',
            'stripe_price_id': None,
            'stripe_product_id': None,
            'features': SUBSCRIPTION_PLANS_CONFIG['free']['features']
        }

        # Aggiorna cache
        _stripe_plans_cache = plans
        _cache_timestamp = now

        print(f"[Stripe] Recuperati {len(plans)} piani da Stripe")
        return plans

    except stripe.error.StripeError as e:
        print(f"Errore Stripe nel recupero piani: {e}")

        # Se c'è una cache precedente, usala
        if _stripe_plans_cache:
            print("[Stripe] Uso cache precedente per errore API")
            return _stripe_plans_cache

        # Fallback: almeno il piano free
        return {
            'free': {
                'name': SUBSCRIPTION_PLANS_CONFIG['free']['name'],
                'price': 0,
                'currency': 'eur',
                'interval': 'month',
                'stripe_price_id': None,
                'stripe_product_id': None,
                'features': SUBSCRIPTION_PLANS_CONFIG['free']['features']
            }
        }
    except Exception as e:
        print(f"Errore generico nel recupero piani: {e}")
        import traceback
        traceback.print_exc()

        # Ritorna almeno il free
        return {
            'free': SUBSCRIPTION_PLANS_CONFIG['free']
        }


def get_plan_by_key(plan_key, force_refresh=False):
    """
    Recupera un singolo piano per chiave
    """
    plans = get_all_plans_from_stripe(force_refresh)
    return plans.get(plan_key)


def clear_plans_cache():
    """
    Svuota la cache dei piani
    """
    global _stripe_plans_cache, _cache_timestamp
    _stripe_plans_cache = None
    _cache_timestamp = None
    print("[Stripe] Cache piani svuotata")


def get_stripe_price_id_by_plan_key(plan_key):
    """
    Recupera il Price ID di Stripe dato un plan_key
    """
    plan = get_plan_by_key(plan_key)
    if plan:
        return plan.get('stripe_price_id')
    return None

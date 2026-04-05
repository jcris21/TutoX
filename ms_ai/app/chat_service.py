import json
import logging
import re
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from .embeddings import embed_text
from .exercise_manager import get_step
from .models import ChatResponse, TutorState
from .redis_manager import redis_manager
from .vectordb import get_chroma_collection
from ms_ai.app.models import llm


logger = logging.getLogger(__name__)


# =========================
# STATE
# =========================

# Avoid repeated LLM calls
_MODEL_LABEL_CACHE: dict[str, str] = {}

# Broad “technical id” pattern to block leakage in output (e.g., stock.warehouse.orderpoint)
_TECH_ID_PATTERN = re.compile(r"\b[a-z_]+(?:\.[a-z0-9_]+){1,}\b", re.IGNORECASE)


# =========================
# ENTRYPOINT
# =========================

async def process_chat(
    *,
    session_id: str,
    message: str,
    context_model: str = "unknown",
) -> ChatResponse:
    try:
        logger.info(
            f"[PROCESS_CHAT] session={session_id} "
            f"message='{message}' context_model={context_model}"
        )

        session = await redis_manager.get_session(session_id) or {}

        if "context" in session and isinstance(session["context"], dict):
            session["context"]["model"] = context_model

        initial_state = {
            **session,
            "session_id": session_id,
            "message": message,
            "context_model": context_model,
        }

        if message.strip():
            initial_state["lang"] = detect_language(message)

        result = await tutor_graph.ainvoke(initial_state)

        await redis_manager.update_session(
            session_id,
            {
                "context_model": result.get("context_model", context_model),
                "context": {"model": result.get("context_model", context_model)},
                **{
                    k: result[k]
                    for k in (
                        "mode",
                        "exercise_id",
                        "required_module",
                        "current_step",
                        "paused",
                        "last_known_module",
                        "lang",
                        "exercise_document",
                        "pending_exercise_id",
                        "pending_required_module",
                        "pending_exercise_document",
                        "pending_goal",
                        "pending_distance",
                        "pending_user_msg",
                    )
                    if k in result
                },
            },
        )

        response_text = result.get("response") or ""

        return ChatResponse(
            response=response_text,
            exercise_id=result.get("exercise_id"),
            current_step=result.get("current_step"),
        )

    except Exception:
        logger.error("Error in process_chat", exc_info=True)
        return ChatResponse(
            response="I encountered an error processing your message.",
            exercise_id=None,
            current_step=None,
            fallback=True,
        )
    
MESSAGES = {
    "clarify_request": {
        "en": "Please clarify your request.",
        "es": "¿Puedes aclarar tu solicitud?",
    },
    "exercise_cancelled": {
        "en": "Okay, exercise cancelled.",
        "es": "Listo, ejercicio cancelado.",
    },
    "exercise_completed": {
        "en": "Exercise completed.",
        "es": "Ejercicio completado.",
    },
    "please_open_app": {
        "en": "Please open the {app} app.",
        "es": "Por favor abre la app {app}.",
    },
    "please_return_app": {
        "en": "Please return to the {app} app.",
        "es": "Por favor vuelve a la app {app}.",
    },
    "confirm_step_by_step": {
        "en": "Do you want step-by-step instructions for {goal}?",
        "es": "¿Quieres instrucciones paso a paso para {goal}?",
    },
}


class _SafeDict(dict):
    def __missing__(self, key):
        return "this app"


# =========================
# HELPERS
# =========================


def t(key: str, lang: str, **kwargs) -> str:
    lang = lang if lang in ("en", "es") else "en"
    template = MESSAGES.get(key, {}).get(lang) or MESSAGES.get(key, {}).get("en") or key
    return template.format_map(_SafeDict(**kwargs))


def normalize_required(required: Optional[str]) -> Optional[str]:
    """
    Normalises a required module/model value coming from steps/session state.

    Returns None when the value is empty or whitespace-only, so the rest of the
    tutor logic can treat it as "no requirement".
    """
    if required is None:
        return None
    required = required.strip()
    return required or None


def detect_language(text: str) -> str:
    t = (text or "").strip().lower()
    if not t:
        return "en"

    # Strong signals (characters)
    if "¿" in t or "¡" in t or "ñ" in t:
        return "es"

    # Token-based detection (handles start/end of string)
    tokens = set(re.findall(r"[a-záéíóúüñ]+", t))

    spanish_tokens = {
        "que",
        "como",
        "donde",
        "por",
        "qué",
        "porque",
        "para",
        "puedes",
        "ayuda",
        "ventas",
        "inventario",
        "factura",
        "presupuesto",
        "modulo",
        "módulo",
        "encuentro",
        "indicar",
        "crear",
        "regla",
    }

    if tokens & spanish_tokens:
        return "es"

    return "en"


async def awaiting_resume_confirmation_node(state: TutorState):
    msg = (state.get("message") or "").strip()
    lang = state["lang"]

    # 1) Explicit cancel → delete session (destructive)
    if is_cancel(msg):
        await redis_manager.delete_session(state["session_id"])
        return {
            "mode": "idle",
            "response": t("exercise_cancelled", lang),
        }
    # 2) Allow switching from resume prompt
    candidate = await find_best_exercise_candidate(msg, lang)
    if should_offer_switch(state.get("exercise_id"), candidate):
        return {
            "mode": "awaiting_exercise_switch",
            "pending_exercise_id": candidate["exercise_id"],
            "pending_required_module": candidate["required_module"],
            "pending_exercise_document": candidate["exercise_document"],
            "pending_goal": candidate["goal"],
            "pending_distance": candidate["distance"],
            "pending_user_msg": msg,
            "response": (
                f"I found another exercise: {candidate['goal']}.\n"
                "Do you want to switch? (switch / continue / cancel)"
                if lang == "en"
                else f"Encontré otro ejercicio: {candidate['goal']}.\n"
                "¿Quieres cambiar? (cambiar / continuar / cancelar)"
            ),
        }
    
    # 3) Yes/continue → resume at the same step
    if is_yes(msg) or is_next(msg):

        step_index = state.get("current_step") or 0
        step = get_step(state, step_index)

        if not step:
            return {
                "mode": "idle",
                "response": "Exercise step not found.",
            }

        return {
            "mode": "exercise_active",
            "paused": False,
            "response": step.get("instruction"),
            "required_module": step.get("validation_steps", {}).get("required_module"),
            "step_id": step.get("step_id"),
        }

    # 4) No/later → pause (non-destructive, keep progress)
    if is_no_or_pause(msg):
        return {
            "mode": "paused_exercise",
            "paused": True,
            "response": (
                "Okay, I’ll pause the exercise. Say “continue” when you want to resume."
                if lang == "en"
                else "Perfecto, pauso el ejercicio. Di “continuar” cuando quieras retomarlo."
            ),
        }

    # 5) Unclear → re-prompt
    return {
        "mode": "awaiting_resume_confirmation",
        "response": (
            "Do you want to continue the exercise? (yes / later / cancel)"
            if lang == "en"
            else "¿Quieres continuar el ejercicio? (sí / más tarde / cancelar)"
        ),
    }


def is_yes(message: str) -> bool:
    return message.strip().lower() in {
        "yes",
        "y",
        "yeah",
        "yep",
        "sí",
        "si",
        "s",
        "sure",
    }


def is_next(message: str) -> bool:
    msg = (message or "").strip().lower()
    return msg in {
        "next",
        "n",
        "continue",
        "go on",
        "done",
        "proceed",
        "siguiente",
        "sig",
        "continuar",
        "continua",
        "listo",
        "hecho",
        "dale",
    }


def is_cancel(message: str) -> bool:
    """User explicitly wants to end/reset the exercise."""
    msg = (message or "").strip().lower()
    if not msg:
        return False

    patterns = [
        # English
        r"\bcancel\b",
        r"\bquit\b",
        r"\bexit\b",
        r"\bend exercise\b",
        r"\bcancel exercise\b",
        r"\bstop exercise\b",
        # Spanish
        r"\bcancelar\b",
        r"\bsalir\b",
        r"\bterminar\b",
        r"\bcancelar ejercicio\b",
        r"\bsalir del ejercicio\b",
        r"\bterminar ejercicio\b",
    ]
    return any(re.search(p, msg) for p in patterns)


def is_no_or_pause(message: str) -> bool:
    """User wants to stop for now but keep progress."""
    msg = (message or "").strip().lower()
    if not msg:
        return False

    patterns = [
        # English
        r"\bnot now\b",
        r"\blater\b",
        r"\bstop for now\b",
        r"\bpause\b",
        # Spanish
        r"\bahora no\b",
        r"\bmás tarde\b",
        r"\bmas tarde\b",
        r"\bluego\b",
        r"\bdespués\b",
        r"\bdespues\b",
        r"\bpausa\b",
    ]
    return any(re.search(p, msg) for p in patterns)

async def general_tutor_response(
    *,
    message: str,
    context_model: str | None,
) -> str:
    lang = detect_language(message)

    system_prompt = (
        "You are an expert Odoo tutor for Odoo version 18.\n"
        "Answer clearly and practically.\n"
        "If the user asks HOW to do something, explain it.\n"
        "If they ask WHAT something is, explain its purpose.\n"
        "Keep answers concise but helpful.\n"
    )

    if lang == "es":
        system_prompt += (
            "\nIMPORTANT: The user is speaking Spanish.\n"
            "Answer ONLY in clear, neutral Spanish.\n"
            "Do NOT mix languages.\n"
            "Do NOT use English technical jargon unless unavoidable.\n"
        )
    else:
        system_prompt += "\nIMPORTANT: Answer ONLY in English.\n"

    friendly_label = "This Screen"
    if context_model:
        friendly_label = (
            await normalize_model_name(
                llm=llm,
                model=context_model,
                lang=lang,
            )
            or friendly_label
        )

    system_prompt += (
        f"\nCurrent screen context: {friendly_label}\n"
        "IMPORTANT:\n"
        "- Never reveal technical model identifiers.\n"
        "- If asked about the model, answer using the user-facing screen name instead.\n"
        "- Make sure to mention a short explanation of the module not to long.\n"
        "- Only use user-facing screen names.\n"
        "- If unsure, say 'this screen'.\n"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=message),
    ]

    response = await llm.ainvoke(messages)
    return response.content.strip()


async def find_best_exercise_candidate(user_msg: str, lang: str):
    if not user_msg.strip():
        return None

    collection = get_chroma_collection("exercises_structured")
    user_embedding = await embed_text(user_msg)

    results = collection.query(
        query_embeddings=[user_embedding],
        n_results=3,
        include=["metadatas", "distances"],
    )

    ids = results.get("ids", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not ids or not distances:
        return None

    best_index = min(range(len(distances)), key=lambda i: distances[i])
    best_id = ids[best_index]
    best_meta = metadatas[best_index]
    best_dist = distances[best_index]

    # Parse doc_json
    best_doc_json = None
    doc_json_raw = best_meta.get("doc_json")
    if doc_json_raw:
        try:
            best_doc_json = json.loads(doc_json_raw)
        except Exception:
            best_doc_json = None

    # Goal
    raw_goal = best_meta.get("goal")
    if isinstance(raw_goal, dict):
        goal = raw_goal.get(lang) or raw_goal.get("en") or "this exercise"
    elif isinstance(raw_goal, str):
        goal = raw_goal
    else:
        goal = "this exercise"

    required_module = (
        best_meta.get("required_module")
        or (best_meta.get("required_modules") or [None])[0]
    )

    return {
        "exercise_id": best_id,
        "distance": float(best_dist),
        "required_module": required_module,
        "exercise_document": json.dumps(best_doc_json) if best_doc_json else None,
        "goal": goal,
    }


def should_offer_switch(
    current_exercise_id: str | None, candidate: dict | None
) -> bool:
    if not candidate:
        return False
    if not candidate.get("exercise_id"):
        return False
    if current_exercise_id and candidate["exercise_id"] == current_exercise_id:
        return False

    # Stricter than idle MAX_DISTANCE (0.80)
    SWITCH_DISTANCE = 0.65
    return candidate["distance"] <= SWITCH_DISTANCE


def _clean_label(s: str) -> str:
    """Normalize whitespace, strip quotes, remove trailing punctuation."""
    s = (s or "").strip().strip('"').strip("'")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"[.!,;:]+$", "", s).strip()
    return s


def _is_bad_label(s: str) -> bool:
    """Reject if empty, too long, or still contains technical identifiers."""
    if not s:
        return True
    if len(s) > 40:
        return True
    if _TECH_ID_PATTERN.search(s):
        return True
    # If it looks like a sentence, reject
    if any(ch in s for ch in ["\n", "→"]) or len(s.split()) > 4:
        return True
    return False


# =========================
# NODES
# =========================


async def normalize_model_name(
    *,
    llm,
    model: Optional[str],
    lang: str = "en",
    use_cache: bool = True,
) -> Optional[str]:
    if not model:
        return None

    m = model.strip().lower()
    if not m:
        return None

    if use_cache and m in _MODEL_LABEL_CACHE:
        return _MODEL_LABEL_CACHE[m]

    system = (
        "You are a strict Odoo UI label app normalizer.\n"
        "You convert Odoo technical identifiers into short, user-facing UI app names.\n"
        "Input will be:\n"
        "- a technical model name (e.g., 'stock.picking')\n"
        "Output rules:\n"
        "- Output ONLY the label for the official app name in odoo, nothing else.\n"
        "- No explanations, no punctuation at the end.\n"
        "- Title Case.\n"
        "- Keep it short (1 word).\n"
        "- NEVER output any technical identifier like 'stock.picking' or 'sale.order'.\n"
        "- If you are unsure, output exactly: This Screen\n"
    )

    if lang == "es":
        system += (
            "\nThe user language is Spanish.\n"
            "Output the label in Spanish.\n"
            "If unsure, output exactly: Esta pantalla\n"
        )

    examples = (
        "Examples:\n"
        "stock.warehouse.orderpoint -> Inventory\n"
        "sale.order -> Sales\n"
        "purchase.order -> Purchases\n"
        "stock.picking -> Inventory\n"
        "account.move -> Accounting\n"
        "mrp.production -> Manufacturing\n"
        "mrp.bom ->  Manufacturing\n"
        "\n"
        "Module examples:\n"
        "sale -> Sales\n"
        "stock -> Inventory\n"
        "purchase -> Purchases\n"
        "account -> Accounting\n"
        "mrp -> Manufacturing\n"
        "project -> Project\n"
        "crm -> CRM\n"
    )

    user = f"{examples}\nInput:\n{m}\nLabel:"

    resp = await llm.ainvoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )

    label = _clean_label(getattr(resp, "content", "") or "")
    if _is_bad_label(label):
        label = "Esta pantalla" if lang == "es" else "This Screen"

    if use_cache:
        _MODEL_LABEL_CACHE[m] = label

    return label


async def load_session(state: TutorState):
    session = await redis_manager.get_session(state["session_id"]) or {}

    # Sticky context
    if "context" in session and not state.get("context_model"):
        ctx = session.get("context")
        if isinstance(ctx, dict):
            state["context_model"] = ctx.get("model")

    # Sticky language
    if session.get("lang") and not state.get("lang"):
        state["lang"] = session["lang"]
    elif not state.get("lang"):
        state["lang"] = detect_language(state.get("message", ""))

    return {**session, **state}


async def idle_node(state: TutorState):
    user_msg = (state.get("message") or "").strip()
    lang = state.get("lang") or "en"

    # Silent on context-only events
    if not user_msg:
        return {"mode": "idle", "response": None}

    # 1) Get structured collection
    collection = get_chroma_collection("exercises_structured")

    # 2) Generate user embedding
    user_embedding = await embed_text(user_msg)

    # 3) Query ANN
    results = collection.query(
        query_embeddings=[user_embedding],
        n_results=3,
        include=["metadatas", "documents", "distances"],
    )

    ids = (results.get("ids") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    # No candidates → general answer
    if not ids or not distances:
        response = await general_tutor_response(
            message=user_msg,
            context_model=state.get("context_model"),
        )
        return {
            "mode": "idle",
            "response": response.strip(),
        }

    # Select best candidate
    best_index = min(range(len(distances)), key=lambda i: distances[i])
    best_dist = distances[best_index]

    MAX_DISTANCE = 0.80

    # Too far → general answer
    if best_dist > MAX_DISTANCE:
        response = await general_tutor_response(
            message=user_msg,
            context_model=state.get("context_model"),
        )
        return {
            "mode": "idle",
            "response": response.strip(),
        }

    # Valid exercise match
    best_id = ids[best_index]
    best_meta = metadatas[best_index] or {}

    # Parse doc_json safely
    best_doc_json = None
    doc_json_raw = best_meta.get("doc_json")
    if doc_json_raw:
        try:
            best_doc_json = (
                doc_json_raw
                if isinstance(doc_json_raw, dict)
                else json.loads(doc_json_raw)
            )
        except Exception:
            best_doc_json = None

    # Extract goal
    raw_goal = best_meta.get("goal")
    if isinstance(raw_goal, dict):
        goal = raw_goal.get(lang) or raw_goal.get("en") or ""
    elif isinstance(raw_goal, str):
        goal = raw_goal
    else:
        goal = "this exercise"

    required_module = (
        best_meta.get("required_module")
        or (best_meta.get("required_modules") or [None])[0]
    )

    return {
        "mode": "awaiting_confirmation",
        "exercise_id": best_id,
        "required_module": required_module,
        "exercise_document": json.dumps(best_doc_json) if best_doc_json else None,
        "response": t(
            "confirm_step_by_step",
            lang,
            goal=goal,
        ),
    }


async def awaiting_confirmation_node(state: TutorState):
    msg = (state.get("message") or "").strip()
    lang = state["lang"]

    if is_cancel(msg):
        await redis_manager.delete_session(state["session_id"])
        return {"mode": "idle", "response": t("exercise_cancelled", lang)}

    if is_yes(msg):
        return {"mode": "module_gate"}

    # NEW: check if this message matches another exercise strongly
    candidate = await find_best_exercise_candidate(msg, lang)
    if should_offer_switch(state.get("exercise_id"), candidate):
        return {
            "mode": "awaiting_exercise_switch",
            "pending_exercise_id": candidate["exercise_id"],
            "pending_required_module": candidate["required_module"],
            "pending_exercise_document": candidate["exercise_document"],
            "pending_goal": candidate["goal"],
            "pending_distance": candidate["distance"],
            "pending_user_msg": msg,
            "response": (
                f"It looks like you’re asking for a different exercise: {candidate['goal']}.\n"
                "Do you want to switch? (switch / continue / cancel)"
                if lang == "en"
                else f"Parece que estás pidiendo otro ejercicio: {candidate['goal']}.\n"
                "¿Quieres cambiar? (cambiar / continuar / cancelar)"
            ),
        }

    # Otherwise: treat as "no"
    await redis_manager.delete_session(state["session_id"])
    return {"mode": "idle", "response": t("exercise_cancelled", lang)}


# Check if user is in the required module, if any. If not, prompt to open it. If yes, start exercise.
async def module_gate_node(state: TutorState):

    lang = state["lang"]

    current_model = normalize_required(state.get("context_model"))
    step_index = state.get("current_step") or 0

    step = get_step(state, step_index)

    if not step:
        return {"mode": "idle", "response": "Exercise not found."}

    required = normalize_required(
        step.get("validation_steps", {}).get("required_module")
    )   

    # If module requirement exists and user is not there yet
    if required and current_model != required:

        app_label = await normalize_model_name(
            llm=llm,
            model=required,
            lang=lang,
        ) or ("This screen" if lang == "en" else "Esta pantalla")

        return {
            "mode": "module_gate",
            "current_step": step_index,
            "required_module": required,
            "response": t("please_open_app", lang, app=app_label),
        }

    # Correct module → start exercise
    return {
        "mode": "exercise_active",
        "current_step": step_index,
        "required_module": required,
        "response": step.get("instruction"),
    }

async def exercise_active_node(state: TutorState):
    
    msg = (state.get("message") or "").strip()
    lang = state["lang"]

    if is_cancel(msg):
        await redis_manager.delete_session(state["session_id"])
        return {"mode": "idle", "response": t("exercise_cancelled", lang)}

    if is_next(msg) or is_yes(msg):
        next_step = state.get("current_step", 0) + 1

        step = get_step(state, next_step)

        if not step:
            await redis_manager.delete_session(state["session_id"])
            return {
                "mode": "idle",
                "response": t("exercise_completed", lang),
            }

        required_module = (
            step.get("validation_steps", {}).get("required_module")
        )

        return {
            "mode": "exercise_active",
            "current_step": next_step,
            "required_module": normalize_required(required_module),
            "response": step.get("instruction"),
        }

    # Try switching
    candidate = await find_best_exercise_candidate(msg, lang)
    if should_offer_switch(state.get("exercise_id"), candidate):
        return {
            "mode": "awaiting_exercise_switch",
            "pending_exercise_id": candidate["exercise_id"],
            "pending_required_module": candidate["required_module"],
            "pending_exercise_document": candidate["exercise_document"],
            "pending_goal": candidate["goal"],
            "pending_distance": candidate["distance"],
            "pending_user_msg": msg,
            "response": (
                f"You're currently doing an exercise. I think you're asking for a different one: {candidate['goal']}.\n"
                "Do you want to switch? (switch / continue / cancel)"
                if lang == "en"
                else f"Estás haciendo un ejercicio. Creo que estás pidiendo otro: {candidate['goal']}.\n"
                "¿Quieres cambiar? (cambiar / continuar / cancelar)"
            ),
        }

    # Otherwise, route to detour
    return {
        "mode": "exercise_detour",
        "detour_question": msg,
    }


async def paused_exercise_node(state: TutorState):
    msg = (state.get("message") or "").strip()
    lang = state["lang"]

    if is_cancel(msg):
        await redis_manager.delete_session(state["session_id"])
        return {"mode": "idle", "response": t("exercise_cancelled", lang)}

    # Allow switching while paused
    candidate = await find_best_exercise_candidate(msg, lang)
    if should_offer_switch(state.get("exercise_id"), candidate):
        return {
            "mode": "awaiting_exercise_switch",
            "pending_exercise_id": candidate["exercise_id"],
            "pending_required_module": candidate["required_module"],
            "pending_exercise_document": candidate["exercise_document"],
            "pending_goal": candidate["goal"],
            "pending_distance": candidate["distance"],
            "pending_user_msg": msg,
            "response": (
                f"You’re in the middle of an exercise. I found another one: {candidate['goal']}.\n"
                "Do you want to switch? (switch / continue / cancel)"
                if lang == "en"
                else f"Estás en medio de un ejercicio. Encontré otro: {candidate['goal']}.\n"
                "¿Quieres cambiar? (cambiar / continuar / cancelar)"
            ),
        }

    if is_yes(msg) or is_next(msg):

        step_index = state.get("current_step") or 0
        step = get_step(state, step_index)

        if not step:
            await redis_manager.delete_session(state["session_id"])
            return {"mode": "idle", "response": "Exercise not found."}

        required = normalize_required(
            step.get("validation_steps", {}).get("required_module")
        )
        current = normalize_required(state.get("context_model"))

        if required and current != required:
            return {
                "mode": "module_gate",
                "paused": True,
                "current_step": step_index,
                "required_module": required,
                "response": t("please_return_app", lang),
            }

        return {
            "mode": "exercise_active",
            "paused": False,
            "current_step": step_index,
            "required_module": required,
            "response": step.get("instruction"),
        }

    return {
        "mode": "paused_exercise",
        "paused": True,
        "response": (
            "Exercise is paused. Say “continue” to resume or “cancel” to end it."
            if lang == "en"
            else "El ejercicio está en pausa. Di “continuar” para retomarlo o “cancelar” para terminarlo."
        ),
    }


async def exercise_detour_node(state: TutorState):
    question = state.get("detour_question") or ""
    current_step = state.get("current_step") or 0
    lang = state.get("lang") or "en"

    raw_doc = state.get("exercise_document")

    goal = ""
    step_text = ""

    if raw_doc:
        try:
            parsed = json.loads(raw_doc)

            document = parsed

            # Extract goal
            raw_goal = document.get("goal")
            if isinstance(raw_goal, dict):
                goal = raw_goal.get(lang) or raw_goal.get("en") or ""
            elif isinstance(raw_goal, str):
                goal = raw_goal

            # Extract current step
            steps = document.get("steps", [])
            if 0 <= current_step < len(steps):
                step_text = steps[current_step].get("instruction", "")

        except Exception as e:
            logger.error(f"[DETOUR_PARSE_ERROR] {e}")

    system_prompt = f"""
You are helping the user during an Odoo exercise.

Exercise goal:
{goal}

Current module:
{state.get("required_module")}

Current step:
{step_text}

The user asked:
"{question}"

If the question is related to this exercise or step, answer in that specific context.
Do NOT give generic Odoo explanations if the question clearly refers to this step.
Keep it concise and practical.

Answer the question clearly. Do NOT ask any follow-up questions.
"""

    messages = [
        SystemMessage(content=system_prompt.strip()),
        HumanMessage(content=question),
    ]

    response = await llm.ainvoke(messages)
    answer = response.content.strip()

    continue_prompt = (
        "Do you want to continue the exercise?"
        if lang == "en"
        else "¿Quieres continuar el ejercicio?"
    )

    return {
        "mode": "awaiting_resume_confirmation",
        "response": f"{answer}\n\n{continue_prompt}",
    }


def is_switch(message: str) -> bool:
    msg = message.strip().lower()
    return msg in {"switch", "change", "start new", "new one", "cambiar"}


def is_continue_current(message: str) -> bool:
    msg = (message or "").strip().lower()
    return msg in {"continue", "keep", "no", "n", "stay"}


async def awaiting_exercise_switch_node(state: TutorState):
    msg = (state.get("message") or "").strip()
    lang = state["lang"]

    if is_cancel(msg):
        await redis_manager.delete_session(state["session_id"])
        return {"mode": "idle", "response": t("exercise_cancelled", lang)}

    if is_switch(msg):
        if not state.get("pending_exercise_id"):
            # corrupted state fallback
            await redis_manager.delete_session(state["session_id"])
            return {
                "mode": "idle",
                "response": (
                    "Something went wrong. Please ask for the exercise again."
                    if lang == "en"
                    else "Algo salió mal. Por favor pide el ejercicio nuevamente."
                ),
            }

        # Replace current exercise with pending
        state["exercise_id"] = state.get("pending_exercise_id")
        state["required_module"] = state.get("pending_required_module")
        state["exercise_document"] = state.get("pending_exercise_document")
        state["current_step"] = 0
        state["paused"] = False

        return {
            "mode": "module_gate",
            "exercise_id": state["exercise_id"],
            "required_module": state["required_module"],
            "exercise_document": state["exercise_document"],
            "current_step": 0,
            "paused": False,
            # clear pending
            "pending_exercise_id": None,
            "pending_required_module": None,
            "pending_exercise_document": None,
            "pending_goal": None,
            "pending_distance": None,
            "pending_user_msg": None,
        }

    if is_continue_current(msg):
        return {
            "mode": "exercise_active",
            "pending_exercise_id": None,
            "pending_required_module": None,
            "pending_exercise_document": None,
            "pending_goal": None,
            "pending_distance": None,
            "pending_user_msg": None,
            "response": (
                "Okay—continuing the current exercise. If you want, say “switch” to start the other exercise."
                if lang == "en"
                else "Perfecto—seguimos con el ejercicio actual. Si quieres, di “cambiar” para iniciar el otro."
            ),
        }

    # Re-prompt
    goal = state.get("pending_goal") or "that exercise"
    return {
        "mode": "awaiting_exercise_switch",
        "response": (
            f"You’re in the middle of an exercise. I found another exercise about: {goal}.\n"
            "Do you want to switch? (switch / continue / cancel)"
            if lang == "en"
            else f"Estás en medio de un ejercicio. Encontré otro ejercicio sobre: {goal}.\n"
            "¿Quieres cambiar? (cambiar / continuar / cancelar)"
        ),
    }


# =========================
# GRAPH
# =========================

graph = StateGraph(TutorState)

# =========================
# NODES
# =========================

graph.add_node("load_session", load_session)
graph.add_node("idle", idle_node)
graph.add_node("awaiting_confirmation", awaiting_confirmation_node)
graph.add_node("module_gate", module_gate_node)
graph.add_node("exercise_active", exercise_active_node)
graph.add_node("paused_exercise", paused_exercise_node)
graph.add_node("exercise_detour", exercise_detour_node)
graph.add_node("awaiting_resume_confirmation", awaiting_resume_confirmation_node)
graph.add_node("awaiting_exercise_switch", awaiting_exercise_switch_node)

# =========================
# ENTRY POINT
# =========================

graph.set_entry_point("load_session")

# =========================
# ROUTING
# =========================

graph.add_conditional_edges(
    "load_session",
    lambda s: s.get("mode", "idle"),
    {
        "idle": "idle",
        "awaiting_confirmation": "awaiting_confirmation",
        "module_gate": "module_gate",
        "exercise_active": "exercise_active",
        "paused_exercise": "paused_exercise",
        "exercise_detour": "exercise_detour",
        "awaiting_resume_confirmation": "awaiting_resume_confirmation",
        "awaiting_exercise_switch": "awaiting_exercise_switch",
    },
)

graph.add_edge("exercise_detour", END)
graph.add_edge("awaiting_exercise_switch", END)

graph.add_conditional_edges(
    "awaiting_confirmation",
    lambda s: s.get("mode"),
    {
        "module_gate": "module_gate",
        "idle": "idle",
        "awaiting_exercise_switch": "awaiting_exercise_switch",
    },
)

graph.add_conditional_edges(
    "awaiting_resume_confirmation",
    lambda s: s.get("mode"),
    {
        "exercise_active": "exercise_active",
        "paused_exercise": "paused_exercise",
        "awaiting_resume_confirmation": "awaiting_resume_confirmation",
        "idle": "idle",
    },
)

graph.add_conditional_edges(
    "module_gate",
    lambda s: s.get("mode"),
    {
        "module_gate": END,
        "exercise_active": END,
        "idle": "idle",
    },
)

graph.add_conditional_edges(
    "paused_exercise",
    lambda s: s.get("mode"),
    {
        "idle": "idle",
        "exercise_active": "exercise_active",
    },
)

graph.add_edge("idle", END)

graph.add_conditional_edges(
    "exercise_active",
    lambda s: s.get("mode"),
    {
        "exercise_active": END,
        "exercise_detour": "exercise_detour",
        "paused_exercise": END,
        "idle": END,
    },
)


# =========================
# COMPILE
# =========================

tutor_graph = graph.compile()

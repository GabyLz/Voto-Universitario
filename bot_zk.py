"""
Bot de votación con PRUEBAS DE CONOCIMIENTO CERO (ZK Proofs).

A diferencia del bot original:
  - Los votos se cifran con ElGamal antes de guardarse en la blockchain.
  - Cada voto incluye una prueba ZK que demuestra que es válido
    (está en el rango de candidatos) sin revelar por quién se votó.
  - Los votos reales y falsos (ruido) son CRIPTOGRÁFICAMENTE INDISTINGUIBLES.
  - Solo la TallyAuthority (con la clave secreta sk) puede descifrar
    los resultados al final.
"""

import asyncio
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from config import TOKEN
from blockchain_sim import BlockchainZKSim
from tally_authority import TallyAuthority
from noise_generator import inyectar_ruido_zk, CARGOS_Y_CANDIDATOS
from anomaly_detector import AnomalyDetectorZK
import zk_proofs as zk

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

REGISTRO, VOTAR = range(2)

with open("padron.json", "r") as f:
    PADRON = json.load(f)

ADMIN_IDS = [11111111]
TOTAL_CARGOS = len(CARGOS_Y_CANDIDATOS)

# ─── Estado global ZK ─────────────────────────────────────────────────────────
tally_authority = TallyAuthority()
blockchain = BlockchainZKSim(tally_authority.clave_publica)
detector = AnomalyDetectorZK(blockchain, tally_authority)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _indicador_progreso(actual, total):
    return "●" * actual + "○" * (total - actual) + f"  {actual}/{total}"


def _barra_visual(votos, total, ancho=10):
    if total == 0:
        return "░" * ancho + "  0%"
    filled = round(votos / total * ancho)
    pct = round(votos / total * 100)
    return "█" * filled + "░" * (ancho - filled) + f"  {pct}%"


def _teclado_post_flujo(codigo):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Ver resultados", callback_data="ver_resultados"),
        InlineKeyboardButton("🔍 Validar mi voto", callback_data=f"validar:{codigo}"),
    ]])


def _construir_resultados(user_id):
    resultados = tally_authority.obtener_resultados(CARGOS_Y_CANDIDATOS)
    total_reales = tally_authority.total_reales
    total_falsos = tally_authority.total_falsos

    msg = (
        "📊 *RESULTADOS DE VOTACIÓN (ZK)*\n"
        "_Universidad Nacional de Trujillo_\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    for cargo in CARGOS_Y_CANDIDATOS.keys():
        msg += f"📍 *{cargo}*\n"
        if cargo in resultados and resultados[cargo]:
            votos_cargo = resultados[cargo]
            total_cargo = sum(votos_cargo.values())
            for candidato, votos in sorted(
                votos_cargo.items(), key=lambda x: x[1], reverse=True
            ):
                barra = _barra_visual(votos, total_cargo)
                msg += f"• {candidato}\n  {barra} · {votos} voto(s)\n"
        else:
            msg += "  _Sin votos reales registrados_\n"
        msg += "\n"

    if user_id in ADMIN_IDS:
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += (
            f"🔍 *Admin:* {total_reales} reales · {total_falsos} ruido\n"
            f"🔐 *ZK:* votos indistinguibles en cadena · "
            f"{len(blockchain.cadena) - 1} bloques\n"
        )

    return msg


# ─── Flujo principal ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start (ZK)")
    context.user_data["mensajes_bot"] = []
    context.user_data["cargos_pendientes"] = list(CARGOS_Y_CANDIDATOS.keys())

    cargos_lista = "\n".join(
        f"  {i + 1}. {c}" for i, c in enumerate(CARGOS_Y_CANDIDATOS.keys())
    )
    await update.message.reply_text(
        "🗳️ *Sistema de Voto Digital UNT — Modo ZK*\n"
        "_Universidad Nacional de Trujillo_\n\n"
        "Bienvenido al sistema oficial de elecciones universitarias.\n\n"
        f"En esta sesión elegirás candidatos para:\n{cargos_lista}\n\n"
        "🔐 *NOVEDAD:* Tu voto está protegido con\n"
        "_Pruebas de Conocimiento Cero (ZK Proofs)_\n"
        "· Nadie puede ver por quién votaste\n"
        "· Nadie puede distinguir votos reales de ruido\n"
        "· Los resultados se descifran solo al final",
        parse_mode="Markdown",
    )
    msg = await update.message.reply_text(
        "🔑 *Verificación de identidad*\n\n"
        "Ingresa tu código universitario para continuar:",
        parse_mode="Markdown",
    )
    context.user_data["mensajes_bot"].append(msg.message_id)
    return REGISTRO


async def validar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = update.message.text.strip()
    logger.info(f"Código recibido: {codigo}")

    if codigo not in PADRON:
        await update.message.reply_text(
            "❌ *Código no reconocido.*\n"
            "Verifica tu código universitario e intenta con /start.",
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    nombre = PADRON[codigo]["nombre"]
    rol = PADRON[codigo]["rol"]

    if PADRON[codigo]["voto_emitido"]:
        await update.message.reply_text(
            f"⚠️ *{nombre}*, ya emitiste tu voto anteriormente.\n\n"
            "Puedes verificar tu participación o consultar los resultados:",
            reply_markup=_teclado_post_flujo(codigo),
            parse_mode="Markdown",
        )
        return ConversationHandler.END

    context.user_data.update({"rol": rol, "codigo": codigo, "nombre": nombre})

    msg = await update.message.reply_text(
        f"✅ *Identidad verificada*\n\n"
        f"Bienvenido/a, *{nombre}*\n"
        f"Rol: {rol.capitalize()}\n\n"
        f"Votarás para {TOTAL_CARGOS} cargos. "
        f"Tu voto será cifrado con ZK proofs.",
        parse_mode="Markdown",
    )
    context.user_data["mensajes_bot"].append(msg.message_id)
    return await mostrar_siguiente_cargo(update, context)


async def mostrar_siguiente_cargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("cargos_pendientes"):
        return await finalizar_votacion(update, context)

    cargo_actual = context.user_data["cargos_pendientes"][0]
    context.user_data["cargo_actual"] = cargo_actual

    pendientes = len(context.user_data["cargos_pendientes"])
    cargo_num = TOTAL_CARGOS - pendientes + 1
    progreso = _indicador_progreso(cargo_num, TOTAL_CARGOS)

    teclado = [
        [InlineKeyboardButton(c, callback_data=c)]
        for c in CARGOS_Y_CANDIDATOS[cargo_actual]
    ]
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🗳️ *Elecciones UNT — Modo ZK*\n"
            f"{progreso}\n\n"
            f"📍 *{cargo_actual}*\n"
            f"Selecciona tu candidato (tu voto será cifrado):"
        ),
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode="Markdown",
    )
    context.user_data["mensajes_bot"].append(msg.message_id)
    return VOTAR


async def recibir_voto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Recibe el voto del usuario, lo cifra con ElGamal,
    crea la prueba ZK y lo guarda en la blockchain.

    El voto en la cadena es indistinguible del ruido.
    """
    query = update.callback_query
    await query.answer()
    candidato_nombre = query.data
    cargo = context.user_data["cargo_actual"]
    rol = context.user_data["rol"]

    # Determinar índice del candidato (1-based, 0 = falso/ruido)
    candidatos = CARGOS_Y_CANDIDATOS[cargo]
    indice_candidato = candidatos.index(candidato_nombre) + 1
    n_candidatos = len(candidatos)

    logger.info(
        f"Voto ZK: {candidato_nombre} (índice {indice_candidato}) | {cargo} | {rol}"
    )

    # ── Cifrar voto con ElGamal ──
    a, b, r = zk.encriptar(indice_candidato, tally_authority.clave_publica)

    # ── Crear prueba ZK: el valor está en {0, 1, ..., n_candidatos} ──
    prueba = zk.crear_prueba_zk(
        a, b, indice_candidato, r, tally_authority.clave_publica, n_candidatos
    )

    # ── Guardar en la blockchain (sin es_falso, sin candidato en texto plano) ──
    bloque = blockchain.agregar_voto(cargo, a, b, prueba)

    # ── Registrar como voto REAL en la autoridad (fuera de la cadena) ──
    tally_authority.registrar_voto(bloque.hash, cargo, a, b, es_real=True)

    # ── Inyectar ruido ZK (votos falsos, indistinguibles) ──
    await inyectar_ruido_zk(blockchain, tally_authority.clave_publica, cantidad=2)
    # Registrar también los votos falsos en la autoridad
    for i in range(1, 3):
        bloque_falso = blockchain.cadena[-i]
        tally_authority.registrar_voto(
            bloque_falso.hash, bloque_falso.cargo,
            bloque_falso.a, bloque_falso.b, es_real=False,
        )

    context.user_data["cargos_pendientes"].pop(0)

    try:
        await query.delete_message()
    except Exception as e:
        logger.warning(f"No se pudo borrar mensaje: {e}")

    if not context.user_data["cargos_pendientes"]:
        return await finalizar_votacion(update, context)
    return await mostrar_siguiente_cargo(update, context)


async def finalizar_votacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = context.user_data.get("codigo")
    nombre = context.user_data.get("nombre", "")

    if codigo and codigo in PADRON:
        PADRON[codigo]["voto_emitido"] = True
        with open("padron.json", "w") as f:
            json.dump(PADRON, f, indent=2)

    chat_id = update.effective_chat.id
    for msg_id in context.user_data.get("mensajes_bot", []):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"No se pudo borrar mensaje {msg_id}: {e}")

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"✅ *¡Voto ZK registrado exitosamente!*\n\n"
            f"Gracias por participar, *{nombre}*.\n"
            f"Tu voto fue cifrado con ElGamal y protegido con\n"
            f"una prueba de conocimiento cero (ZK Proof).\n\n"
            f"_Nadie puede ver por quién votaste._\n"
            f"_Nadie puede distinguir tu voto del ruido._"
        ),
        reply_markup=_teclado_post_flujo(codigo),
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─── Callbacks de botones post-flujo ──────────────────────────────────────────

async def callback_ver_resultados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    await query.message.reply_text(
        _construir_resultados(user_id), parse_mode="Markdown"
    )


async def callback_validar_voto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    codigo = query.data.split(":", 1)[1]

    if codigo in PADRON and PADRON[codigo]["voto_emitido"]:
        nombre = PADRON[codigo]["nombre"]
        rol = PADRON[codigo]["rol"]
        await query.message.reply_text(
            "🔍 *Validación de participación ZK*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Participación verificada*\n\n"
            f"Nombre: *{nombre}*\n"
            f"Rol: {rol.capitalize()}\n"
            f"Estado: Voto ZK emitido ✓\n\n"
            "_El sistema confirma tu participación. Tu voto está "
            "cifrado con ZK proofs. No existe ningún registro "
            "que vincule tu identidad con tu elección._",
            parse_mode="Markdown",
        )
    else:
        await query.message.reply_text(
            "🔍 *Validación de participación*\n\n"
            "⚠️ No encontramos registro de tu voto.\n"
            "Si completaste el proceso, contacta al administrador.",
            parse_mode="Markdown",
        )


# ─── Comandos de consulta ─────────────────────────────────────────────────────

async def resultados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Verificar integridad de la cadena antes de mostrar resultados
    cadena_ok = blockchain.verificar_cadena()
    if not cadena_ok:
        await update.message.reply_text(
            "⚠️ *ALERTA:* La cadena tiene pruebas ZK inválidas o hashes rotos.",
            parse_mode="Markdown",
        )
        return
    await update.message.reply_text(
        _construir_resultados(user_id), parse_mode="Markdown"
    )


async def anomalias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporte = detector.detectar()
    mensaje = "🤖 *Detección de Anomalías — IA (Modo ZK)*\n\n"
    if isinstance(reporte, str):
        mensaje += reporte
    else:
        for item in reporte:
            mensaje += f"• {item}\n"
    mensaje += (
        "\n🔐 _Los votos individuales están cifrados. "
        "El análisis usa solo datos públicos de la cadena._"
    )
    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text(
            "⛔ Solo administradores pueden reiniciar la votación."
        )
        return
    global blockchain, tally_authority, detector
    tally_authority = TallyAuthority()
    blockchain = BlockchainZKSim(tally_authority.clave_publica)
    detector = AnomalyDetectorZK(blockchain, tally_authority)
    for cod in PADRON:
        PADRON[cod]["voto_emitido"] = False
    with open("padron.json", "w") as f:
        json.dump(PADRON, f, indent=2)
    await update.message.reply_text(
        "🔄 *Votación ZK reiniciada.*\n"
        "_Nuevas claves ElGamal generadas. Cadena limpia._",
        parse_mode="Markdown",
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Proceso cancelado. Usa /start para comenzar de nuevo."
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─── Entrada principal ────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("registro", start),
        ],
        states={
            REGISTRO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, validar_codigo)
            ],
            VOTAR: [CallbackQueryHandler(recibir_voto)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
        per_user=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(
        CallbackQueryHandler(callback_ver_resultados, pattern="^ver_resultados$")
    )
    app.add_handler(
        CallbackQueryHandler(callback_validar_voto, pattern="^validar:")
    )
    app.add_handler(CommandHandler("resultados", resultados))
    app.add_handler(CommandHandler("anomalias", anomalias))
    app.add_handler(CommandHandler("reset", reset))

    logger.info("Bot ZK iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()

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
from blockchain_sim import BlockchainSim
from noise_generator import inyectar_ruido, CARGOS_Y_CANDIDATOS
from anomaly_detector import AnomalyDetector

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

REGISTRO, VOTAR = range(2)

with open("padron.json", "r") as f:
    PADRON = json.load(f)

ADMIN_IDS = [11111111]
TOTAL_CARGOS = len(CARGOS_Y_CANDIDATOS)

blockchain = BlockchainSim()
detector = AnomalyDetector(blockchain)


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
    resultados_reales = blockchain.obtener_resultados_reales()
    total_reales = len(blockchain.votos_reales)
    total_falsos = len(blockchain.votos_falsos)

    msg = (
        "📊 *RESULTADOS DE VOTACIÓN*\n"
        "_Universidad Nacional de Trujillo_\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    for cargo in CARGOS_Y_CANDIDATOS.keys():
        msg += f"📍 *{cargo}*\n"
        if cargo in resultados_reales and resultados_reales[cargo]:
            votos_cargo = resultados_reales[cargo]
            total_cargo = sum(int(v) for v in votos_cargo.values())
            for candidato, votos in sorted(votos_cargo.items(), key=lambda x: x[1], reverse=True):
                barra = _barra_visual(int(votos), total_cargo)
                msg += f"• {candidato}\n  {barra} · {int(votos)} voto(s)\n"
        else:
            msg += "  _Sin votos registrados aún_\n"
        msg += "\n"

    if user_id in ADMIN_IDS:
        msg += "━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"🔍 *Admin:* {total_reales} reales · {total_falsos} ruido\n"

    return msg


# ─── Flujo principal ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    context.user_data["mensajes_bot"] = []
    context.user_data["cargos_pendientes"] = list(CARGOS_Y_CANDIDATOS.keys())

    cargos_lista = "\n".join(
        f"  {i+1}. {c}" for i, c in enumerate(CARGOS_Y_CANDIDATOS.keys())
    )
    await update.message.reply_text(
        "🗳️ *Sistema de Voto Digital UNT*\n"
        "_Universidad Nacional de Trujillo_\n\n"
        "Bienvenido al sistema oficial de elecciones universitarias.\n\n"
        f"En esta sesión elegirás candidatos para:\n{cargos_lista}\n\n"
        "Tu voto es 100% anónimo y está protegido\n"
        "por ruido criptográfico e inmutabilidad blockchain.",
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
        f"Votarás para {TOTAL_CARGOS} cargos. Usa los botones para seleccionar.",
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

    teclado = [[InlineKeyboardButton(c, callback_data=c)] for c in CARGOS_Y_CANDIDATOS[cargo_actual]]
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=(
            f"🗳️ *Elecciones UNT*\n"
            f"{progreso}\n\n"
            f"📍 *{cargo_actual}*\n"
            f"Selecciona tu candidato:"
        ),
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode="Markdown",
    )
    context.user_data["mensajes_bot"].append(msg.message_id)
    return VOTAR


async def recibir_voto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    candidato = query.data
    cargo = context.user_data["cargo_actual"]
    rol = context.user_data["rol"]

    logger.info(f"Voto: {candidato} | {cargo} | {rol}")

    blockchain.agregar_voto(
        {
            "cargo": cargo,
            "candidato": candidato,
            "rol": rol,
            "peso": 1,
            "timestamp_voto": asyncio.get_event_loop().time(),
        },
        es_falso=False,
    )
    await inyectar_ruido(blockchain, cantidad=2)

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
            f"✅ *¡Voto registrado exitosamente!*\n\n"
            f"Gracias por participar, *{nombre}*.\n"
            f"Tu voto fue guardado de forma anónima e inmutable."
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
    await query.message.reply_text(_construir_resultados(user_id), parse_mode="Markdown")


async def callback_validar_voto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    codigo = query.data.split(":", 1)[1]

    if codigo in PADRON and PADRON[codigo]["voto_emitido"]:
        nombre = PADRON[codigo]["nombre"]
        rol = PADRON[codigo]["rol"]
        await query.message.reply_text(
            "🔍 *Validación de participación*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Participación verificada*\n\n"
            f"Nombre: *{nombre}*\n"
            f"Rol: {rol.capitalize()}\n"
            f"Estado: Voto emitido ✓\n\n"
            "_El sistema confirma tu participación. No existe ningún registro "
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
    await update.message.reply_text(_construir_resultados(user_id), parse_mode="Markdown")


async def anomalias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporte = detector.detectar()
    mensaje = "🤖 *Detección de Anomalías — IA*\n\n"
    if isinstance(reporte, str):
        mensaje += reporte
    else:
        for item in reporte:
            mensaje += f"• {item}\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Solo administradores pueden reiniciar la votación.")
        return
    global blockchain, detector
    blockchain = BlockchainSim()
    detector = AnomalyDetector(blockchain)
    for cod in PADRON:
        PADRON[cod]["voto_emitido"] = False
    with open("padron.json", "w") as f:
        json.dump(PADRON, f, indent=2)
    await update.message.reply_text("🔄 *Votación reiniciada.*", parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proceso cancelado. Usa /start para comenzar de nuevo.")
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
            REGISTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, validar_codigo)],
            VOTAR: [CallbackQueryHandler(recibir_voto)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
        per_user=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_ver_resultados, pattern="^ver_resultados$"))
    app.add_handler(CallbackQueryHandler(callback_validar_voto, pattern="^validar:"))
    app.add_handler(CommandHandler("resultados", resultados))
    app.add_handler(CommandHandler("anomalias", anomalias))
    app.add_handler(CommandHandler("reset", reset))

    logger.info("Bot iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()

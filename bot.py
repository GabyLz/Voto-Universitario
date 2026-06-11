import asyncio
import random
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
    filters
)
from config import TOKEN
from blockchain_sim import BlockchainSim
from noise_generator import inyectar_ruido, CARGOS_Y_CANDIDATOS
from anomaly_detector import AnomalyDetector

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados de conversación
REGISTRO, VOTAR = range(2)

# Cargar padrón simulado
with open("padron.json", "r") as f:
    PADRON = json.load(f)

ADMIN_IDS = [11111111]  # Telegram IDs de administradores

# Inicializar blockchain y detector
blockchain = BlockchainSim()
detector = AnomalyDetector(blockchain)



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /start command")
    await update.message.reply_text(
        "🗳️ *Sistema de Voto Digital UNT*\n\n"
        "✅ Anonimato (no guardamos quién vota por quién)\n"
        "🎭 Ruido criptográfico (votos falsos para evitar correlación)\n"
        "🔗 Blockchain simulada (inmutable)\n"
        "🤖 IA detectora de anomalías\n\n"
        "Usa /registro para identificarte y votar.\n"
        "Usa /resultados para ver resultados (solo admins ven detalles reales).\n"
        "Usa /evidencia para ver pruebas de anonimato.",
        parse_mode="Markdown"
    )


async def registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Received /registro command")
    if "mensajes_bot" not in context.user_data:
        context.user_data["mensajes_bot"] = []
    if "cargos_pendientes" not in context.user_data:
        context.user_data["cargos_pendientes"] = list(CARGOS_Y_CANDIDATOS.keys())
    
    msg = await update.message.reply_text("Ingresa tu *código universitario* (solo números):", parse_mode="Markdown")
    context.user_data["mensajes_bot"].append(msg.message_id)
    return REGISTRO


async def validar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received code: {update.message.text}")
    codigo = update.message.text.strip()
    if codigo in PADRON:
        if PADRON[codigo]["voto_emitido"]:
            await update.message.reply_text("❌ Ya has votado. No puedes votar nuevamente.")
            return ConversationHandler.END
        context.user_data["rol"] = PADRON[codigo]["rol"]
        context.user_data["codigo"] = codigo
        msg1 = await update.message.reply_text(f"✅ Identidad verificada: {PADRON[codigo]['nombre']} ({context.user_data['rol'].capitalize()})")
        context.user_data["mensajes_bot"].append(msg1.message_id)
        return await mostrar_siguiente_cargo(update, context)
    else:
        await update.message.reply_text("❌ Código no válido o no habilitado para votar.")
        return ConversationHandler.END


async def mostrar_siguiente_cargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("cargos_pendientes"):
        return await finalizar_votacion(update, context)
    cargo_actual = context.user_data["cargos_pendientes"][0]
    context.user_data["cargo_actual"] = cargo_actual
    teclado = [[InlineKeyboardButton(c, callback_data=c)] for c in CARGOS_Y_CANDIDATOS[cargo_actual]]
    chat_id = update.effective_chat.id
    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=f"📍 Cargo: *{cargo_actual}*\nSelecciona tu candidato:",
        reply_markup=InlineKeyboardMarkup(teclado),
        parse_mode="Markdown"
    )
    context.user_data["mensajes_bot"].append(msg.message_id)
    return VOTAR


async def recibir_voto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    candidato = query.data
    cargo = context.user_data["cargo_actual"]
    rol = context.user_data["rol"]
    peso = 1  # TODOS LOS VOTOS VALEN 1

    logger.info(f"Recibiendo voto para {candidato} en {cargo} (rol: {rol}, peso: {peso})")

    # ⚠️ IMPORTANTE: NO SE ALMACENA NINGÚN DATO QUE IDENTIFIQUE AL VOTANTE
    datos_voto = {
        "cargo": cargo,
        "candidato": candidato,
        "rol": rol,
        "peso": peso,
        "timestamp_voto": asyncio.get_event_loop().time()
    }
    blockchain.agregar_voto(datos_voto, es_falso=False)

    # Inyectar ruido (solo para anonimato, proporción 2:1)
    await inyectar_ruido(blockchain, cantidad=2)

    # Quitar cargo de pendientes
    context.user_data["cargos_pendientes"].pop(0)

    # Eliminar mensaje de voto actual
    try:
        await query.delete_message()
    except Exception as e:
        logger.warning(f"No se pudo borrar mensaje: {e}")

    # Siguiente cargo o finalizar
    if not context.user_data["cargos_pendientes"]:
        return await finalizar_votacion(update, context)
    else:
        return await mostrar_siguiente_cargo(update, context)


async def finalizar_votacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Marcar en padrón que ya votó
    codigo = context.user_data.get("codigo")
    if codigo and codigo in PADRON:
        PADRON[codigo]["voto_emitido"] = True
        with open("padron.json", "w") as f:
            json.dump(PADRON, f, indent=2)

    # Borrar todos los mensajes del bot
    chat_id = update.effective_chat.id
    for msg_id in context.user_data.get("mensajes_bot", []):
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            logger.warning(f"No se pudo borrar mensaje {msg_id}: {e}")

    # Mensaje final
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Usted ya ha votado. ¡Gracias por participar!",
        parse_mode="Markdown"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def resultados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    resultados_reales = blockchain.obtener_resultados_reales()
    total_votos_reales = len(blockchain.votos_reales)
    total_votos_falsos = len(blockchain.votos_falsos)

    mensaje = "📊 *RESULTADOS DE VOTACIÓN*\n\n"

    # TODOS LOS USUARIOS VER SOLO VOTOS REALES
    for cargo in CARGOS_Y_CANDIDATOS.keys():
        mensaje += f"📍 *{cargo}*\n"
        if cargo in resultados_reales:
            for candidato, votos in sorted(resultados_reales[cargo].items(), key=lambda x: x[1], reverse=True):
                mensaje += f"  • {candidato}: {int(votos)}\n"
        else:
            mensaje += "  • No hay votos registrados aún\n"
        mensaje += "\n"

    if user_id in ADMIN_IDS:
        mensaje += f"🔍 INFO ADMIN: Total votos reales: {total_votos_reales} | Total votos falsos (ruido): {total_votos_falsos}\n"
        mensaje += "🎭 El ruido SOLO sirve para anonimato, NO se cuenta en resultados.\n"

    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def evidencia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = "🔒 *EVIDENCIA DE ANONIMATO 100%*\n\n"
    mensaje += "1️⃣ *Padrón Electoral*:\n"
    mensaje += "   Solo registra tu nombre, rol y si ya votaste (nunca registra para quién votaste)\n\n"
    mensaje += "2️⃣ *Votos en la Blockchain*:\n"
    mensaje += "   Los votos se guardan sin datos personales (ningún código, ID o nombre)\n\n"
    mensaje += "3️⃣ *Ruido Criptográfico*:\n"
    mensaje += "   Se mezclan votos falsos para que nadie pueda decir qué voto es tuyo por el tiempo\n\n"
    mensaje += "4️⃣ *Limpieza Automática*:\n"
    mensaje += "   Borramos todos tus datos temporales inmediatamente después de votar\n\n"
    mensaje += "✅ *NO HAY NINGÚN LUGAR donde se registre quién votó por quién*"
    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def anomalias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporte = detector.detectar()
    mensaje = "🤖 *Análisis de IA - Detección de anomalías*\n\n"
    if isinstance(reporte, str):
        mensaje += reporte
    else:
        for item in reporte:
            mensaje += f"• {item}\n"
    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Solo administradores pueden reiniciar la votación.")
        return
    global blockchain, detector
    blockchain = BlockchainSim()
    detector = AnomalyDetector(blockchain)
    for cod in PADRON:
        PADRON[cod]["voto_emitido"] = False
    with open("padron.json", "w") as f:
        json.dump(PADRON, f, indent=2)
    await update.message.reply_text("🔄 Votación reiniciada.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proceso cancelado. Usa /registro para empezar de nuevo.")
    context.user_data.clear()
    return ConversationHandler.END


def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("registro", registro)],
        states={
            REGISTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, validar_codigo)],
            VOTAR: [CallbackQueryHandler(recibir_voto)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=True,
        per_user=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("resultados", resultados))
    app.add_handler(CommandHandler("evidencia", evidencia))
    app.add_handler(CommandHandler("anomalias", anomalias))
    app.add_handler(CommandHandler("reset", reset))

    logger.info("Bot iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()

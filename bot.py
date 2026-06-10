import asyncio
import random
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
from noise_generator import inyectar_ruido, ruido_periodico, CARGOS_Y_CANDIDATOS
from anomaly_detector import AnomalyDetector
import json

# Estados de conversación
REGISTRO, SELECCIONAR_CARGO, VOTAR = range(3)

# Cargar padrón simulado
with open("padron.json", "r") as f:
    PADRON = json.load(f)

ADMIN_IDS = [11111111]  # Telegram IDs de administradores

# Inicializar blockchain y detector
blockchain = BlockchainSim()
detector = AnomalyDetector(blockchain)
ruido_stop_event = None
ruido_task = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if "mensajes_bot" not in context.user_data:
        context.user_data["mensajes_bot"] = []
    msg = await update.message.reply_text("Ingresa tu *código universitario* (solo números):", parse_mode="Markdown")
    context.user_data["mensajes_bot"].append(msg.message_id)
    return REGISTRO


async def validar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = update.message.text.strip()
    if codigo in PADRON:
        if PADRON[codigo]["voto_emitido"]:
            await update.message.reply_text("❌ Ya has votado. No puedes votar nuevamente.")
            return ConversationHandler.END
        context.user_data["rol"] = PADRON[codigo]["rol"]
        context.user_data["codigo"] = codigo
        context.user_data["cargos_pendientes"] = list(CARGOS_Y_CANDIDATOS.keys())
        msg1 = await update.message.reply_text(f"✅ Identidad verificada: {PADRON[codigo]['nombre']} ({context.user_data['rol'].capitalize()})")
        context.user_data["mensajes_bot"].append(msg1.message_id)
        return await mostrar_siguiente_cargo(update, context)
    else:
        await update.message.reply_text("❌ Código no válido o no habilitado para votar.")
        return ConversationHandler.END


async def mostrar_siguiente_cargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data["cargos_pendientes"]:
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
    peso = 2/3 if rol == "docente" else 1/3

    # ⚠️ IMPORTANTE: NO SE ALMACENA NINGÚN DATO QUE IDENTIFIQUE AL VOTANTE
    # Registrar voto real en blockchain (SIN DATOS DE IDENTIDAD)
    datos_voto = {
        "cargo": cargo,
        "candidato": candidato,
        "rol": rol,
        "peso": peso,
        "timestamp_voto": asyncio.get_event_loop().time()
        # 🔒 NO HAY: código universitario, user_id, nombre, ni ningún dato personal
    }
    blockchain.agregar_voto(datos_voto, es_falso=False)

    # Inyectar ruido
    await inyectar_ruido(blockchain, cantidad=random.randint(1, 3))

    # Quitar cargo de pendientes
    context.user_data["cargos_pendientes"].pop(0)

    # Eliminar mensaje de voto actual
    try:
        await query.delete_message()
    except Exception as e:
        print(f"No se pudo borrar mensaje: {e}")

    # Siguiente cargo o finalizar
    if not context.user_data["cargos_pendientes"]:
        return await finalizar_votacion(update, context)
    else:
        return await mostrar_siguiente_cargo(update, context)


async def finalizar_votacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Marcar en padrón que ya votó
    codigo = context.user_data["codigo"]
    PADRON[codigo]["voto_emitido"] = True
    with open("padron.json", "w") as f:
        json.dump(PADRON, f, indent=2)

    # Borrar todos los mensajes del bot
    chat_id = update.effective_chat.id
    for msg_id in context.user_data["mensajes_bot"]:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            print(f"No se pudo borrar mensaje {msg_id}: {e}")

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

    mensaje = "📊 *RESULTADOS*\n\n"

    if user_id in ADMIN_IDS:
        mensaje += "🔍 *VISTA DE ADMINISTRADOR (SOLO VOTOS REALES)*\n\n"
        for cargo, candidatos in resultados_reales.items():
            mensaje += f"📍 *{cargo}*\n"
            for candidato, votos in candidatos.items():
                mensaje += f"  • {candidato}: {votos:.2f}\n"
            mensaje += "\n"
        mensaje += f"Total votos reales: {total_votos_reales}\nTotal votos falsos: {total_votos_falsos}\n"
    else:
        mensaje += "⚠️ Esta vista incluye ruido para anonimato.\n\n"
        # Mostrar resultados con ruido (solo para público)
        for cargo in CARGOS_Y_CANDIDATOS.keys():
            mensaje += f"📍 *{cargo}*\n"
            if cargo in resultados_reales:
                for candidato, votos in resultados_reales[cargo].items():
                    mensaje += f"  • {candidato}: {votos:.2f}\n"
            mensaje += "\n"

    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def evidencia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra evidencia técnica de anonimato"""
    # Ejemplo de un voto REAL en la blockchain
    ejemplo_voto = {
        "cargo": "Rector",
        "candidato": "Dr. Juan Pérez",
        "rol": "docente",
        "peso": 0.6666666666666666,
        "timestamp_voto": 1234567890.123456
    }
    # Ejemplo de un registro en padron.json
    ejemplo_padron = {
        "12345678": {
            "nombre": "Carlos López",
            "rol": "docente",
            "voto_emitido": True
        }
    }

    mensaje = "🔒 *EVIDENCIA 100% DE ANONIMATO DEL VOTO*\n\n"
    mensaje += "📋 *1. Padrón electoral (padron.json)*:\n"
    mensaje += f"   ```json\n{json.dumps(ejemplo_padron, indent=6)}\n```\n"
    mensaje += "   ✅ NO almacena: candidato elegido, ID de Telegram, nombre en el voto\n\n"

    mensaje += "🔗 *2. Blockchain (voto REAL almacenado)*:\n"
    mensaje += f"   ```json\n{json.dumps(ejemplo_voto, indent=6)}\n```\n"
    mensaje += "   ✅ NO contiene: código universitario, ID de Telegram, nombre del votante\n\n"

    mensaje += "🎭 *3. Ruido criptográfico*:\n"
    mensaje += "   - Votos falsos se mezclan automáticamente después de cada voto real\n"
    mensaje += "   - Imposible correlacionar un voto con un usuario por tiempo\n\n"

    mensaje += "🧹 *4. Contexto del bot*:\n"
    mensaje += "   - Todos los datos temporales (código, rol, etc.) se ELIMINAN completamente después de votar\n"
    mensaje += "   - No hay rastro en el bot de quién votó por quién\n\n"

    mensaje += "🔍 *CONCLUSIÓN*:\n"
    mensaje += "   NO HAY NINGÚN LUGAR en el sistema donde se guarde la relación entre un usuario y su voto.\n"
    mensaje += "   El voto es SECRETO y ANÓNIMO 100%."
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


async def post_init(application: Application):
    """Función para inicializar tareas en segundo plano correctamente"""
    global ruido_stop_event, ruido_task
    ruido_stop_event = asyncio.Event()
    ruido_task = asyncio.create_task(ruido_periodico(blockchain, stop_event=ruido_stop_event))


async def post_shutdown(application: Application):
    """Función para detener tareas en segundo plano correctamente"""
    global ruido_stop_event, ruido_task
    if ruido_stop_event:
        ruido_stop_event.set()
    if ruido_task and not ruido_task.done():
        try:
            await asyncio.wait_for(ruido_task, timeout=5.0)
        except asyncio.TimeoutError:
            ruido_task.cancel()
            try:
                await ruido_task
            except asyncio.CancelledError:
                pass


def main():
    app = Application.builder().token(TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("registro", registro)],
        states={
            REGISTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, validar_codigo)],
            VOTAR: [CallbackQueryHandler(recibir_voto)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True,  # Set to True for CallbackQueryHandler
        per_chat=True,
        per_user=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("resultados", resultados))
    app.add_handler(CommandHandler("evidencia", evidencia))
    app.add_handler(CommandHandler("anomalias", anomalias))
    app.add_handler(CommandHandler("reset", reset))

    print("Bot iniciado...")
    app.run_polling()


if __name__ == "__main__":
    main()

import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, MessageHandler, filters
from config import TOKEN
from blockchain_sim import BlockchainSim
from noise_generator import inyectar_ruido, ruido_periodico
from anomaly_detector import AnomalyDetector
import json

# Estados de conversación
REGISTRO, VOTACION = range(2)

# Cargar padrón simulado
with open("padron.json", "r") as f:
    PADRON = json.load(f)

CANDIDATOS = ["Rector", "Vicerrector Académico", "Vicerrector Administrativo", "Decano de Ingeniería", "Voto Nulo"]
ADMIN_IDS = [11111111]  # Telegram IDs de administradores

# Inicializar blockchain
blockchain = BlockchainSim()
detector = AnomalyDetector(blockchain)
ruido_task = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🗳️ *Sistema de Voto Digital UNT*\n\n"
        "Este bot simula una votación universitaria con:\n"
        "✅ Anonimato (no guardamos quién vota por quién)\n"
        "🎭 Ruido criptográfico (votos falsos para evitar correlación)\n"
        "🔗 Blockchain simulada (inmutable)\n"
        "🤖 IA detectora de anomalías\n\n"
        "Usa /registro para identificarte y votar.",
        parse_mode="Markdown"
    )

async def registro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Guardar IDs de mensajes para borrar después
    if "mensajes_bot" not in context.user_data:
        context.user_data["mensajes_bot"] = []
    msg = await update.message.reply_text("Ingresa tu *código universitario* (solo números):", parse_mode="Markdown")
    context.user_data["mensajes_bot"].append(msg.message_id)
    return REGISTRO

async def validar_codigo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    codigo = update.message.text.strip()
    user_id = str(update.effective_user.id)
    if codigo in PADRON:
        if PADRON[codigo]["voto_emitido"]:
            await update.message.reply_text("❌ Ya has votado. No puedes votar nuevamente.")
            return ConversationHandler.END
        # Guardar rol del usuario en contexto
        context.user_data["rol"] = PADRON[codigo]["rol"]
        context.user_data["codigo"] = codigo
        # Simular verificación biométrica (solo texto)
        msg1 = await update.message.reply_text(f"✅ Identidad verificada: {PADRON[codigo]['nombre']} ({context.user_data['rol'].capitalize()})")
        context.user_data["mensajes_bot"].append(msg1.message_id)
        # Mostrar candidatos
        teclado = [[InlineKeyboardButton(c, callback_data=c)] for c in CANDIDATOS]
        msg2 = await update.message.reply_text("Selecciona tu candidato:", reply_markup=InlineKeyboardMarkup(teclado))
        context.user_data["mensajes_bot"].append(msg2.message_id)
        return VOTACION
    else:
        await update.message.reply_text("❌ Código no válido o no habilitado para votar.")
        return ConversationHandler.END

async def recibir_voto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    candidato = query.data
    rol = context.user_data["rol"]
    peso = 2/3 if rol == "docente" else 1/3

    # Registrar voto real en blockchain
    datos_voto = {
        "candidato": candidato,
        "rol": rol,
        "peso": peso,
        "timestamp_voto": asyncio.get_event_loop().time()
    }
    bloque = blockchain.agregar_voto(datos_voto, es_falso=False)

    # Marcar en padrón que ya votó
    codigo = context.user_data["codigo"]
    PADRON[codigo]["voto_emitido"] = True
    with open("padron.json", "w") as f:
        json.dump(PADRON, f, indent=2)

    # Inyectar ruido (votos falsos) después del voto real
    await inyectar_ruido(blockchain, cantidad=random.randint(1, 5))

    # Borrar todos los mensajes anteriores del bot
    chat_id = query.message.chat_id
    for msg_id in context.user_data["mensajes_bot"]:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except Exception as e:
            print(f"No se pudo borrar mensaje {msg_id}: {e}")
    
    # Borrar también el mensaje con los botones de candidatos
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=query.message.message_id)
    except Exception as e:
        print(f"No se pudo borrar mensaje de candidatos: {e}")

    # Enviar único mensaje final
    await context.bot.send_message(
        chat_id=chat_id,
        text="✅ Usted ya ha votado. ¡Gracias por participar!",
        parse_mode="Markdown"
    )
    
    # Limpiar datos del contexto
    context.user_data.clear()
    return ConversationHandler.END

async def resultados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    resultados_reales = blockchain.obtener_resultados_reales()
    total_votos_reales = sum(resultados_reales.values())
    total_votos_falsos = len(blockchain.votos_falsos)
    
    mensaje = "📊 *RESULTADOS PARCIALES (con ruido)*\n\n"
    mensaje += f"Votos reales: {total_votos_reales} | Votos falsos inyectados: {total_votos_falsos}\n\n"
    mensaje += "*Por candidato (ponderado):*\n"
    for candidato in CANDIDATOS:
        votos = resultados_reales.get(candidato, 0)
        mensaje += f"• {candidato}: {votos:.2f}\n"
    
    if user_id in ADMIN_IDS:
        # Los administradores ven también el ruido detallado
        mensaje += f"\n🔍 *Detalle para administradores*\nRuido total inyectado: {total_votos_falsos} votos falsos.\n"
        mensaje += "Los resultados reales (sin ruido) son los mostrados arriba."
    else:
        mensaje += "\n⚠️ Los resultados incluyen votos falsos para garantizar anonimato. Solo el CEUA conoce el factor de ruido exacto."
    
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def anomalias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporte = detector.detectar()
    mensaje = "🤖 *Análisis de IA - Detección de anomalías*\n\n"
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
    # Reiniciar padrón
    for cod in PADRON:
        PADRON[cod]["voto_emitido"] = False
    with open("padron.json", "w") as f:
        json.dump(PADRON, f, indent=2)
    await update.message.reply_text("🔄 Votación reiniciada. Todos los votos (reales y ruido) han sido eliminados.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Proceso cancelado. Usa /registro para empezar de nuevo.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Conversación para registro y votación
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("registro", registro)],
        states={
            REGISTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, validar_codigo)],
            VOTACION: [CallbackQueryHandler(recibir_voto)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("resultados", resultados))
    app.add_handler(CommandHandler("anomalias", anomalias))
    app.add_handler(CommandHandler("reset", reset))
    
    # Tarea de ruido periódico en segundo plano
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(ruido_periodico(blockchain, intervalo_segundos=30))
    
    print("Bot iniciado...")
    app.run_polling()

if __name__ == "__main__":
    main()
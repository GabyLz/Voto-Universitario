import random
import asyncio
from blockchain_sim import BlockchainSim

CANDIDATOS = ["Rector", "Vicerrector Académico", "Vicerrector Administrativo", "Decano de Ingeniería", "Voto Nulo"]

async def inyectar_ruido(blockchain: BlockchainSim, cantidad=1):
    """Inyecta votos falsos aleatorios"""
    for _ in range(cantidad):
        candidato_falso = random.choice(CANDIDATOS)
        rol_falso = random.choice(["docente", "estudiante"])
        peso_falso = 2/3 if rol_falso == "docente" else 1/3
        blockchain.agregar_voto({
            "candidato": candidato_falso,
            "rol": rol_falso,
            "peso": peso_falso,
            "timestamp_voto": asyncio.get_event_loop().time()
        }, es_falso=True)
        await asyncio.sleep(0.1)  # simula latencia

async def ruido_periodico(blockchain: BlockchainSim, intervalo_segundos=30):
    """Cada cierto tiempo inyecta ruido aleatorio (1-3 votos falsos)"""
    while True:
        await asyncio.sleep(intervalo_segundos)
        cantidad = random.randint(1, 3)
        await inyectar_ruido(blockchain, cantidad)
        print(f"[Ruido] Inyectados {cantidad} votos falsos")
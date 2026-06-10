import random
import asyncio
from blockchain_sim import BlockchainSim

# Definir cargos y sus candidatos
CARGOS_Y_CANDIDATOS = {
    "Rector": ["Dr. Juan Pérez", "Dra. María Gómez", "Dr. Roberto Díaz", "Voto Nulo"],
    "Vicerrector Académico": ["Dr. Carlos Ruiz", "Dra. Ana López", "Dra. Patricia Morales", "Voto Nulo"],
    "Vicerrector Administrativo": ["Dr. Luis Fernández", "Dra. Laura Martínez", "Dr. Andrés Castillo", "Voto Nulo"],
    "Decano": ["Dr. Pedro Sánchez", "Dra. Sofía Rodríguez", "Dr. Javier Ortega", "Voto Nulo"]
}


async def inyectar_ruido(blockchain: BlockchainSim, cantidad=1):
    """Inyecta votos falsos aleatorios por cargo"""
    for _ in range(cantidad):
        cargo_falso = random.choice(list(CARGOS_Y_CANDIDATOS.keys()))
        candidato_falso = random.choice(CARGOS_Y_CANDIDATOS[cargo_falso])
        rol_falso = random.choice(["docente", "estudiante"])
        peso_falso = 2/3 if rol_falso == "docente" else 1/3
        blockchain.agregar_voto({
            "cargo": cargo_falso,
            "candidato": candidato_falso,
            "rol": rol_falso,
            "peso": peso_falso,
            "timestamp_voto": asyncio.get_event_loop().time()
        }, es_falso=True)
        await asyncio.sleep(0.1)


async def ruido_periodico(blockchain: BlockchainSim, intervalo_segundos=30, stop_event=None):
    """Cada cierto tiempo inyecta ruido aleatorio (1-3 votos falsos) - con evento de parada"""
    while not (stop_event and stop_event.is_set()):
        try:
            await asyncio.sleep(intervalo_segundos)
            if stop_event and stop_event.is_set():
                break
            cantidad = random.randint(1, 3)
            await inyectar_ruido(blockchain, cantidad)
            print(f"[Ruido] Inyectados {cantidad} votos falsos")
        except asyncio.CancelledError:
            break

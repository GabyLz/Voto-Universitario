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
    """Inyecta votos falsos aleatorios por cargo (solo para anonimato)"""
    for _ in range(cantidad):
        cargo_falso = random.choice(list(CARGOS_Y_CANDIDATOS.keys()))
        candidato_falso = random.choice(CARGOS_Y_CANDIDATOS[cargo_falso])
        rol_falso = random.choice(["docente", "estudiante"])
        peso_falso = 1  # También peso 1, pero NO cuenta en resultados
        blockchain.agregar_voto({
            "cargo": cargo_falso,
            "candidato": candidato_falso,
            "rol": rol_falso,
            "peso": peso_falso,
            "timestamp_voto": asyncio.get_event_loop().time()
        }, es_falso=True)
        await asyncio.sleep(0.1)



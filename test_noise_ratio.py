import asyncio
import sys
from blockchain_sim import BlockchainSim
from noise_generator import inyectar_ruido

async def test_proporcion_ruido():
    print("Iniciando prueba de proporcion de ruido 2:1...")
    
    # 1. Inicializar la blockchain simulada
    blockchain = BlockchainSim()
    
    # El bloque genesis no es un voto, verificamos que esté vacío de votos por ahora
    assert len(blockchain.votos_reales) == 0
    assert len(blockchain.votos_falsos) == 0
    print("[OK] Blockchain inicializada correctamente (solo bloque Genesis).")
    
    # 2. Simular la emisión de 5 votos reales
    votos_a_simular = 5
    for i in range(votos_a_simular):
        # Datos ficticios de voto real
        datos_voto = {
            "cargo": "Rector",
            "candidato": "Dr. Juan Perez",
            "rol": "estudiante",
            "peso": 1,
            "timestamp_voto": 123456789.0
        }
        # Agregar voto real (como se hace en bot.py)
        blockchain.agregar_voto(datos_voto, es_falso=False)
        
        # Inyectar exactamente 2 votos de ruido (como se hace en bot.py)
        await inyectar_ruido(blockchain, cantidad=2)
        
        print(f"  Simulado voto real #{i+1} + 2 votos falsos.")

    # 3. Verificaciones de proporción
    total_reales = len(blockchain.votos_reales)
    total_falsos = len(blockchain.votos_falsos)
    total_bloques_esperados = 1 + (votos_a_simular * 3) # genesis + (1 real + 2 falsos)*5 = 16
    
    print(f"\nResultados finales de la simulacion:")
    print(f"  Votos reales registrados: {total_reales}")
    print(f"  Votos falsos (ruido) registrados: {total_falsos}")
    print(f"  Total de bloques en la blockchain: {len(blockchain.cadena)}")
    
    # Aserciones
    assert total_reales == votos_a_simular, f"Se esperaban {votos_a_simular} votos reales, se obtuvieron {total_reales}."
    assert total_falsos == votos_a_simular * 2, f"Se esperaban {votos_a_simular * 2} votos falsos, se obtuvieron {total_falsos}."
    assert len(blockchain.cadena) == total_bloques_esperados, f"Se esperaban {total_bloques_esperados} bloques totales, se obtuvieron {len(blockchain.cadena)}."
    
    # Verificar proporción matemática (2 falsos por 1 verdadero)
    proporcion = total_falsos / total_reales
    assert proporcion == 2.0, f"La proporcion esperada es 2.0, pero se obtuvo {proporcion}."
    
    print("\n[OK] ¡Prueba completada con exito! La proporcion de ruido es exactamente 2:1.")

if __name__ == "__main__":
    try:
        asyncio.run(test_proporcion_ruido())
    except AssertionError as e:
        print(f"[ERROR] Fallo en la asercion: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Error inesperado: {e}")
        sys.exit(1)
    sys.exit(0)


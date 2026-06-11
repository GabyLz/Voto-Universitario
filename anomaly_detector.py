import numpy as np
from collections import defaultdict
from datetime import datetime

class AnomalyDetector:
    def __init__(self, blockchain):
        self.blockchain = blockchain

    def detectar(self):
        # Obtener tiempos de votos reales
        tiempos = [bloque.timestamp for bloque in self.blockchain.votos_reales]
        if len(tiempos) < 5:
            return "No hay suficientes votos para análisis."

        # Calcular velocidad de votos por minuto
        tiempos.sort()
        diferencias = np.diff(tiempos)
        votos_por_minuto = 60 / np.mean(diferencias) if len(diferencias) > 0 else 0

        # Detectar picos: si votos_por_minuto > promedio + 2 desviaciones
        umbral = np.mean(diferencias) - 2 * np.std(diferencias) if len(diferencias) > 1 else 0
        picos = [t for t in diferencias if t < umbral]

        anomalias = []
        if votos_por_minuto > 10:
            anomalias.append(f"Alta velocidad de votación: {votos_por_minuto:.1f} votos/min")
        if len(picos) > 0:
            anomalias.append(f"Se detectaron {len(picos)} intervalos de votación inusualmente rápidos.")
        # Simular clustering simple para votos concentrados
        candidatos_count = defaultdict(int)
        for bloque in self.blockchain.votos_reales:
            candidatos_count[bloque.datos["candidato"]] += 1
        if max(candidatos_count.values()) > len(self.blockchain.votos_reales) * 0.8:
            anomalias.append("Concentración anómala de votos en un solo candidato.")

        return anomalias if anomalias else ["Sin anomalías detectadas."]


# ═══════════════════════════════════════════════════════════════════════════════
# VERSIÓN ZK — Compatible con BlockchainZKSim + TallyAuthority
# Los votos están cifrados. El detector usa:
#   - timestamps públicos de todos los bloques
#   - info agregada de la autoridad (totales, ratio)
# ═══════════════════════════════════════════════════════════════════════════════

class AnomalyDetectorZK:
    def __init__(self, blockchain_zk, tally_authority):
        self.blockchain = blockchain_zk
        self.tally = tally_authority

    def detectar(self):
        # Timestamps de todos los bloques de voto (excluyendo génesis)
        tiempos = [b.timestamp for b in self.blockchain.cadena[1:]]
        if len(tiempos) < 5:
            return "No hay suficientes bloques para análisis."

        tiempos.sort()
        diferencias = np.diff(tiempos)
        votos_por_minuto = 60 / np.mean(diferencias) if len(diferencias) > 0 else 0

        anomalias = []

        if votos_por_minuto > 10:
            anomalias.append(
                f"Alta velocidad de votación: {votos_por_minuto:.1f} bloques/min "
                f"(incluye ruido ZK)"
            )

        # Info agregada desde la autoridad (no revela votos individuales)
        total_reales = self.tally.total_reales
        total_falsos = self.tally.total_falsos
        if total_reales > 0 and total_falsos > 0:
            ratio = total_falsos / total_reales
            anomalias.append(f"Ratio ruido/real: {ratio:.1f}:1  (reales={total_reales}, ruido={total_falsos})")

        # Concentración: solo si la autoridad ya descifró resultados
        if self.tally._resultados:
            for cargo, cands in self.tally._resultados.items():
                total = sum(cands.values())
                if total > 0:
                    max_votos = max(cands.values())
                    if max_votos > total * 0.8:
                        ganador = max(cands, key=cands.get)
                        anomalias.append(
                            f"Concentración en {cargo}: {ganador} con "
                            f"{max_votos}/{total} votos ({100*max_votos/total:.0f}%)"
                        )

        return anomalias if anomalias else ["Sin anomalías detectadas."]
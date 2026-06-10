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
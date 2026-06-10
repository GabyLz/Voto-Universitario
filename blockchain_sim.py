import hashlib
import time
import json
from typing import List, Dict

class Bloque:
    def __init__(self, index, timestamp, datos, hash_anterior, es_falso=False):
        self.index = index
        self.timestamp = timestamp
        self.datos = datos  # {'candidato': 'X', 'rol': 'docente', 'peso': 0.666}
        self.hash_anterior = hash_anterior
        self.es_falso = es_falso
        self.nonce = 0  # para minado simulado
        self.hash = self.calcular_hash()

    def calcular_hash(self):
        contenido = f"{self.index}{self.timestamp}{self.datos}{self.hash_anterior}{self.es_falso}{self.nonce}"
        return hashlib.sha256(contenido.encode()).hexdigest()

    def minar(self, dificultad=2):
        objetivo = "0" * dificultad
        while self.hash[:dificultad] != objetivo:
            self.nonce += 1
            self.hash = self.calcular_hash()

class BlockchainSim:
    def __init__(self):
        self.cadena = [self.crear_bloque_genesis()]
        self.votos_reales = []  # lista de bloques reales (para resultados)
        self.votos_falsos = []  # lista de bloques falsos (solo para ruido)

    def crear_bloque_genesis(self):
        return Bloque(0, time.time(), "Genesis", "0", es_falso=False)

    def obtener_ultimo_bloque(self):
        return self.cadena[-1]

    def agregar_voto(self, datos_voto, es_falso=False):
        nuevo_bloque = Bloque(len(self.cadena), time.time(), datos_voto,
                              self.obtener_ultimo_bloque().hash, es_falso)
        nuevo_bloque.minar(dificultad=1)  # simula trabajo
        self.cadena.append(nuevo_bloque)
        if not es_falso:
            self.votos_reales.append(nuevo_bloque)
        else:
            self.votos_falsos.append(nuevo_bloque)
        return nuevo_bloque

    def obtener_resultados_reales(self):
        # Suma ponderada por candidato
        resultados = {}
        for bloque in self.votos_reales:
            candidato = bloque.datos["candidato"]
            peso = bloque.datos["peso"]
            resultados[candidato] = resultados.get(candidato, 0) + peso
        return resultados
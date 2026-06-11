import hashlib
import time
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Bloque:
    def __init__(self, index, timestamp, datos, hash_anterior, es_falso=False):
        self.index = index
        self.timestamp = timestamp
        self.datos = datos  # {'cargo': 'Rector', 'candidato': 'X', 'rol': 'docente', 'peso': 0.666}
        self.hash_anterior = hash_anterior
        self.es_falso = es_falso
        self.nonce = 0
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
        self.votos_reales = []
        self.votos_falsos = []

    def crear_bloque_genesis(self):
        return Bloque(0, time.time(), "Genesis", "0", es_falso=False)

    def obtener_ultimo_bloque(self):
        return self.cadena[-1]

    def agregar_voto(self, datos_voto, es_falso=False):
        logger.info(f"Agregando voto {'falso' if es_falso else 'real'}: {datos_voto}")
        nuevo_bloque = Bloque(
            len(self.cadena),
            time.time(),
            datos_voto,
            self.obtener_ultimo_bloque().hash,
            es_falso
        )
        nuevo_bloque.minar(dificultad=1)
        self.cadena.append(nuevo_bloque)
        if not es_falso:
            self.votos_reales.append(nuevo_bloque)
            logger.info(f"Total votos reales ahora: {len(self.votos_reales)}")
        else:
            self.votos_falsos.append(nuevo_bloque)
        return nuevo_bloque

    def obtener_resultados_reales(self):
        logger.info(f"Calculando resultados de {len(self.votos_reales)} votos reales")
        resultados = {}
        for bloque in self.votos_reales:
            logger.info(f"Procesando voto real: {bloque.datos}")
            cargo = bloque.datos["cargo"]
            candidato = bloque.datos["candidato"]
            peso = bloque.datos["peso"]
            if cargo not in resultados:
                resultados[cargo] = {}
            resultados[cargo][candidato] = resultados[cargo].get(candidato, 0) + peso
        logger.info(f"Resultados calculados: {resultados}")
        return resultados


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE Y BLOCKCHAIN CON ZK PROOFS
# Versión con pruebas de conocimiento cero: votos reales y falsos
# son criptográficamente indistinguibles en la cadena.
# ═══════════════════════════════════════════════════════════════════════════════

class BloqueZK:
    """
    Bloque que almacena un voto cifrado con ElGamal + prueba ZK de validez.

    NO guarda:
      - El candidato elegido (está cifrado dentro de a, b)
      - La bandera es_falso (no existe)
      - El rol del votante

    CUALQUIERA puede:
      - Verificar que la prueba ZK es válida
      - Verificar la integridad de la cadena (hashes)

    NADIE (sin la clave secreta sk) puede:
      - Saber si el voto es real o falso
      - Saber por qué candidato se votó
    """

    def __init__(self, index, timestamp, cargo, a, b, prueba_zk, hash_anterior):
        self.index = index
        self.timestamp = timestamp
        self.cargo = cargo            # público (ej: "Rector")
        self.a = a                    # ElGamal: g^r
        self.b = b                    # ElGamal: pk^r · g^voto
        self.prueba_zk = prueba_zk    # list[(c_j, s_j)]
        self.hash_anterior = hash_anterior
        self.nonce = 0
        self.hash = self.calcular_hash()

    def calcular_hash(self):
        contenido = (
            f"{self.index}{self.timestamp}{self.cargo}"
            f"{self.a}{self.b}{self.prueba_zk}{self.hash_anterior}{self.nonce}"
        )
        return hashlib.sha256(contenido.encode()).hexdigest()

    def minar(self, dificultad=1):
        objetivo = "0" * dificultad
        while self.hash[:dificultad] != objetivo:
            self.nonce += 1
            self.hash = self.calcular_hash()


class BlockchainZKSim:
    """
    Blockchain simulada con votos protegidos por ZK proofs.

    La cadena es pública. Cualquiera puede verificar las pruebas ZK
    y la integridad de los hashes, pero NADIE puede distinguir
    votos reales de falsos sin la clave secreta de la autoridad.
    """

    def __init__(self, pk):
        self.pk = pk
        self.cadena = [self.crear_bloque_genesis()]

    def crear_bloque_genesis(self):
        return BloqueZK(
            index=0,
            timestamp=time.time(),
            cargo="GENESIS",
            a=0,
            b=0,
            prueba_zk=[],
            hash_anterior="0",
        )

    def obtener_ultimo_bloque(self):
        return self.cadena[-1]

    def agregar_voto(self, cargo, a, b, prueba_zk):
        """
        Agrega un voto cifrado a la cadena.

        No recibe parámetro es_falso. Todos los votos se ven iguales.
        La distinción real/falso solo la conoce la TallyAuthority.
        """
        logger.info(f"Agregando voto ZK para cargo={cargo}")
        nuevo_bloque = BloqueZK(
            index=len(self.cadena),
            timestamp=time.time(),
            cargo=cargo,
            a=a,
            b=b,
            prueba_zk=prueba_zk,
            hash_anterior=self.obtener_ultimo_bloque().hash,
        )
        nuevo_bloque.minar(dificultad=1)
        self.cadena.append(nuevo_bloque)
        logger.info(f"Bloque ZK #{nuevo_bloque.index} minado. "
                     f"Hash: {nuevo_bloque.hash[:16]}...")
        return nuevo_bloque

    def verificar_cadena(self):
        """
        Verifica integridad completa de la cadena:
          1. Hashes consecutivos correctos
          2. Pruebas ZK válidas para cada bloque de voto

        Retorna True si todo es válido.
        """
        from zk_proofs import verificar_prueba_zk
        for i in range(1, len(self.cadena)):
            bloque = self.cadena[i]
            anterior = self.cadena[i - 1]

            if bloque.hash_anterior != anterior.hash:
                logger.error(f"Hash roto en bloque {i}")
                return False
            if bloque.hash != bloque.calcular_hash():
                logger.error(f"Hash propio inválido en bloque {i}")
                return False

            # Verificar ZK proof (el génesis no tiene prueba)
            if bloque.prueba_zk:
                # Determinamos n_candidatos desde el tamaño de la prueba
                n_candidatos = len(bloque.prueba_zk) - 1
                if not verificar_prueba_zk(
                    bloque.a, bloque.b, bloque.prueba_zk, self.pk, n_candidatos
                ):
                    logger.error(f"Prueba ZK inválida en bloque {i}")
                    return False

        logger.info("Cadena verificada: todas las pruebas ZK válidas.")
        return True

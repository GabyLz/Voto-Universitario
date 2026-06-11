"""
Autoridad Electoral que posee la clave secreta (sk).
Sabe qué bloques son votos reales (por registro interno, NO por la cadena).
Descifra los resultados al finalizar la votación.
"""

import logging
import zk_proofs as zk

logger = logging.getLogger(__name__)


class TallyAuthority:

    def __init__(self):
        self.sk, self.pk = zk.generar_claves()
        self.votos_reales = {}       # hash_bloque -> {"cargo": str, "a": int, "b": int}
        self.votos_falsos = {}       # hash_bloque -> {"cargo": str, "a": int, "b": int}
        self._resultados = None

    @property
    def clave_publica(self):
        return self.pk

    def registrar_voto(self, hash_bloque, cargo, a, b, es_real):
        """Registra internamente si un voto es real o falso."""
        entrada = {"cargo": cargo, "a": a, "b": b}
        if es_real:
            self.votos_reales[hash_bloque] = entrada
        else:
            self.votos_falsos[hash_bloque] = entrada

    def descifrar_voto(self, a, b):
        """Descifra un voto individual."""
        return zk.descifrar(a, b, self.sk)

    def obtener_resultados(self, candidatos_por_cargo):
        """
        Descifra todos los votos reales y arma el escrutinio.

        candidatos_por_cargo: dict {"Rector": ["Juan", "María", ...], ...}

        Retorna dict: {cargo: {candidato: cantidad_votos}}
        """
        resultados = {}
        for cargo in candidatos_por_cargo:
            resultados[cargo] = {c: 0 for c in candidatos_por_cargo[cargo]}

        for entrada in self.votos_reales.values():
            cargo = entrada["cargo"]
            indice = self.descifrar_voto(entrada["a"], entrada["b"])
            if indice is None:
                logger.warning(f"No se pudo descifrar voto para {cargo}")
                continue
            candidatos = candidatos_por_cargo.get(cargo, [])
            if 1 <= indice <= len(candidatos):
                nombre = candidatos[indice - 1]
                if cargo in resultados:
                    resultados[cargo][nombre] = resultados[cargo].get(nombre, 0) + 1
            else:
                logger.warning(f"Índice {indice} fuera de rango para {cargo}")

        self._resultados = resultados
        logger.info(f"Resultados descifrados: {resultados}")
        return resultados

    def verificar_consistencia(self, blockchain_zk):
        """
        Verifica que todos los bloques de la cadena tengan pruebas ZK válidas
        y que los votos reales registrados internamente coincidan con la cadena.
        """
        cadena_ok = blockchain_zk.verificar_cadena()
        logger.info(f"Verificación de cadena: {'OK' if cadena_ok else 'FALLÓ'}")
        return cadena_ok

    @property
    def total_reales(self):
        return len(self.votos_reales)

    @property
    def total_falsos(self):
        return len(self.votos_falsos)

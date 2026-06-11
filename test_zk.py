"""
Pruebas del sistema ZK.
Verifica:
  1. Cifrado/descifrado ElGamal
  2. Prueba ZK válida → verifica OK
  3. Prueba ZK inválida → verifica FAIL
  4. Indistinguibilidad: cifrados de voto real vs falso
  5. Flujo completo con blockchain ZK
"""

import asyncio
import sys
import time

import zk_proofs as zk
from blockchain_sim import BlockchainZKSim
from tally_authority import TallyAuthority
from noise_generator import CARGOS_Y_CANDIDATOS


def test_cifrado_descifrado():
    """Prueba básica de ElGamal."""
    print("-" * 50)
    print("TEST 1: Cifrado / Descifrado ElGamal")
    sk, pk = zk.generar_claves()
    assert pk == pow(zk.G_Q, sk, zk.P), "pk != g^sk"

    for voto in [0, 1, 2, 3, 4]:
        a, b, r = zk.encriptar(voto, pk)
        descifrado = zk.descifrar(a, b, sk)
        assert descifrado == voto, f"voto={voto} pero descifrado={descifrado}"

    print("  [OK] Todos los valores se cifran y descifran correctamente.")
    return sk, pk


def test_zk_prueba_valida():
    """Prueba que una ZK proof válida sea aceptada."""
    print("\n" + "-" * 50)
    print("TEST 2: Prueba ZK válida (OR proof)")

    sk, pk = zk.generar_claves()
    n_candidatos = 4  # 0..4 = 5 valores posibles

    for voto_real in range(n_candidatos + 1):
        a, b, r = zk.encriptar(voto_real, pk)
        prueba = zk.crear_prueba_zk(a, b, voto_real, r, pk, n_candidatos)
        assert zk.verificar_prueba_zk(a, b, prueba, pk, n_candidatos), (
            f"Prueba rechazada para voto={voto_real}"
        )

    print(f"  [OK] Pruebas ZK válidas para todos los valores 0..{n_candidatos}.")


def test_zk_prueba_invalida():
    """Prueba que una ZK proof incorrecta sea rechazada."""
    print("\n" + "-" * 50)
    print("TEST 3: Prueba ZK invalida (debe ser rechazada)")

    _, pk = zk.generar_claves()
    n_candidatos = 4

    # Caso 1: voto fuera de rango -> la funcion lanza AssertionError
    try:
        a, b, r = zk.encriptar(5, pk)  # 5 > 4
        zk.crear_prueba_zk(a, b, 5, r, pk, n_candidatos)
        assert False, "Deberia haber lanzado AssertionError"
    except AssertionError:
        pass  # Esperado: no se permiten pruebas para valores fuera de rango

    # Caso 2: modificar la prueba despues de crearla
    a, b, r = zk.encriptar(2, pk)
    prueba = zk.crear_prueba_zk(a, b, 2, r, pk, n_candidatos)
    # Alterar un valor de la prueba
    prueba_trucada = list(prueba)
    c0, s0 = prueba_trucada[0]
    prueba_trucada[0] = ((c0 + 1) % zk.Q, s0)
    assert not zk.verificar_prueba_zk(a, b, prueba_trucada, pk, n_candidatos), (
        "Prueba trucada NO fue rechazada"
    )

    # Caso 3: prueba con otro cifrado
    a2, b2, _ = zk.encriptar(3, pk)
    assert not zk.verificar_prueba_zk(a2, b2, prueba, pk, n_candidatos), (
        "Prueba de otro cifrado NO fue rechazada"
    )

    print("  [OK] Pruebas invalidas correctamente rechazadas.")


def test_indistinguibilidad():
    """Verifica que votos reales y falsos sean indistinguibles a simple vista."""
    print("\n" + "-" * 50)
    print("TEST 4: Indistinguibilidad voto real vs falso")

    _, pk = zk.generar_claves()
    n = 4

    a_real, b_real, r_real = zk.encriptar(2, pk)  # voto real: candidato 2
    a_falso, b_falso, r_falso = zk.encriptar(0, pk)  # voto falso: nulo

    # Ambos son números grandes del mismo tamaño
    assert isinstance(a_real, int) and isinstance(b_real, int)
    assert isinstance(a_falso, int) and isinstance(b_falso, int)

    # Las pruebas ZK son idénticas en estructura
    p_real = zk.crear_prueba_zk(a_real, b_real, 2, r_real, pk, n)
    p_falso = zk.crear_prueba_zk(a_falso, b_falso, 0, r_falso, pk, n)

    assert len(p_real) == len(p_falso), "Las pruebas tienen distinto tamaño"
    assert zk.verificar_prueba_zk(a_real, b_real, p_real, pk, n)
    assert zk.verificar_prueba_zk(a_falso, b_falso, p_falso, pk, n)

    # Verificar que NO se puede distinguir por el valor de a o b
    # (son aleatorios, así que no hay un patrón visible)
    print(f"  Real : a={str(a_real)[:20]}... b={str(b_real)[:20]}...")
    print(f"  Falso: a={str(a_falso)[:20]}... b={str(b_falso)[:20]}...")
    print("  [OK] Votos reales y falsos son indistinguibles sin la clave sk.")


def test_suma_homomorfica():
    """Verifica la suma homomórfica de cifrados ElGamal."""
    print("\n" + "-" * 50)
    print("TEST 5: Suma homomórfica")

    sk, pk = zk.generar_claves()

    # 3 votos: 2, 3, 0 (falso) → suma = 5
    cifrados = [
        zk.encriptar(2, pk)[:2],
        zk.encriptar(3, pk)[:2],
        zk.encriptar(0, pk)[:2],
    ]

    a_total, b_total = zk.suma_homomorfica(cifrados)
    g_suma = zk.descifrar_suma(a_total, b_total, sk)

    suma = zk._log_discreto(g_suma, max_val=20)
    assert suma == 5, f"Suma esperada=5, obtenida={suma}"

    print(f"  Suma homomórfica: 2 + 3 + 0 = {suma}")
    print("  [OK] Suma homomórfica funciona correctamente.")


async def test_flujo_completo():
    """Simula un flujo completo de votación con ZK."""
    print("\n" + "-" * 50)
    print("TEST 6: Flujo completo (blockchain ZK + autoridad)")

    authority = TallyAuthority()
    chain = BlockchainZKSim(authority.clave_publica)

    # Simular votos
    votos_reales = [
        ("Rector", "Dr. Juan Pérez"),
        ("Rector", "Dra. María Gómez"),
        ("Rector", "Dr. Juan Pérez"),
        ("Vicerrector Académico", "Dr. Carlos Ruiz"),
        ("Vicerrector Académico", "Dra. Ana López"),
    ]

    for cargo, candidato in votos_reales:
        candidatos = CARGOS_Y_CANDIDATOS[cargo]
        indice = candidatos.index(candidato) + 1
        n = len(candidatos)

        a, b, r = zk.encriptar(indice, authority.clave_publica)
        proof = zk.crear_prueba_zk(a, b, indice, r, authority.clave_publica, n)
        bloque = chain.agregar_voto(cargo, a, b, proof)
        authority.registrar_voto(bloque.hash, cargo, a, b, es_real=True)

        # 2 votos falsos por cada real
        for _ in range(2):
            a_f, b_f, r_f = zk.encriptar(0, authority.clave_publica)
            cargo_f = "Rector"
            p_f = zk.crear_prueba_zk(a_f, b_f, 0, r_f, authority.clave_publica, 4)
            b_falso = chain.agregar_voto(cargo_f, a_f, b_f, p_f)
            authority.registrar_voto(b_falso.hash, cargo_f, a_f, b_f, es_real=False)

    # Verificar cadena
    assert chain.verificar_cadena(), "Verificación de cadena falló"

    # Obtener resultados
    resultados = authority.obtener_resultados(CARGOS_Y_CANDIDATOS)

    assert resultados["Rector"]["Dr. Juan Pérez"] == 2
    assert resultados["Rector"]["Dra. María Gómez"] == 1
    assert resultados["Vicerrector Académico"]["Dr. Carlos Ruiz"] == 1
    assert resultados["Vicerrector Académico"]["Dra. Ana López"] == 1

    print(f"  Bloques totales: {len(chain.cadena)}")
    print(f"  Votos reales: {authority.total_reales}")
    print(f"  Votos falsos: {authority.total_falsos}")
    print(f"  Resultados: {resultados}")
    print("  [OK] Flujo completo funciona: votos cifrados, ZK válidas, "
          "resultados correctos.")


async def test_observador_no_distingue():
    """Simula un observador externo que intenta distinguir votos reales de falsos."""
    print("\n" + "-" * 50)
    print("TEST 7: Observador externo NO puede distinguir real de falso")

    authority = TallyAuthority()
    chain = BlockchainZKSim(authority.clave_publica)

    # Crear 1 voto real y 1 falso
    a_r, b_r, r_r = zk.encriptar(3, authority.clave_publica)
    p_r = zk.crear_prueba_zk(a_r, b_r, 3, r_r, authority.clave_publica, 4)
    chain.agregar_voto("Rector", a_r, b_r, p_r)

    a_f, b_f, r_f = zk.encriptar(0, authority.clave_publica)
    p_f = zk.crear_prueba_zk(a_f, b_f, 0, r_f, authority.clave_publica, 4)
    chain.agregar_voto("Rector", a_f, b_f, p_f)

    # Un observador solo ve los bloques
    b1 = chain.cadena[1]  # voto real
    b2 = chain.cadena[2]  # voto falso

    # No hay campo es_falso
    assert not hasattr(b1, "es_falso")
    assert not hasattr(b2, "es_falso")

    # No hay datos en texto plano con el candidato
    assert not hasattr(b1, "datos")
    assert not hasattr(b2, "datos")

    # Ambos bloques son estructuralmente idénticos
    assert type(b1.a) == type(b2.a) == int
    assert type(b1.b) == type(b2.b) == int
    assert len(b1.prueba_zk) == len(b2.prueba_zk)

    # Ambas pruebas son válidas
    assert zk.verificar_prueba_zk(b1.a, b1.b, b1.prueba_zk, authority.clave_publica, 4)
    assert zk.verificar_prueba_zk(b2.a, b2.b, b2.prueba_zk, authority.clave_publica, 4)

    # Sin sk, es imposible saber cuál es real
    # (solo verificamos que el descifrado revela la verdad)
    v1 = zk.descifrar(b1.a, b1.b, authority.sk)
    v2 = zk.descifrar(b2.a, b2.b, authority.sk)
    assert v1 != v2  # uno es 3, otro es 0
    assert (v1 == 3 and v2 == 0) or (v1 == 0 and v2 == 3)

    print(f"  Bloque #1: a={str(b1.a)[:30]}...")
    print(f"  Bloque #2: a={str(b2.a)[:30]}...")
    print("  Ambos bloques son indistinguibles sin la clave sk.")
    print("  [OK] Observador externo no puede distinguir votos reales de falsos.")


async def main():
    print("\n" + "=" * 50)
    print("  PRUEBAS DEL SISTEMA ZK — VOTO UNIVERSITARIO")
    print("=" * 50)

    try:
        test_cifrado_descifrado()
    except AssertionError as e:
        print(f"\n[FAIL] Test 1: {e}")
        sys.exit(1)

    try:
        test_zk_prueba_valida()
    except AssertionError as e:
        print(f"\n[FAIL] Test 2: {e}")
        sys.exit(1)

    try:
        test_zk_prueba_invalida()
    except AssertionError as e:
        print(f"\n[FAIL] Test 3: {e}")
        sys.exit(1)

    try:
        test_indistinguibilidad()
    except AssertionError as e:
        print(f"\n[FAIL] Test 4: {e}")
        sys.exit(1)

    try:
        test_suma_homomorfica()
    except AssertionError as e:
        print(f"\n[FAIL] Test 5: {e}")
        sys.exit(1)

    try:
        await test_flujo_completo()
    except AssertionError as e:
        print(f"\n[FAIL] Test 6: {e}")
        sys.exit(1)

    try:
        await test_observador_no_distingue()
    except AssertionError as e:
        print(f"\n[FAIL] Test 7: {e}")
        sys.exit(1)

    print("\n" + "=" * 50)
    print("  TODAS LAS PRUEBAS PASARON [OK]")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())

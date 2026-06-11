"""
Motor criptográfico del sistema ZK.
Implementa:
  - Cifrado ElGamal (sobre subgrupo de orden primo)
  - Prueba ZK disyuntiva (OR proof) de rango: voto ∈ {0, 1, ..., N}
  - Suma homomórfica y descifrado

Usa solo hashlib + aritmética modular. Sin dependencias externas.
"""

import hashlib
import secrets

# ═══════════════════════════════════════════════════════════════════════════════
# PARÁMETROS DEL GRUPO (primo seguro de 128 bits para simulación educativa)
# En producción real se usaría RFC 3526 Group 14 (2048-bit) o superior.
# ═══════════════════════════════════════════════════════════════════════════════

# p = 2q + 1, ambos primos (safe prime verificado con Miller-Rabin)
P = 578433664540083465152592055267573773443
Q = 289216832270041732576296027633786886721   # (P - 1) // 2

G = 2                                          # generador de Z_p*
G_Q = pow(G, 2, P)                             # generador del subgrupo de orden q (= 4 mod P)

# Verificación rápida: G_Q^Q ≡ 1 (mod P)
assert pow(G_Q, Q, P) == 1, "G_Q no genera el subgrupo de orden Q"


def _generar_h(semilla="voto-universitario-unt"):
    """Genera h en el subgrupo de orden q. Nadie conoce log_g(h)."""
    h_bytes = hashlib.sha256(semilla.encode()).digest()
    h_int = int.from_bytes(h_bytes, "big") % P
    return pow(h_int, 2, P)


H = _generar_h()


# ═══════════════════════════════════════════════════════════════════════════════
# ELGAMAL
# ═══════════════════════════════════════════════════════════════════════════════

def generar_claves():
    """Genera par de claves ElGamal para la autoridad electoral."""
    sk = secrets.randbelow(Q - 1) + 1
    pk = pow(G_Q, sk, P)
    return sk, pk


def encriptar(voto, pk):
    """
    Encripta un valor de voto con ElGamal.

    Parámetros
    ----------
    voto : int
        0 = voto falso (ruido).
        1..N = índice del candidato elegido.
    pk : int
        Clave pública de la autoridad electoral.

    Retorna
    -------
    (a, b, r) : (int, int, int)
        Cifrado (a, b) y aleatoriedad r usada.
    """
    r = secrets.randbelow(Q - 1) + 1
    a = pow(G_Q, r, P)                     # a = g^r
    b = (pow(pk, r, P) * pow(G_Q, voto, P)) % P  # b = pk^r * g^voto
    return a, b, r


def descifrar(a, b, sk):
    """
    Descifra UN voto individual.

    g^v = b / a^sk  →  fuerza bruta el log discreto.
    Solo funciona porque v es pequeño (≤ número de candidatos).
    """
    a_sk = pow(a, sk, P)
    a_sk_inv = pow(a_sk, P - 2, P)         # inverso modular (P es primo)
    g_v = (b * a_sk_inv) % P
    return _log_discreto(g_v, max_val=20)


def _log_discreto(g_v, max_val=20):
    """Fuerza bruta para encontrar v tal que G_Q^v = g_v mod P."""
    for v in range(max_val + 1):
        if pow(G_Q, v, P) == g_v:
            return v
    return None


def suma_homomorfica(cifrados):
    """
    Suma homomórfica: multiplica todos los (a, b) componente a componente.

    ∏ a_i = g^(Σ r_i)      ∏ b_i = pk^(Σ r_i) · g^(Σ v_i)
    """
    a_total = 1
    b_total = 1
    for a_i, b_i in cifrados:
        a_total = (a_total * a_i) % P
        b_total = (b_total * b_i) % P
    return a_total, b_total


def descifrar_suma(a_total, b_total, sk):
    """Descifra una suma homomórfica. Retorna g^(suma de votos)."""
    a_sk = pow(a_total, sk, P)
    a_sk_inv = pow(a_sk, P - 2, P)
    return (b_total * a_sk_inv) % P


# ═══════════════════════════════════════════════════════════════════════════════
# PRUEBA ZK DISYUNTIVA (OR proof)
# Demuestra que el valor encriptado v ∈ {0, 1, ..., max_candidato}
# SIN revelar cuál es.
#
# Técnica: prueba de Chaum-Pedersen (igualdad de log discretos)
# combinada con OR-proof de Cramer-Damgård-Schoenmakers (CDS'94)
# hecha no-interactiva vía Fiat-Shamir.
# ═══════════════════════════════════════════════════════════════════════════════

def crear_prueba_zk(a, b, voto, r, pk, n_candidatos):
    """
    Crea una prueba ZK disyuntiva de que el cifrado (a, b) contiene
    un valor en {0, 1, ..., n_candidatos}.

    Parámetros
    ----------
    a, b : int
        Cifrado ElGamal.
    voto : int
        Valor real encriptado (0 = falso, 1..N = candidato).
    r : int
        Aleatoriedad usada en la encriptación.
    pk : int
        Clave pública de la autoridad.
    n_candidatos : int
        Número de candidatos. El rango probado es {0 .. n_candidatos}.

    Retorna
    -------
    prueba : list[tuple[int, int]]
        Lista de pares (c_j, s_j), uno por cada valor posible (incluye 0).
        En total n_candidatos + 1 pares.
    """
    assert 0 <= voto <= n_candidatos, f"voto={voto} fuera de rango 0..{n_candidatos}"

    n = n_candidatos + 1   # cantidad de valores posibles (incluye el 0)

    c = [0] * n
    s = [0] * n
    A = [0] * n
    B = [0] * n

    # ── Rama REAL (índice = voto) ──
    w = secrets.randbelow(Q - 1) + 1
    A[voto] = pow(G_Q, w, P)
    B[voto] = pow(pk, w, P)

    # ── Ramas FALSAS (j ≠ voto): simuladas ──
    for j in range(n):
        if j == voto:
            continue
        c[j] = secrets.randbelow(Q)
        s[j] = secrets.randbelow(Q)

        # A_j = g^{s_j} · a^{-c_j}
        a_neg_c = pow(a, Q - c[j], P)
        A[j] = (pow(G_Q, s[j], P) * a_neg_c) % P

        # B_j = pk^{s_j} · (b · g^{-j})^{-c_j}
        g_neg_j = pow(G_Q, Q - j, P)
        b_por_g_neg = (b * g_neg_j) % P
        b_neg_c = pow(b_por_g_neg, Q - c[j], P)
        B[j] = (pow(pk, s[j], P) * b_neg_c) % P

    # ── Desafío global (Fiat-Shamir) ──
    desafio = _hash_prueba(A, B, a, b, pk)

    # ── Completar rama real ──
    suma_c_falsos = sum(c[j] for j in range(n) if j != voto) % Q
    c[voto] = (desafio - suma_c_falsos) % Q
    s[voto] = (w + c[voto] * r) % Q

    return list(zip(c, s))


def verificar_prueba_zk(a, b, prueba, pk, n_candidatos):
    """
    Verifica una prueba ZK disyuntiva.

    Retorna True si la prueba es válida (el valor encriptado está en rango).
    """
    n = n_candidatos + 1

    if len(prueba) != n:
        return False

    A = [0] * n
    B = [0] * n

    for j, (c_j, s_j) in enumerate(prueba):
        c_j = c_j % Q
        s_j = s_j % Q

        # Reconstruir A_j = g^{s_j} · a^{-c_j}
        a_neg_c = pow(a, Q - c_j, P)
        A[j] = (pow(G_Q, s_j, P) * a_neg_c) % P

        # Reconstruir B_j = pk^{s_j} · (b · g^{-j})^{-c_j}
        g_neg_j = pow(G_Q, Q - j, P)
        b_por_g_neg = (b * g_neg_j) % P
        b_neg_c = pow(b_por_g_neg, Q - c_j, P)
        B[j] = (pow(pk, s_j, P) * b_neg_c) % P

    # Verificar que Σ c_j ≡ hash (mod Q)
    desafio = _hash_prueba(A, B, a, b, pk)
    suma_c = sum(c_j for c_j, _ in prueba) % Q

    return suma_c == desafio


def _hash_prueba(A, B, a, b, pk):
    """Hash Fiat-Shamir de todos los compromisos de la prueba."""
    partes = []
    for av, bv in zip(A, B):
        partes.append(f"{av},{bv}")
    partes.append(f"{a},{b},{pk}")
    datos = "|".join(partes)
    h = hashlib.sha256(datos.encode()).digest()
    return int.from_bytes(h, "big") % Q

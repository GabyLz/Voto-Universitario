# Guía Completa de Implementación: Bot de Telegram para Voto Digital Universitario (UNT Hackathon)

---

## 📋 Tabla de Contenidos
1. [Configuración Inicial del Bot de Telegram](#1-configuración-inicial-del-bot-de-telegram)
2. [Estructura del Proyecto](#2-estructura-del-proyecto)
3. [Instalación y Ejecución](#3-instalación-y-ejecución)
4. [Sistema de Registro y Verificación](#4-sistema-de-registro-y-verificación)
5. [Voto Anónimo Seguro con Ruido Criptográfico](#5-voto-anónimo-seguro-con-ruido-criptográfico)
6. [Blockchain Simulada (Sin Implementación Real)](#6-blockchain-simulada-sin-implementación-real)
7. [Pruebas y Validación](#7-pruebas-y-validación)
8. [Plan de Evolución a Blockchain Real](#8-plan-de-evolución-a-blockchain-real)

---

## 1. Configuración Inicial del Bot de Telegram

### Paso 1: Registrar el bot en BotFather
1. Abre Telegram y busca a **@BotFather**
2. Envía `/newbot` y sigue las instrucciones:
   - Nombre del bot: `SistemaVotoUNT_bot` (ejemplo)
   - Username: `SistemaVotoUNT_bot` (debe terminar en `_bot`)
3. **IMPORTANTE**: Guarda el token de acceso que te entrega BotFather (ej: `123456789:ABCdefGhIJKlmNoPQRStuVWxyZ`)

### Paso 2: Configurar comandos básicos
Envía `/setcommands` a BotFather y pega esta lista:
```
start - Iniciar el bot y ver información
registro - Registrarse y votar
resultados - Ver resultados parciales
anomalias - Ver análisis de IA (solo admin)
reset - Reiniciar votación (solo admin)
```

### Paso 3: Configurar seguridad básica
- En `config.py`, reemplaza `TU_TOKEN_AQUI` con tu token real
- En `bot.py` (línea 18), agrega tu ID de Telegram a `ADMIN_IDS` (para comandos de administrador)

---

## 2. Estructura del Proyecto

```
BOT VOTO/
├── bot.py                 # Código principal del bot
├── config.py              # Token del bot
├── blockchain_sim.py      # Simulación de blockchain
├── noise_generator.py     # Generador de ruido criptográfico
├── anomaly_detector.py    # Detector de anomalías con IA
├── padron.json            # Padrón electoral simulado
├── requirements.txt       # Dependencias del proyecto
└── GUIA_COMPLETA.md       # Esta guía
```

### Descripción de cada archivo:
| Archivo | Función |
|---------|---------|
| `bot.py` | Lógica principal del bot, manejo de comandos y conversaciones |
| `config.py` | Almacena el token de acceso del bot |
| `blockchain_sim.py` | Simula una blockchain para inmutabilidad de votos |
| `noise_generator.py` | Genera votos falsos para proteger el anonimato |
| `anomaly_detector.py` | Analiza patrones de votación para detectar anomalías |
| `padron.json` | Base de datos simulada de votantes habilitados |

---

## 3. Instalación y Ejecución

### Requisitos previos
- Python 3.9 o superior
- pip (gestor de paquetes de Python)

### Paso 1: Instalar dependencias
Abre una terminal en el directorio del proyecto y ejecuta:
```powershell
pip install -r requirements.txt
```

### Paso 2: Configurar el token
Edita el archivo `config.py` y agrega tu token:
```python
TOKEN = "TU_TOKEN_REAL_AQUI"
```

### Paso 3: Ejecutar el bot
```powershell
python bot.py
```

Si todo sale bien, verás el mensaje: `Bot iniciado...`

---

## 4. Sistema de Registro y Verificación

### Flujo de registro
1. El usuario envía `/registro` al bot
2. El bot pide el **código universitario**
3. Se valida el código contra `padron.json`
4. Si es válido y no ha votado, se muestra la lista de candidatos

### Características clave de seguridad
- ✅ Solo verifica que el código exista en el padrón
- ✅ Marca `voto_emitido: true` para prevenir votos duplicados
- ✅ **NO GUARDA NINGUNA RELACIÓN entre el ID de Telegram y el voto emitido**
- ✅ El voto se registra en la blockchain simulada sin datos identificatorios

### Padrón electoral (`padron.json`)
```json
{
  "12345678": {"nombre": "Carlos López", "rol": "docente", "voto_emitido": false},
  "87654321": {"nombre": "Ana Torres", "rol": "estudiante", "voto_emitido": false},
  "11111111": {"nombre": "Admin CEUA", "rol": "admin", "voto_emitido": false}
}
```

---

## 5. Voto Anónimo Seguro con Ruido Criptográfico

### ¿Cómo funciona el anonimato?
1. **Separación total**: El padrón solo marca "ya votó", sin guardar el voto
2. **Blockchain simulada**: Almacena votos sin datos de identidad
3. **Ruido criptográfico**: Votos falsos aleatorios que se mezclan con los reales

### Ruido criptográfico (técnica de mitigación de correlación)
- Después de cada voto real, se inyectan **1-5 votos falsos** aleatorios
- Cada 30 segundos, se inyectan **1-3 votos falsos** adicionales
- Los votos falsos se marcan con `es_falso: true` y no se incluyen en los resultados finales
- **Proporción recomendada**: ~30-50% de ruido vs votos reales

### ¿Por qué funciona?
Imagina que un atacante obtiene acceso a la base de datos:
- Ve 100 votos, pero no sabe cuáles son reales y cuáles son falsos
- No puede correlacionar el momento del voto con el usuario
- La distribución de votos falsos es estadísticamente similar a la real

---

## 6. Blockchain Simulada (Sin Implementación Real)

### ¿Qué replica?
| Característica | Implementación |
|----------------|----------------|
| **Inmutabilidad** | Cada bloque tiene un hash SHA-256 que depende del bloque anterior |
| **Transparencia** | Los resultados se calculan solo con votos reales |
| **Auditabilidad** | Los bloques se pueden verificar hash por hash |

### Clase `BlockchainSim` (`blockchain_sim.py`)
```python
class Bloque:
    - index: Número de bloque
    - timestamp: Hora del voto
    - datos: {candidato, rol, peso}
    - hash_anterior: Hash del bloque previo
    - es_falso: Indica si es ruido
    - hash: Hash SHA-256 del bloque

class BlockchainSim:
    - agregar_voto(): Añade un voto a la cadena
    - obtener_resultados_reales(): Calcula resultados sin ruido
```

---

## 7. Pruebas y Validación

### Pruebas funcionales obligatorias
1. **Prueba de voto único**: Usa el mismo código dos veces → debe fallar
2. **Prueba de anonimato**: Revisa `padron.json` → no hay información del voto
3. **Prueba de ruido**: Vota y revisa la blockchain → hay votos falsos
4. **Prueba de resultados**: Vota por un candidato → resultados deben reflejarlo

### Cómo ejecutar las pruebas manualmente
1. Abre el bot en Telegram y envía `/start`
2. Usa un código del padrón (ej: `12345678`)
3. Vota por un candidato
4. Usa `/resultados` para ver los resultados
5. Usa el mismo código nuevamente → debe decir "Ya has votado"

---

## 8. Plan de Evolución a Blockchain Real

### Etapa 1: Migrar a una red de prueba
- Usar **Hyperledger Fabric** (permisionado, ideal para consorcios universitarios)
- O **Ethereum Testnet** (Goerli/Sepolia) para prototipos públicos

### Etapa 2: Smart Contracts
- Implementar un contrato que:
  1. Valide que el votante está habilitado (sin revelar identidad)
  2. Registre el voto hashado
  3. Impida votos duplicados

### Etapa 3: Zero-Knowledge Proofs (ZKPs)
- Usar **zk-SNARKs** o **zk-STARKs** para:
  - Probar que el votante está habilitado **sin revelar su identidad**
  - Probar que el voto es válido **sin revelar el candidato**

---

## 📊 Resumen de Medidas de Seguridad
| Medida | Objetivo |
|--------|----------|
| Padrón separado | Evitar vinculación voto-identidad |
| Ruido criptográfico | Mitigar ataques de correlación |
| Blockchain simulada | Garantizar inmutabilidad |
| Análisis de anomalías | Detectar manipulación masiva |

---

## 🎯 Guía de Presentación para Hackathon
1. **Demo en vivo**: Muestra el flujo completo de registro y voto
2. **Resalta seguridad**: Explica el ruido criptográfico y la separación voto-identidad
3. **Muestra código**: Abre `bot.py` y `blockchain_sim.py` para demostrar la implementación
4. **Plan futuro**: Menciona la evolución a blockchain real

¡Éxito en el hackathon! 🚀

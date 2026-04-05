# 🚀 Odoo AI Tutor - Guía Completa de Testing

**Versión:** 2.0.0  
**Última actualización:** 27 de Enero de 2026  
**Autor:** Backend Development Team

---

## 📋 Tabla de Contenidos

1. [Configuración Inicial](#1-configuración-inicial)
2. [Health Check](#2-health-check)
3. [Crear Ejercicio de Prueba](#3-crear-ejercicio-de-prueba)
4. [Obtener Step del Ejercicio](#4-obtener-step-del-ejercicio)
5. [Obtener Contexto de Instrucción](#5-obtener-contexto-de-instrucción)
6. [Conectar WebSocket](#6-conectar-websocket)
7. [Enviar Mensaje de Chat](#7-enviar-mensaje-de-chat)
8. [Responder a Confirmación](#8-responder-a-confirmación)
9. [Navegar a Siguiente Step](#9-navegar-a-siguiente-step)
10. [Enviar Evento de UI](#10-enviar-evento-de-ui)
11. [Enviar Evento de Feedback](#11-enviar-evento-de-feedback)
12. [Actualizar Contexto](#12-actualizar-contexto)
13. [Obtener Interacciones del Usuario](#13-obtener-interacciones-del-usuario)
14. [Búsqueda Semántica](#14-búsqueda-semántica)
15. [Obtener Interacciones de Sesión](#15-obtener-interacciones-de-sesión)
16. [Troubleshooting](#troubleshooting)
17. [Notas Importantes](#notas-importantes)

---

## 1. Configuración Inicial

### 1.1 Requisitos Previos

- **Postman** v10+ (descarga desde [postman.com](https://www.postman.com))
- **Python 3.10+** instalado
- **Backend corriendo** en `http://localhost:8000`
- **Redis** corriendo en `redis://localhost:6379`
- **ChromaDB** configurado (Cloud o Local)

### 1.2 Iniciar el Backend

```bash
cd d:\odoo_concepts\odoo-tutor-backend
python -m uvicorn ms_ai.app.main:app --reload --host 0.0.0.0 --port 8000
```

**Output esperado:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### 1.3 Importar Colección en Postman

1. Abre Postman
2. Ve a `File` → `Import`
3. Selecciona `Odoo-AI-Tutor-Testing.postman_collection.json`
4. Haz clic en **Import**

### 1.4 Configurar Variables

En Postman, ve a la colección y abre la pestaña **Variables**:

| Variable | Valor | Descripción |
|----------|-------|-------------|
| `base_url` | `http://localhost:8002` | URL base del backend |
| `api_key` | `your-super-secret-key-123` | API Key desde `.env` |
| `user_login` | `user.test@example.com` | Usuario de prueba |
| `db` | `test_db` | Base de datos |
| `exercise_id` | `ex-create-quotation` | ID del ejercicio |
| `session_id` | `test-session-001` | ID de sesión (se actualiza) |
| `interaction_id` | `` | ID de interacción (se actualiza) |

---

## ✅ 2. Health Check

**Objetivo:** Verificar que el backend está corriendo y todos los servicios conectados.

### Request

```
Method: GET
URL: {{base_url}}/health
Headers:
  Content-Type: application/json
```

### Pasos en Postman

1. Abre la carpeta **🔧 Setup**
2. Haz clic en **✅ 1. Health Check**
3. Haz clic en **Send**

### Response Esperado (200)

```json
{
  "status": "healthy",
  "timestamp": "2026-01-27T15:30:45.123456",
  "redis": "connected",
  "active_websockets": 0,
  "llm_model": "gpt-4o-2024-11-20",
  "chroma": "connected"
}
```

### ✅ Validaciones

- [ ] Status es `healthy`
- [ ] Redis está conectado
- [ ] LLM model es `gpt-4o-2024-11-20`
- [ ] ChromaDB está conectado

---

## ✅ 3. Crear Ejercicio de Prueba

**Objetivo:** Guardar un ejercicio estructurado en ChromaDB con 5 pasos.

### Request

```
Method: POST
URL: {{base_url}}/test/create-exercise
Headers:
  Content-Type: application/json
  x-api-key: {{api_key}}
```

### Pasos en Postman

1. Abre la carpeta **🔧 Setup**
2. Haz clic en **✅ 2. Create Test Exercise**
3. Haz clic en **Send**

### Response Esperado (200)

```json
{
  "message": "✅ Test exercise created successfully",
  "exercise_id": "ex-create-quotation",
  "steps": 5,
  "timestamp": "2026-01-27T15:30:46.123456"
}
```

### 📝 Estructura del Ejercicio Creado

```
Exercise: ex-create-quotation
├── Step 1: ex-create-quotation_step-001
│   └── "Go to **Sales > Quotations**. Click **New**."
├── Step 2: ex-create-quotation_step-002
│   └── "Create a new customer named **Company**."
├── Step 3: ex-create-quotation_step-003
│   └── "Add products: Consulting Hours (10 units at $20/unit)..."
├── Step 4: ex-create-quotation_step-004
│   └── "Apply a 10% discount to the total order."
└── Step 5: ex-create-quotation_step-005
    └── "Save the quotation."
```

### ✅ Validaciones

- [ ] Respuesta es 200
- [ ] `exercise_id` es `ex-create-quotation`
- [ ] `steps` es 5
- [ ] Ejercicio está guardado en ChromaDB

---

## ✅ 4. Obtener Step del Ejercicio

**Objetivo:** Recuperar un step específico del ejercicio.

### Request

```
Method: GET
URL: {{base_url}}/exercise/{{exercise_id}}/step/1
Headers:
  Content-Type: application/json
  x-api-key: {{api_key}}
```

### Pasos en Postman

1. Abre la carpeta **📚 REST API - Exercises**
2. Haz clic en **✅ 3. Get Exercise Step**
3. Haz clic en **Send**

### Response Esperado (200)

```json
{
  "exercise_id": "ex-create-quotation",
  "step": {
    "step_id": "ex-create-quotation_step-001",
    "step_order": 1,
    "instruction": "Go to **Sales > Quotations**. Click **New**.",
    "expected_action": {
      "model": "sale.order",
      "action": "create",
      "metadata": {
        "view_type": "form"
      }
    },
    "hints": ["You can access Sales from the main menu."],
    "exercise_id": "ex-create-quotation"
  },
  "timestamp": "2026-01-27T15:30:47.123456"
}
```

### ✅ Validaciones

- [ ] Respuesta es 200
- [ ] `step_id` es correcto
- [ ] `instruction` no está vacía
- [ ] `expected_action` contiene modelo y acción

### 🔧 Pruebas Adicionales

Cambia el número de step en la URL para probar:
- `/exercise/ex-create-quotation/step/2`
- `/exercise/ex-create-quotation/step/3`
- `/exercise/ex-create-quotation/step/4`
- `/exercise/ex-create-quotation/step/5`

---

## ✅ 5. Obtener Contexto de Instrucción

**Objetivo:** Recuperar el contexto completo de una instrucción incluyendo steps anteriores y siguientes.

### Request

```
Method: GET
URL: {{base_url}}/exercise/{{exercise_id}}/step-context/ex-create-quotation_step-002
Headers:
  Content-Type: application/json
  x-api-key: {{api_key}}
```

### Pasos en Postman

1. Abre la carpeta **📚 REST API - Exercises**
2. Haz clic en **✅ 4. Get Step Context**
3. Haz clic en **Send**

### Response Esperado (200)

```json
{
  "exercise_id": "ex-create-quotation",
  "context": {
    "exercise_id": "ex-create-quotation",
    "exercise_goal": "Learn how to create a sales quotation from scratch for a new B2B customer.",
    "module": "sales",
    "current_step": {
      "step_id": "ex-create-quotation_step-002",
      "step_order": 2,
      "instruction": "Create a new customer named **Company**.",
      "expected_action": {
        "model": "res.partner",
        "action": "create"
      },
      "hints": ["Click on the customer field and select 'Create and Edit'."]
    },
    "previous_step": {
      "step_id": "ex-create-quotation_step-001",
      "instruction": "Go to **Sales > Quotations**. Click **New**."
    },
    "next_step": {
      "step_id": "ex-create-quotation_step-003",
      "instruction": "Add the following products: Consulting Hours (10 units at $20/unit)..."
    }
  },
  "timestamp": "2026-01-27T15:30:48.123456"
}
```

### ✅ Validaciones

- [ ] Respuesta es 200
- [ ] `current_step` contiene la instrucción correcta
- [ ] `previous_step` existe y es diferente a `current_step`
- [ ] `next_step` existe y es diferente a `current_step`
- [ ] `exercise_goal` está presente

---

## ✅ 6. Conectar WebSocket

**Objetivo:** Establecer conexión WebSocket para comunicación en tiempo real.

### Request

```
Method: WebSocket (GET)
URL: ws://localhost:8000/ws?session_id=test-session-001&user_login=user.test@example.com&db=test_db
```

### Pasos en Postman

1. Abre la carpeta **🔌 WebSocket - Real-time Communication**
2. Haz clic en **✅ 5. WebSocket Connect**
3. Cambia el protocolo a **WebSocket** (abajo a la izquierda)
4. Haz clic en **Connect**

### Response Esperado (Status 101)

```json
{
  "type": "connection_established",
  "session_id": "test-session-001",
  "user_login": "user.test@example.com",
  "timestamp": 1706345678.123
}
```

### 📌 Importante

Cuando se conecte, verás un **ícono verde** y la opción de **Disconnect**. Eso significa que la conexión es exitosa.

### ✅ Validaciones

- [ ] Status es 101 (WebSocket Upgrade)
- [ ] `type` es `connection_established`
- [ ] `session_id` está presente
- [ ] El ícono está verde

### 🔄 Mantener la Conexión Abierta

**NO desconectes aún.** Necesitas esta conexión abierta para los próximos pasos.

---

## ✅ 7. Enviar Mensaje de Chat

**Objetivo:** Enviar un mensaje de chat que dispare la detección de ejercicios y confirmación.

### Request

```
WebSocket Message:
{
  "type": "chat",
  "message": "How do I create a sales quotation in Odoo?",
  "context": {
    "model": "sale.order"
  }
}
```

### Pasos en Postman

1. Asegúrate de que WebSocket está conectado (de pasos anteriores)
2. En el campo **Message** escribe el JSON anterior
3. Haz clic en **Send**

### Respuesta Inmediata (ACK)

```json
{
  "type": "chat_response",
  "response": "Processing your request...",
  "exercise_id": null,
  "fallback": false,
  "interaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1706345679.456,
  "status": "processing"
}
```

### Respuesta Posterior (1-2 segundos)

```json
{
  "type": "chat_response_complete",
  "response": "Would you like step-by-step instructions for creating a sales quotation?",
  "exercise_id": "ex-create-quotation",
  "fallback": false,
  "interaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": 1706345680.789,
  "status": "complete"
}
```

### ✅ Validaciones

- [ ] Primera respuesta tiene `interaction_id`
- [ ] Segunda respuesta tiene `exercise_id`
- [ ] `type` es `chat_response_complete`
- [ ] `response` no está vacía
- [ ] Mensajes llegan en WebSocket

### 💾 Guardar interaction_id

Copia el `interaction_id` de la respuesta y guárdalo en una variable de Postman:

```
{{interaction_id}} = "550e8400-e29b-41d4-a716-446655440000"
```

---

## ✅ 8. Responder a Confirmación

**Objetivo:** Responder "yes" a la confirmación del ejercicio para comenzar.

### Request

```
WebSocket Message:
{
  "type": "chat",
  "message": "yes",
  "context": {
    "model": "sale.order"
  }
}
```

### Pasos en Postman

1. En el mismo WebSocket, escribe el JSON anterior en **Message**
2. Haz clic en **Send**

### Respuesta Esperada

```json
{
  "type": "chat_response",
  "response": "Step 1 of 5: Go to **Sales > Quotations**. Click **New**.\n\nHints: You can access Sales from the main menu.",
  "exercise_id": "ex-create-quotation",
  "current_step": 1,
  "fallback": false,
  "interaction_id": "550e8400-e29b-41d4-a716-446655440001",
  "timestamp": 1706345681.234,
  "status": "complete"
}
```

### ✅ Validaciones

- [ ] `current_step` es 1
- [ ] `response` incluye "Step 1 of 5"
- [ ] `exercise_id` es `ex-create-quotation`
- [ ] Nueva `interaction_id` generada

### 📝 Notas

- La sesión ahora está en modo `exercise_active`
- El estado se guardó en Redis
- Estás listo para avanzar al siguiente step

---

## ✅ 9. Navegar a Siguiente Step

**Objetivo:** Usar "next" o "n" para avanzar al siguiente step del ejercicio.

### Request

```
WebSocket Message:
{
  "type": "chat",
  "message": "next",
  "context": {
    "model": "sale.order"
  }
}
```

### Pasos en Postman

1. En el mismo WebSocket, escribe el JSON anterior en **Message**
2. Haz clic en **Send**

### Respuesta Esperada

```json
{
  "type": "chat_response",
  "response": "Step 2 of 5: Create a new customer named **Company**.\n\nHints: Click on the customer field and select 'Create and Edit'.",
  "exercise_id": "ex-create-quotation",
  "current_step": 2,
  "fallback": false,
  "interaction_id": "550e8400-e29b-41d4-a716-446655440002",
  "timestamp": 1706345682.456,
  "status": "complete"
}
```

### ✅ Validaciones

- [ ] `current_step` cambió a 2
- [ ] `response` incluye "Step 2 of 5"
- [ ] Nueva `interaction_id` generada
- [ ] Instrucción es diferente al step anterior

### 🔄 Repetir

Repite este paso 3 veces más para recorrer todos los steps:

```
Mensajes a enviar:
1. "next" → Step 2
2. "next" → Step 3
3. "next" → Step 4
4. "next" → Step 5
```

---

## ✅ 10. Enviar Evento de UI

**Objetivo:** Enviar eventos UI (clicks de botones, cambios de vista, etc.) que se guardan como interacciones.

### Request

```
WebSocket Message:
{
  "type": "ui_event",
  "event_name": "button_click",
  "event_data": {
    "button_name": "save",
    "model": "sale.order",
    "timestamp": 1706345683.000
  }
}
```

### Pasos en Postman

1. En el mismo WebSocket, escribe el JSON anterior en **Message**
2. Haz clic en **Send**

### Respuesta Esperada

```json
{
  "type": "ui_event_acknowledged",
  "event_name": "button_click",
  "interaction_id": "550e8400-e29b-41d4-a716-446655440003",
  "timestamp": 1706345683.789
}
```

### ✅ Validaciones

- [ ] `type` es `ui_event_acknowledged`
- [ ] `event_name` es `button_click`
- [ ] `interaction_id` fue generado
- [ ] Evento se guardó en ChromaDB

### 🔄 Otros Eventos UI

Prueba otros eventos:

```json
{
  "type": "ui_event",
  "event_name": "field_change",
  "event_data": {
    "field_name": "customer_id",
    "model": "sale.order",
    "value": "Company Inc"
  }
}
```

```json
{
  "type": "ui_event",
  "event_name": "view_change",
  "event_data": {
    "previous_view": "form",
    "current_view": "list",
    "model": "sale.order"
  }
}
```

---

## ✅ 11. Enviar Evento de Feedback

**Objetivo:** Enviar feedback sobre instrucciones confusas o problemas técnicos. El backend encontrará automáticamente la instrucción correspondiente.

### Request - Feedback Unclear

```
WebSocket Message:
{
  "type": "feedback_event",
  "event_name": "ai_feedback_unclear",
  "event_data": {
    "comment": "This step is confusing. I don't know where to find the customer field.",
    "context": {
      "model": "sale.order",
      "view": "form",
      "mode": "edit"
    },
    "error": "",
    "message_body_html": "<p>This instruction is not clear</p>",
    "message_body_text": "This instruction is not clear",
    "message_uid": "031761a0-bcbd-4a5b-82c9-4253366b02f2",
    "rpc_result": "",
    "saved_to_odoo": false,
    "timestamp": "2026-01-27T22:11:35.3942",
    "vote": ""
  }
}
```

### Pasos en Postman

1. Asegúrate de que estés en Step 2 (ejecutando 3 × "next")
2. En el mismo WebSocket, escribe el JSON anterior en **Message**
3. Haz clic en **Send**

### Respuesta Inmediata

```json
{
  "type": "feedback_acknowledged",
  "event_name": "ai_feedback_unclear",
  "interaction_id": "550e8400-e29b-41d4-a716-446655440004",
  "instruction_found": true,
  "timestamp": 1706345684.234
}
```

### Respuesta Posterior (Background Processing)

```json
{
  "type": "instruction_modification_initiated",
  "interaction_id": "550e8400-e29b-41d4-a716-446655440004",
  "step_id": "ex-create-quotation_step-002",
  "status": "processing",
  "message": "Processing ai_feedback_unclear. Your feedback will be used to improve this instruction.",
  "timestamp": 1706345685.000
}
```

### ✅ Validaciones

- [ ] `type` es `feedback_acknowledged`
- [ ] `instruction_found` es `true`
- [ ] `step_id` es correcto: `ex-create-quotation_step-002`
- [ ] `interaction_id` fue generado
- [ ] Segunda respuesta indica que se está procesando

### 📝 Log en Backend

Deberías ver en la terminal:

```
🔍 Processing feedback modification:
  Exercise: ex-create-quotation
  Step ID: ex-create-quotation_step-002
  Feedback Type: ai_feedback_unclear
  Comment: This step is confusing...
✅ Feedback modification pipeline initiated: interaction_id=550e...
```

### 🔄 Otro Tipo de Feedback

```
WebSocket Message:
{
  "type": "feedback_event",
  "event_name": "ai_feedback_technical_issue",
  "event_data": {
    "comment": "I got an error when trying to save the quotation",
    "error": "Database connection error",
    ...
  }
}
```

---

## ✅ 12. Actualizar Contexto

**Objetivo:** Actualizar el contexto de sesión (modelo actual, vista, departamento, etc.).

### Request

```
WebSocket Message:
{
  "type": "context_update",
  "context": {
    "model": "project.project",
    "view": "kanban",
    "department": "IT"
  }
}
```

### Pasos en Postman

1. En el mismo WebSocket, escribe el JSON anterior en **Message**
2. Haz clic en **Send**

### Respuesta Esperada

```json
{
  "type": "context_updated",
  "message": "Context updated successfully",
  "context": {
    "model": "project.project",
    "view": "kanban",
    "department": "IT"
  },
  "timestamp": 1706345686.234
}
```

### ✅ Validaciones

- [ ] `type` es `context_updated`
- [ ] Contexto en la respuesta coincide con lo enviado
- [ ] Timestamp es reciente

### 📝 Uso

Este contexto se usa para:
- Personalizar respuestas del chat según el módulo actual
- Trackear en qué vista estaba el usuario
- Mejorar las sugerencias de ejercicios

---

## ✅ 13. Obtener Interacciones del Usuario

**Objetivo:** Recuperar todas las interacciones guardadas para un usuario específico.

### Request

```
Method: GET
URL: {{base_url}}/user/interactions?user_login={{user_login}}&interaction_type=chat&limit=10
Headers:
  x-api-key: {{api_key}}
```

### Pasos en Postman

1. **Desconecta el WebSocket primero** (haz clic en Disconnect)
2. Abre la carpeta **📊 REST API - Analytics**
3. Haz clic en **✅ 12. Get User Interactions**
4. Haz clic en **Send**

### Response Esperado (200)

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "document": "How do I create a sales quotation in Odoo?",
    "metadata": {
      "user_login": "user.test@example.com",
      "session_id": "test-session-001",
      "interaction_type": "chat",
      "timestamp": "2026-01-27T15:30:47.123456",
      "interaction_id": "550e8400-e29b-41d4-a716-446655440000",
      "message_length": 48
    }
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "document": "Step 1 of 5: Go to **Sales > Quotations**. Click **New**...",
    "metadata": {
      "user_login": "user.test@example.com",
      "session_id": "test-session-001",
      "interaction_type": "chat",
      "timestamp": "2026-01-27T15:30:48.123456",
      "interaction_id": "550e8400-e29b-41d4-a716-446655440001"
    }
  },
  ...
]
```

### ✅ Validaciones

- [ ] Respuesta es 200
- [ ] Array contiene múltiples interacciones
- [ ] Cada interacción tiene `id` e `interaction_id`
- [ ] `metadata` contiene usuario, sesión, tipo
- [ ] `document` contiene el texto del mensaje

### 🔧 Filtros Disponibles

Prueba con diferentes parámetros:

```
# Solo chat
/user/interactions?user_login=user.test@example.com&interaction_type=chat

# Solo feedback
/user/interactions?user_login=user.test@example.com&interaction_type=feedback_event

# Solo UI events
/user/interactions?user_login=user.test@example.com&interaction_type=ui_event

# Todos
/user/interactions?user_login=user.test@example.com&limit=50
```

---

## ✅ 14. Búsqueda Semántica

**Objetivo:** Hacer búsqueda semántica sobre interacciones del usuario usando ChromaDB.

### Request

```
Method: POST
URL: {{base_url}}/user/interactions/search?user_login={{user_login}}&query=quotation&n_results=5
Headers:
  x-api-key: {{api_key}}
```

### Pasos en Postman

1. Abre la carpeta **📊 REST API - Analytics**
2. Haz clic en **✅ 13. Search Interactions (Semantic Search)**
3. Haz clic en **Send**

### Response Esperado (200)

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "document": "How do I create a sales quotation in Odoo?",
    "metadata": {
      "user_login": "user.test@example.com",
      "session_id": "test-session-001",
      "interaction_type": "chat",
      "timestamp": "2026-01-27T15:30:47.123456"
    },
    "similarity_score": 0.92
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440002",
    "document": "Step 3 of 5: Add products: Consulting Hours (10 units at $20/unit), Hosting Service...",
    "metadata": {...},
    "similarity_score": 0.78
  }
]
```

### ✅ Validaciones

- [ ] Respuesta es 200
- [ ] Resultados contienen `similarity_score`
- [ ] Score está entre 0 y 1
- [ ] Resultados están ordenados por similaridad (descendente)
- [ ] Documentos son relevantes al query "quotation"

### 🔍 Pruebas de Búsqueda

Cambia el parámetro `query` para probar:

```
# Buscar por producto
/user/interactions/search?user_login=user.test@example.com&query=products

# Buscar por acción
/user/interactions/search?user_login=user.test@example.com&query=create customer

# Buscar por descuento
/user/interactions/search?user_login=user.test@example.com&query=discount

# Buscar por error
/user/interactions/search?user_login=user.test@example.com&query=error technical issue

# Más resultados
/user/interactions/search?user_login=user.test@example.com&query=quotation&n_results=20
```

### 💡 Caso de Uso

Útil para:
- Encontrar preguntas anteriores similares
- Agrupar problemas por tema
- Mejorar las sugerencias de ayuda
- Análisis de patrones de comportamiento del usuario

---

## ✅ 15. Obtener Interacciones de Sesión

**Objetivo:** Recuperar todas las interacciones de una sesión específica.

### Request

```
Method: GET
URL: {{base_url}}/session/test-session-001/interactions?user_login={{user_login}}
Headers:
  x-api-key: {{api_key}}
```

### Pasos en Postman

1. Abre la carpeta **📊 REST API - Analytics**
2. Haz clic en **✅ 14. Get Session Interactions**
3. Modifica `test-session-001` con tu `session_id` si es diferente
4. Haz clic en **Send**

### Response Esperado (200)

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "document": "How do I create a sales quotation in Odoo?",
    "metadata": {
      "user_login": "user.test@example.com",
      "session_id": "test-session-001",
      "interaction_type": "chat",
      "timestamp": "2026-01-27T15:30:47.123456",
      "interaction_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "document": "yes",
    "metadata": {
      "user_login": "user.test@example.com",
      "session_id": "test-session-001",
      "interaction_type": "chat",
      "timestamp": "2026-01-27T15:30:48.234567"
    }
  },
  {
    "id": "550e8400-e29b-41d4-a716-446655440003",
    "document": "button_click on save",
    "metadata": {
      "user_login": "user.test@example.com",
      "session_id": "test-session-001",
      "interaction_type": "ui_event",
      "timestamp": "2026-01-27T15:30:49.345678"
    }
  }
]
```

### ✅ Validaciones

- [ ] Respuesta es 200
- [ ] Todos los items tienen `session_id = test-session-001`
- [ ] `user_login` es consistente
- [ ] Contiene mezcla de `chat`, `ui_event` e `interaction_type`s
- [ ] Timestamps son progresivos

### 📊 Diferencia

| Endpoint | Describe |
|----------|----------|
| `/user/interactions` | **Todas** las interacciones de un usuario (todas las sesiones) |
| `/session/{session_id}/interactions` | **Solo** interacciones de una sesión específica |

---

## 🐛 Troubleshooting

### Problema 1: Backend no responde (ERR_CONNECTION_REFUSED)

**Error:**
```
Error: connect ECONNREFUSED 127.0.0.1:8000
```

**Solución:**
1. Verifica que el backend está corriendo:
   ```bash
   cd d:\odoo_concepts\odoo-tutor-backend
   python -m uvicorn ms_ai.app.main:app --reload
   ```
2. Verifica el puerto: `http://localhost:8000/health`
3. Si ves error de import, instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```

---

### Problema 2: WebSocket no se conecta (1002 error)

**Error:**
```
WebSocket closed with code 1002
```

**Causas:**
- Falta `session_id` o `user_login` en la URL
- Backend no tiene soporte WebSocket activado

**Solución:**
1. Verifica URL:
   ```
   ws://localhost:8000/ws?session_id=test-001&user_login=user@test.com&db=test_db
   ```
2. Verifica que FastAPI está configurado con WebSocket
3. Reinicia el backend

---

### Problema 3: 401 Unauthorized

**Error:**
```json
{
  "detail": "Invalid or missing API key"
}
```

**Solución:**
1. Verifica que `x-api-key` header está presente
2. Compara el valor con `.env`:
   ```
   API_KEY=your-super-secret-key-123
   ```
3. Actualiza la variable en Postman si es diferente

---

### Problema 4: interaction_id no se genera

**Error:**
```json
{
  "interaction_id": null
}
```

**Causas:**
- ChromaDB no está conectado
- `user_interaction_manager` no está inicializado

**Solución:**
1. Verifica ChromaDB:
   ```python
   # En la terminal Python
   import chromadb
   client = chromadb.HttpClient(host="...", port=...)
   ```
2. Revisa los logs del backend para errores
3. Asegúrate que `CHROMA_API_KEY` está en `.env`

---

### Problema 5: Exercise no aparece en ChromaDB

**Error:**
```json
{
  "error": "Exercise not found",
  "exercise_id": "ex-create-quotation"
}
```

**Solución:**
1. Ejecuta primero el paso **✅ 2. Create Test Exercise**
2. Verifica que la respuesta fue 200
3. Revisa en ChromaDB:
   ```python
   collection = client.get_collection("exercises_structured")
   collection.get(ids=["ex-create-quotation"])
   ```

---

### Problema 6: Redis no conecta

**Error:**
```
ConnectionError: Error -1 connecting to localhost:6379
```

**Solución:**
1. Inicia Redis:
   ```bash
   redis-cli ping
   ```
2. Si no está instalado:
   ```bash
   # Windows (con Docker)
   docker run -d -p 6379:6379 redis:latest
   ```
3. Verifica en `.env`:
   ```
   REDIS_URL=redis://localhost:6379
   ```

---

## 📋 Notas Importantes

### 1. Orden de Ejecución

**Debes** ejecutar los pasos en este orden:

```
1. Health Check (verifica que todo está up)
2. Create Test Exercise (carga el ejercicio)
3. Get Exercise Step (verifica REST API)
4. Get Step Context (verifica contexto)
5. WebSocket Connect (abre conexión)
6. Send Chat Message (inicia conversación)
7. Respond to Confirmation (confirma ejercicio)
8. Navigate Steps (avanza por pasos)
9. Send UI Events (simula interacciones)
10. Send Feedback (prueba feedback mechanism)
11. Update Context (actualiza contexto)
12. Get User Interactions (recupera datos)
13. Search Interactions (búsqueda semántica)
14. Get Session Interactions (sesión específica)
```

---

### 2. Variables Importantes

| Variable | Donde Guardarla | Cuando |
|----------|-----------------|--------|
| `session_id` | Post-request script | Después de conectar WebSocket |
| `interaction_id` | Post-request script | Después de cada mensaje |
| `exercise_id` | Collection variables | Permanente |
| `api_key` | Collection variables | Permanente |
| `user_login` | Collection variables | Permanente |

**Script para guardar automáticamente:**
```javascript
// En la pestaña "Tests" de cada request
if (pm.response.json().session_id) {
    pm.environment.set("session_id", pm.response.json().session_id);
}
if (pm.response.json().interaction_id) {
    pm.environment.set("interaction_id", pm.response.json().interaction_id);
}
```

---

### 3. Timing

- **Health Check**: ~10ms
- **Create Exercise**: ~500ms (primer acceso ChromaDB)
- **Get Exercise Step**: ~100ms
- **WebSocket Connect**: ~200ms
- **Chat Message**: ~2-3 segundos (LLM processing)
- **UI Event**: ~100ms
- **Get User Interactions**: ~500ms

---

### 4. Límites y Consideraciones

| Recurso | Límite | Notas |
|---------|--------|-------|
| Max interactions por usuario | 1000 | Configurable en ChromaDB |
| Max search results | 100 | Por query |
| WebSocket timeout | 30 min | Sin actividad |
| Session TTL | 1 hour | En Redis |
| Message queue | 50 | Por sesión |

---

### 5. Limpieza

**Para limpiar después de las pruebas:**

```bash
# Limpiar Redis
redis-cli FLUSHALL

# Limpiar ChromaDB (opcional)
python -c "
import chromadb
client = chromadb.HttpClient(...)
client.delete_collection('user_interactions')
client.delete_collection('exercises_structured')
"
```

---

### 6. Monitoreo

**Verificar en tiempo real:**

```bash
# Ver logs del backend
# La terminal donde corre el backend muestra logs en vivo

# Monitor Redis
redis-cli MONITOR

# Monitor ChromaDB
# Accede a https://api.trychroma.com dashboard
```

---

### 7. Integración con Frontend Real

Cuando integres con el frontend real:

1. **Reemplaza las variables** de Postman con valores reales
2. **Cambia el protocolo** de `ws://` a `wss://` si usas HTTPS
3. **Configura CORS** correctamente en `main.py`
4. **Maneja reconexión** de WebSocket en el cliente
5. **Implementa retry logic** para fallos de red

---

## 📞 Soporte

Si encuentras problemas:

1. **Revisa los logs** del backend (terminal)
2. **Verifica conectividad**: `telnet localhost 8000`
3. **Prueba cada servicio** por separado:
   - Redis: `redis-cli ping`
   - ChromaDB: Accede a su dashboard
   - LLM: Revisa API key de OpenAI
4. **Contacta al equipo** con:
   - URL del request
   - Request body
   - Response completa
   - Logs del backend

---

**Última actualización:** 27 de Enero de 2026  
**Versión:** 2.0.0  
**Estado:** ✅ Production Ready

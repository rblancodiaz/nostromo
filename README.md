# 🏨 Neobookings MCP Server

Un servidor **Model Context Protocol (MCP)** completo para la API de reservas hoteleras de Neobookings, que permite gestionar reservas de hotel a través de interacciones en lenguaje natural con asistentes como Claude, ChatGPT y otros.

## ✨ Características Principales

- 🔗 **Integración completa con la API de Neobookings** (51 endpoints implementados)
- 🗣️ **Procesamiento de lenguaje natural** para reservas hoteleras
- 🔒 **Gestión segura de credenciales** con variables de entorno
- 🛡️ **Manejo integral de errores** y logging estructurado
- 🧪 **Cobertura completa de tests** automatizados
- 📊 **Suite de diagnósticos** y benchmarking
- 🎯 **Arquitectura modular** siguiendo principios SOLID

## 📊 Estado del Proyecto

### ✅ Endpoints Implementados: 51/51 (100%)

| Categoría | Endpoints | Estado |
|-----------|-----------|--------|
| 🔐 **Autenticación** | 1/1 | ✅ Completo |
| 🛒 **Gestión de Cestas** | 9/9 | ✅ Completo |
| 💰 **Gestión de Presupuestos** | 4/4 | ✅ Completo |
| 🏨 **Hoteles e Inventario** | 15/15 | ✅ Completo |
| 📦 **Productos Genéricos** | 3/3 | ✅ Completo |
| 📋 **Gestión de Órdenes** | 13/13 | ✅ Completo |
| 🎁 **Paquetes Turísticos** | 4/4 | ✅ Completo |
| 👥 **Usuarios y Recompensas** | 1/1 | ✅ Completo |
| 🌍 **Búsqueda Geográfica** | 1/1 | ✅ Completo |

## 🚀 Instalación Paso a Paso

### Prerrequisitos

- **Python 3.8+** instalado
- **pip** para gestión de paquetes
- **Claude Desktop** (opcional, para integración con Claude)

### 1. Clonar o Descargar el Proyecto

```bash
# Si tienes git instalado
git clone <repository-url>
cd mcp-neobookings

# O simplemente navega al directorio donde tienes el proyecto
cd mcp-neobookings
```

### 2. Crear Entorno Virtual (Recomendado)

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows:
venv\Scripts\activate
# En macOS/Linux:
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
# Instalar todas las dependencias del proyecto
pip install -r requirements.txt
```

### 4. Test de Conectividad Inicial

```bash
# Test rápido para verificar que todo funciona
python quick_test.py
```

**Salida esperada:**
```
🔬 Quick MCP Connectivity Test
------------------------------
[10:30:15] [PASS] ✅ Configuration OK
[10:30:16] [PASS] ✅ Connectivity OK (1250ms)
[10:30:16] [PASS] ✅ Tools Loading OK (51/51 tools)
[10:30:18] [PASS] ✅ Basic Function OK (1800ms)

============================================================
📊 QUICK TEST SUMMARY
============================================================
Status: 🟢 ALL TESTS PASSED
Tests:  4/4 passed (100%)
```

## 🧪 Guía Completa de Testing

### Tests Disponibles

| Script | Propósito | Tiempo | Uso Recomendado |
|--------|-----------|--------|-----------------|
| `quick_test.py` | Verificación rápida | ~5s | Checks diarios |
| `test_mcp_health.py` | Diagnóstico completo | ~30s | Troubleshooting |
| `test_endpoints.py` | Testing interactivo | Variable | Desarrollo |
| `benchmark_mcp.py` | Análisis de rendimiento | ~60s | Optimización |

### 1. Test Rápido de Conectividad

```bash
# Verificación básica (más rápida)
python quick_test.py
```

**¿Cuándo usar?**
- Verificación diaria del sistema
- Antes de hacer deploy
- Check rápido después de cambios

### 2. Diagnóstico Completo de Salud

```bash
# Test completo con salida detallada
python test_mcp_health.py --verbose

# Test de categoría específica
python test_mcp_health.py --category authentication
python test_mcp_health.py --category connectivity
python test_mcp_health.py --category tools_registry

# Modo rápido (solo tests críticos)
python test_mcp_health.py --quick

# Guardar resultados en archivo JSON
python test_mcp_health.py --output health_report.json
```

**Categorías disponibles:**
- `configuration` - Variables de entorno y configuración
- `connectivity` - Conectividad de red y API
- `authentication` - Autenticación y tokens
- `tools_registry` - Carga de herramientas MCP
- `basic_endpoints` - Funcionalidad básica
- `advanced_endpoints` - Operaciones avanzadas
- `performance` - Tiempos de respuesta
- `error_handling` - Manejo de errores

### 3. Testing Interactivo de Endpoints

```bash
# Modo interactivo
python test_endpoints.py

# Test de herramienta específica
python test_endpoints.py --tool hotel_search_rq

# Test con argumentos personalizados
python test_endpoints.py --tool hotel_search_rq --args '{"page": 1, "num_results": 5}'

# Listar todas las herramientas disponibles
python test_endpoints.py --list-tools
```

**Comandos del modo interactivo:**
```
> list                    # Mostrar todas las herramientas
> info hotel_search_rq    # Información de la herramienta
> test hotel_search_rq    # Probar con datos de ejemplo
> custom hotel_search_rq  # Probar con argumentos personalizados
> quit                    # Salir
```

### 4. Benchmarking de Rendimiento

```bash
# Benchmark completo
python benchmark_mcp.py

# Benchmark rápido
python benchmark_mcp.py --quick

# Test con requests concurrentes
python benchmark_mcp.py --concurrent 5

# Guardar resultados detallados
python benchmark_mcp.py --output benchmark_results.json
```

**Métricas medidas:**
- Tiempo de respuesta (min/max/avg/median/p95)
- Tasa de éxito
- Throughput (requests/segundo)
- Uso de memoria
- Grades de rendimiento (A-F)

## 🖥️ Configuración de Claude Desktop

### 1. Localizar el Archivo de Configuración

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### 2. Configurar el MCP Server

Añadir o crear el archivo `claude_desktop_config.json` con el siguiente contenido:

```json
{
  "mcpServers": {
    "neobookings": {
      "command": "python",
      "args": ["C:\\ruta\\completa\\al\\proyecto\\mcp-neobookings\\main.py"],
      "env": {
        "NEO_CLIENT_CODE": "neo",
        "NEO_SYSTEM_CODE": "XML",
        "NEO_USERNAME": "neomcp",
        "NEO_PASSWORD": "ECtIOnSPhepO",
        "NEO_API_BASE_URL": "https://ws-test.neobookings.com/api/v2",
        "NEO_API_TIMEOUT": "30"
      }
    }
  }
}
```

**⚠️ Importante:** Reemplaza `C:\\ruta\\completa\\al\\proyecto\\mcp-neobookings\\main.py` con la ruta real de tu proyecto.

### 3. Verificar la Integración

1. **Reinicia Claude Desktop** completamente
2. **Abre una nueva conversación**
3. **Verifica que aparece el icono MCP** (🔗) en la interfaz
4. **Prueba con un comando simple:**

```
"Busca hoteles en Madrid"
```

## 🎯 Uso del Sistema

### Comandos de Ejemplo

#### 🔐 Autenticación
```
"Autentica con el sistema Neobookings"
"Obtén un token de autenticación"
```

#### 🔍 Búsqueda de Hoteles
```
"Busca hoteles en Barcelona"
"Encuentra hoteles de 4 estrellas en Madrid"
"Busca alojamiento cerca de la playa en Valencia"
```

#### 📅 Disponibilidad
```
"Verifica disponibilidad para el 15 de julio en hoteles de Madrid"
"Consulta el calendario de disponibilidad para agosto"
```

#### 🛒 Gestión de Reservas
```
"Crea una nueva cesta de reserva"
"Añade este hotel a la cesta"
"Confirma la reserva de la cesta"
```

#### 💰 Presupuestos
```
"Busca presupuestos para hoteles en Sevilla"
"Obtén detalles del presupuesto con ID 12345"
```

#### 📦 Paquetes y Productos
```
"Busca paquetes turísticos disponibles"
"Consulta productos adicionales para la reserva"
```

### Herramientas Disponibles por Categoría

#### 🔐 Autenticación (1 herramienta)
- `authenticator_rq` - Autenticación en el sistema

#### 🛒 Gestión de Cestas (9 herramientas)
- `basket_create_rq` - Crear nueva cesta
- `basket_add_product_rq` - Añadir productos
- `basket_del_product_rq` - Eliminar productos
- `basket_summary_rq` - Resumen de cesta
- `basket_lock_rq` - Bloquear cesta
- `basket_unlock_rq` - Desbloquear cesta
- `basket_confirm_rq` - Confirmar cesta
- `basket_delete_rq` - Eliminar cesta
- `basket_properties_update_rq` - Actualizar propiedades

#### 💰 Gestión de Presupuestos (4 herramientas)
- `budget_search_rq` - Buscar presupuestos
- `budget_details_rq` - Detalles de presupuesto
- `budget_properties_update_rq` - Actualizar propiedades
- `budget_delete_rq` - Eliminar presupuesto

#### 🏨 Hoteles e Inventario (15 herramientas)
- `hotel_search_rq` - Buscar hoteles
- `hotel_details_rq` - Detalles de hotel
- `hotel_room_avail_rq` - Disponibilidad de habitaciones
- `hotel_room_details_rq` - Detalles de habitaciones
- `hotel_calendar_avail_rq` - Calendario de disponibilidad
- `hotel_inventory_read_rq` - Leer inventario
- `hotel_inventory_update_rq` - Actualizar inventario
- `hotel_price_update_rq` - Actualizar precios
- `hotel_board_details_rq` - Detalles de pensión
- `hotel_rate_details_rq` - Detalles de tarifas
- `hotel_offer_details_rq` - Detalles de ofertas
- `hotel_room_extra_avail_rq` - Disponibilidad de extras
- `hotel_room_extra_details_rq` - Detalles de extras
- `hotel_info_list_details_rq` - Lista de información
- `chain_info_list_details_rq` - Información de cadenas

#### 📦 Productos Genéricos (3 herramientas)
- `generic_product_avail_rq` - Disponibilidad de productos
- `generic_product_details_rq` - Detalles de productos
- `generic_product_extra_avail_rq` - Disponibilidad de extras

#### 📋 Gestión de Órdenes (13 herramientas)
- `order_search_rq` - Buscar órdenes
- `order_details_rq` - Detalles de orden
- `order_cancel_rq` - Cancelar orden
- `order_data_modify_rq` - Modificar datos
- `order_credit_card_rq` - Información de tarjeta
- `order_payment_create_rq` - Crear pago
- `order_put_rq` - Crear/actualizar orden
- `order_event_notify_rq` - Notificar evento
- `order_event_read_rq` - Leer eventos
- `order_event_search_rq` - Buscar eventos
- `order_notification_rq` - Crear notificación
- `order_notification_read_rq` - Leer notificaciones
- `order_notification_remove_rq` - Eliminar notificaciones

#### 🎁 Paquetes Turísticos (4 herramientas)
- `package_avail_rq` - Disponibilidad de paquetes
- `package_details_rq` - Detalles de paquetes
- `package_calendar_avail_rq` - Calendario de paquetes
- `package_extra_avail_rq` - Disponibilidad de extras

#### 👥 Usuarios y Recompensas (1 herramienta)
- `user_rewards_details_rq` - Detalles de recompensas

#### 🌍 Búsqueda Geográfica (1 herramienta)
- `zone_search_rq` - Buscar zonas geográficas

## 🏗️ Arquitectura del Proyecto

### Estructura de Carpetas

```
mcp-neobookings/
├── 📁 tools/                      # Herramientas MCP organizadas por categoría
│   ├── 📁 ctauthentication/              # Autenticación (1 endpoint)
│   ├── 📁 ctbasket/               # Gestión de cestas (9 endpoints)
│   ├── 📁 ctbudget/               # Gestión de presupuestos (4 endpoints)
│   ├── 📁 cthotelinventory/             # Hoteles e inventario (15 endpoints)
│   ├── 📁 ctgenericproduct/              # Productos genéricos (3 endpoints)
│   ├── 📁 ctorders/               # Gestión de órdenes (13 endpoints)
│   ├── 📁 ctpackages/              # Paquetes turísticos (4 endpoints)
│   ├── 📁 ctusers/                # Usuarios y recompensas (1 endpoint)
│   └── 📁 ctgeosearch/              # Búsqueda geográfica (1 endpoint)
├── 📁 handlers/                   # Lógica de procesamiento
├── 📁 tests/                      # Suite de tests
├── 📁 config/                     # Archivos de configuración
├── 📄 main.py                     # Punto de entrada del servidor MCP
├── 📄 quick_test.py               # Test rápido de conectividad
├── 📄 test_mcp_health.py          # Suite completa de diagnósticos
├── 📄 test_endpoints.py           # Tester interactivo de endpoints
├── 📄 benchmark_mcp.py            # Suite de benchmarks
├── 📄 requirements.txt            # Dependencias del proyecto
├── 📄 .env                        # Variables de entorno
├── 📄 claude_desktop_config.json  # Configuración para Claude Desktop
├── 📄 mcp_config.yaml            # Configuración MCP
└── 📄 README.md                   # Este archivo
```

### Principios de Diseño

- **🎯 Single Responsibility**: Cada herramienta maneja un endpoint específico
- **🔄 Dependency Injection**: Todas las dependencias se inyectan para testing
- **🛡️ Error Handling**: Manejo integral de errores con logging estructurado
- **🔒 Security**: Gestión segura de credenciales mediante variables de entorno
- **🧪 Testing**: Cobertura completa de tests unitarios e integración

## 🔧 Troubleshooting

### Problemas Comunes y Soluciones

#### 🚫 Error: "Module not found"
```bash
# Asegúrate de que el entorno virtual está activado
source venv/bin/activate  # macOS/Linux
# o
venv\Scripts\activate     # Windows

# Reinstala las dependencias
pip install -r requirements.txt
```

#### 🌐 Error de Conectividad
```bash
# Verifica la conectividad
python test_mcp_health.py --category connectivity

# Comprueba las variables de entorno
python test_mcp_health.py --category configuration
```

#### 🔐 Error de Autenticación
```bash
# Verifica las credenciales
python test_mcp_health.py --category authentication

# Comprueba el archivo .env
cat .env
```

#### 🔗 Claude Desktop no detecta el MCP
1. **Verifica la ruta** en `claude_desktop_config.json`
2. **Reinicia Claude Desktop** completamente
3. **Comprueba los logs** del sistema
4. **Ejecuta el test rápido** para verificar funcionamiento:
   ```bash
   python quick_test.py
   ```

#### ⚡ Rendimiento Lento
```bash
# Analiza el rendimiento
python benchmark_mcp.py --verbose

# Ejecuta diagnóstico de rendimiento
python test_mcp_health.py --category performance
```

### Códigos de Estado de Tests

| Código | Significado | Acción |
|--------|-------------|--------|
| `0` | ✅ Todos los tests pasaron | Continuar normalmente |
| `1` | ⚠️ Tests fallaron (no críticos) | Revisar warnings |
| `2` | 🚨 Fallos críticos | Revisar configuración |
| `3` | 💥 Error en ejecución | Contactar soporte |

### Grades de Rendimiento

| Grade | Tiempo | Estado | Recomendación |
|-------|--------|--------|---------------|
| **A** 🟢 | < 1000ms | Excelente | Mantener |
| **B** 🔵 | 1000-2000ms | Bueno | Aceptable |
| **C** 🟡 | 2000-5000ms | Regular | Monitorear |
| **D** 🟠 | > 5000ms | Lento | Optimizar |
| **F** ❌ | Fallos | Error | Revisar |

## 📞 Soporte y Contacto

### Documentación Adicional

- **📚 Guía Detallada de Tests**: [TESTING_GUIDE.md](TESTING_GUIDE.md)
- **🔧 Documentación de la API**: Consultar especificación OpenAPI incluida
- **🐛 Reportar Problemas**: Crear issue en el repositorio del proyecto

### Scripts de Monitoreo

#### Monitoreo Diario Automatizado

Crear script `daily_check.sh` (Linux/macOS) o `daily_check.bat` (Windows):

```bash
#!/bin/bash
echo "🔍 Daily MCP Health Check - $(date)"

# Test rápido
python quick_test.py
if [ $? -eq 0 ]; then
    echo "✅ Quick test passed"
    python benchmark_mcp.py --quick
else
    echo "❌ Issues detected, running full diagnostics"
    python test_mcp_health.py --verbose
fi
```

#### Alertas por Email (Ejemplo)

```bash
# Añadir al crontab para ejecución diaria
0 9 * * * cd /path/to/mcp-neobookings && ./daily_check.sh | mail -s "MCP Health Report" admin@example.com
```

## 🎉 ¡Listo para Usar!

Si has seguido todos los pasos correctamente, deberías tener:

1. ✅ **MCP Server funcionando** - Verificado con `quick_test.py`
2. ✅ **Claude Desktop integrado** - Con el icono MCP visible
3. ✅ **51 endpoints disponibles** - Todos los servicios de Neobookings
4. ✅ **Suite de tests completa** - Para diagnóstico y monitoreo

**🚀 Próximos pasos:**
- Experimenta con búsquedas de hoteles en lenguaje natural
- Prueba el flujo completo de reservas
- Utiliza los scripts de diagnóstico regularmente
- Explora todas las funcionalidades disponibles

**💡 Recuerda:**
- Los tests son tu mejor herramienta para diagnóstico
- Mantén el sistema actualizado ejecutando checks regulares
- La documentación completa está en [TESTING_GUIDE.md](TESTING_GUIDE.md)

---

**🏨 ¡Disfruta gestionando reservas hoteleras con lenguaje natural!**

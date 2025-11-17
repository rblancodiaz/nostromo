# MCP Testing Suite Documentation

Esta suite de testing proporciona herramientas completas para verificar, diagnosticar y analizar el rendimiento del servidor MCP Neobookings.

## 📋 Archivos de Testing Disponibles

### 1. `test_mcp_health.py` - Suite Completa de Diagnósticos
**Propósito**: Verificación exhaustiva de salud y funcionalidad del MCP

**Características**:
- ✅ Validación de configuración y variables de entorno
- 🌐 Tests de conectividad API y verificación SSL
- 🔐 Pruebas de autenticación y validación de tokens
- 🛠️ Verificación de registro y carga de herramientas MCP
- 🏨 Tests de endpoints básicos (búsquedas de hoteles, zonas, presupuestos)
- ⚡ Tests de rendimiento y tiempos de respuesta
- 🚨 Validación de manejo de errores
- 📊 Reportes detallados con recomendaciones

**Uso**:
```bash
# Test completo con salida detallada
python test_mcp_health.py --verbose

# Test de categoría específica
python test_mcp_health.py --category authentication

# Modo rápido (solo tests críticos)
python test_mcp_health.py --quick

# Guardar resultados en JSON
python test_mcp_health.py --output results.json
```

**Categorías de Test**:
- `configuration` - Configuración y entorno
- `connectivity` - Conectividad de red y API
- `authentication` - Autenticación y autorización
- `tools_registry` - Registro de herramientas MCP
- `basic_endpoints` - Funcionalidad básica de endpoints
- `advanced_endpoints` - Operaciones avanzadas
- `performance` - Rendimiento y tiempos de respuesta
- `error_handling` - Manejo de errores

### 2. `quick_test.py` - Test Rápido de Conectividad
**Propósito**: Verificación rápida de componentes esenciales

**Características**:
- 🔧 Validación básica de configuración
- 🌐 Test de conectividad API
- 📦 Verificación de carga de herramientas
- ⚡ Test de funcionalidad básica
- 📊 Resumen conciso con estado general

**Uso**:
```bash
# Ejecución simple
python quick_test.py
```

**Salida Ejemplo**:
```
🔬 Quick MCP Connectivity Test
------------------------------
[10:30:15] [PASS] ✅ Configuration OK (URL: https://ws-test.neobookings.com/api/v2)
[10:30:16] [PASS] ✅ Connectivity OK (1250ms)
[10:30:16] [PASS] ✅ Tools Loading OK (51/51 tools)
[10:30:18] [PASS] ✅ Basic Function OK (1800ms)

============================================================
📊 QUICK TEST SUMMARY
============================================================
Status: 🟢 ALL TESTS PASSED
Tests:  4/4 passed (100%)
Time:   3.2s

Component Status:
  • Configuration: ✅ OK
  • Connectivity:  ✅ OK
  • Tools Loading: ✅ OK
  • Basic Function:✅ OK

🎉 MCP Server is ready for use!
============================================================
```

### 3. `test_endpoints.py` - Tester Interactivo de Endpoints
**Propósito**: Testing individual e interactivo de endpoints específicos

**Características**:
- 🎮 Modo interactivo con comandos
- 🔧 Testing de endpoints individuales
- 📝 Información detallada de herramientas
- 🎯 Argumentos personalizados
- 📋 Lista completa de herramientas disponibles

**Uso**:
```bash
# Modo interactivo
python test_endpoints.py

# Test de herramienta específica
python test_endpoints.py --tool hotel_search_rq

# Test con argumentos personalizados
python test_endpoints.py --tool hotel_search_rq --args '{"page": 1, "num_results": 5}'

# Listar todas las herramientas
python test_endpoints.py --list-tools
```

**Comandos Interactivos**:
- `list` - Mostrar todas las herramientas disponibles
- `info <tool_name>` - Información detallada de la herramienta
- `test <tool_name>` - Probar herramienta con datos de ejemplo
- `custom <tool_name>` - Probar con argumentos personalizados
- `quit` - Salir

### 4. `benchmark_mcp.py` - Suite de Benchmarks de Rendimiento
**Propósito**: Análisis de rendimiento y benchmarking del servidor

**Características**:
- ⚡ Tests de velocidad de respuesta
- 🔄 Tests concurrentes
- 📊 Estadísticas detalladas (min/max/avg/median/p95)
- 🎯 Cálculo de throughput (requests/sec)
- 💾 Monitoreo de uso de memoria
- 🏆 Grades de rendimiento
- 💡 Recomendaciones de optimización

**Uso**:
```bash
# Benchmark completo
python benchmark_mcp.py

# Benchmark rápido
python benchmark_mcp.py --quick

# Test con 5 requests concurrentes
python benchmark_mcp.py --concurrent 5

# Guardar resultados
python benchmark_mcp.py --output benchmark_results.json
```

**Métricas Medidas**:
- Tiempo de respuesta (min/max/avg/median/p95)
- Tasa de éxito
- Throughput (requests por segundo)
- Uso de memoria
- Grades de rendimiento (A-F)

## 🚀 Guía de Uso Recomendada

### Para Verificación Inicial
```bash
# 1. Test rápido para verificar estado general
python quick_test.py

# 2. Si hay problemas, ejecutar diagnóstico completo
python test_mcp_health.py --verbose
```

### Para Desarrollo y Debugging
```bash
# 1. Test de endpoint específico durante desarrollo
python test_endpoints.py --tool <endpoint_name>

# 2. Test interactivo para explorar herramientas
python test_endpoints.py

# 3. Verificación de categoría específica
python test_mcp_health.py --category tools_registry
```

### Para Análisis de Rendimiento
```bash
# 1. Benchmark básico
python benchmark_mcp.py --quick

# 2. Benchmark completo con concurrencia
python benchmark_mcp.py --concurrent 3

# 3. Análisis detallado con guardado de resultados
python benchmark_mcp.py --output performance_report.json
```

### Para CI/CD y Automatización
```bash
# Test de salud completo con salida estructurada
python test_mcp_health.py --output health_check.json

# Test rápido para validación de deploy
python quick_test.py

# Benchmark de regresión
python benchmark_mcp.py --quick --output regression_test.json
```

## 📊 Interpretación de Resultados

### Códigos de Salida
- `0` - Todos los tests pasaron
- `1` - Tests fallaron (no críticos)
- `2` - Fallos críticos detectados
- `3` - Error en ejecución del test
- `130` - Interrumpido por usuario

### Grades de Rendimiento
- **A** (🟢): < 1000ms - Excelente
- **B** (🔵): 1000-2000ms - Bueno
- **C** (🟡): 2000-5000ms - Aceptable
- **D** (🟠): > 5000ms - Necesita optimización
- **F** (❌): Fallos en ejecución

### Status de Salud
- **🟢 ALL TESTS PASSED** - Sistema completamente funcional
- **🟡 PARTIAL SUCCESS** - Algunos problemas no críticos
- **🔴 CRITICAL FAILURES** - Requiere atención inmediata

## 🔧 Resolución de Problemas Comunes

### Error de Configuración
```bash
# Verificar variables de entorno
python test_mcp_health.py --category configuration
```

### Problemas de Conectividad
```bash
# Verificar conectividad de red
python test_mcp_health.py --category connectivity
```

### Errores de Autenticación
```bash
# Verificar credenciales
python test_mcp_health.py --category authentication
```

### Problemas de Carga de Herramientas
```bash
# Verificar registro de tools
python test_mcp_health.py --category tools_registry
```

### Rendimiento Lento
```bash
# Análisis de rendimiento
python benchmark_mcp.py --verbose
```

## 📈 Monitoring Continuo

### Script de Monitoreo Diario
```bash
#!/bin/bash
# daily_health_check.sh

echo "🔍 Daily MCP Health Check - $(date)"

# Quick health check
python quick_test.py
QUICK_EXIT=$?

if [ $QUICK_EXIT -eq 0 ]; then
    echo "✅ Quick test passed"
    
    # Run performance benchmark
    python benchmark_mcp.py --quick --output "logs/benchmark_$(date +%Y%m%d).json"
    
    echo "📊 Daily check completed successfully"
else
    echo "❌ Issues detected, running full diagnostics"
    
    # Full health check with detailed output
    python test_mcp_health.py --verbose --output "logs/health_$(date +%Y%m%d).json"
    
    echo "🚨 Full diagnostic completed - check logs for details"
fi
```

### Alertas Automatizadas
Los scripts pueden integrarse con sistemas de alertas mediante códigos de salida y archivos JSON de salida.

## 💡 Mejores Prácticas

1. **Ejecutar `quick_test.py` antes de cualquier deploy**
2. **Usar `test_mcp_health.py --verbose` para debugging detallado**
3. **Ejecutar benchmarks periódicamente para detectar regresiones**
4. **Usar modo interactivo para desarrollo y testing de nuevos endpoints**
5. **Guardar resultados en JSON para análisis histórico**
6. **Configurar alertas basadas en códigos de salida**

## 📞 Soporte

Si los tests revelan problemas persistentes:
1. Revisar logs detallados generados por los scripts
2. Verificar configuración de red y credenciales
3. Consultar la documentación del API de Neobookings
4. Contactar al equipo de soporte técnico

# Plan de Implementación: Corrección Cartográfica y Trazado de Rutas en Plotly JS
**Documento de Referencia Obligatorio:** Leer previamente [`Architecture.md`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Architecture.md)  
**Archivo de Plan:** `PLAN-correccion-mapa-plotly-itinerarios-2026-11-04.md`  
**Fecha:** 04 de Noviembre de 2026  
**Estado:** PENDIENTE DE EJECUCIÓN (Solo Diseño y Especificación Técnica)

---

## 1. Rol Asignado al Agente
* **Rol:** **Data Visualization & Geospatial Systems Engineer**
* **Misión:** Solucionar el problema de renderizado del mapa de Plotly JS (el cual actualmente aparece en blanco o solo con el contorno continental), asegurar la representación visual nítida de todos los aeropuertos colombianos y trazar dinámicamente las rutas aéreas (arcos/líneas de vuelo) de los itinerarios creados, sincronizándose reactivamente con las altas y bajas de itinerarios.

---

## 2. Diagnóstico y Problemas a Resolver
1. **Mapa en Blanco / Desconfigurado:** Como se aprecia en la captura del usuario, el contenedor del mapa muestra únicamente un contorno pálido de Colombia sin marcadores visibles de aeropuertos, debido a un encuadre de proyección y escala erróneos (`mercator` escala 4.5 centrado fuera de los límites de datos) o a la falta de carga de estilos geoespaciales.
2. **Falta de Trazado de Rutas:** El mapa solo intenta renderizar puntos aislados. Un portal de itinerarios profesional debe graficar las rutas activas que conectan origen y destino de cada viaje registrado.
3. **Falta de Reactividad:** Cuando un itinerario es registrado o eliminado, el mapa permanece estático y requiere recargar la página completa.

---

## 3. Especificación Detallada de Cambios

### 3.1 Corrección del Renderizado Base de Plotly JS
* **Configuración Geoespacial Optimizada:**
  * Proyección centrada de Colombia: `center: { lat: 4.5708, lon: -74.2973 }`.
  * Escala y límites (`lataxis`, `lonaxis`) ajustados a los límites geográficos reales de Colombia (`lat: [-4.2, 13.5]`, `lon: [-79.0, -66.8]`).
  * Paleta visual moderna:
    * Tierra (`landcolor`): `#f8fafc`.
    * Océano (`oceancolor`): `#e0f2fe`.
    * Fronteras (`countrycolor`, `subunitcolor`): `#cbd5e1`.
    * Fondo transparente integrado con el tema del portal.
* **Marcadores de Aeropuertos:**
  * Puntos estilizados con círculos luminosos (`#0284c7`, borde blanco).
  * Distinción visual para aeropuertos internacionales (color azul oscuro `#1e40af` o mayor tamaño) vs nacionales.
  * Etiquetas de texto con código IATA visible (`BOG`, `MDE`, `CLO`, etc.).
  * Tooltips (Hoverinfo) ricos en HTML mostrando:
    * Nombre oficial del aeropuerto.
    * Ciudad y departamento.
    * Total de itinerarios activos que tocan este aeropuerto.

### 3.2 Trazado Dinámico de Líneas de Vuelo (Itinerary Flight Paths)
* Implementar una capa secundaria en Plotly (trazas de tipo `scattergeo` con `mode: 'lines'`).
* Para cada itinerario registrado en la base de datos:
  * Obtener coordenadas de `origin_airport` y `destination_airport`.
  * Dibujar una línea de conexión estilizada (color azul cian `#0ea5e9`, grosor 2.5px, estilo punteado o con curva ligera).
  * Al pasar el cursor sobre la línea de vuelo, desplegar tooltip con:
    * Pasajero.
    * Ruta: `[IATA_ORIGEN] → [IATA_DESTINO]`.
    * Fecha y duración en minutos.

### 3.3 Sincronización Reactiva
* Exponer una función central `refreshMapData()` en `app.js`.
* Al crear un nuevo itinerario (`POST 201`) $\rightarrow$ Agregar la traza de vuelo al mapa sin parpadeo.
* Al eliminar un itinerario (`DELETE 204`) $\rightarrow$ Retirar la traza de vuelo del mapa de forma inmediata.
* Al seleccionar un aeropuerto en el formulario de reserva $\rightarrow$ Centrar e iluminar temporalmente el marcador en el mapa.

---

## 4. Archivos Afectados
* [`Taller-Git-Prueba/frontend/app.js`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/app.js)
* [`Taller-Git-Prueba/frontend/index.html`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/index.html)
* [`airport-service/src/infrastructure/adapters/plotly_adapter.py`](file:///c:/Dev/Universidad/Arquitectura%20Soft/airport-service/src/infrastructure/adapters/plotly_adapter.py) (Ajuste del layout y datos si es necesario para sincronía).

---

## 5. Criterios de Aceptación y Validación
1. El mapa de Colombia carga con todos sus aeropuertos visibles como nodos identificados con su código IATA.
2. Cada itinerario existente dibuja una línea clara de origen a destino entre los aeropuertos involucrados.
3. El mapa es completamente responsivo y permite zoom/paneo suave.
4. Crear o eliminar un itinerario actualiza las líneas de vuelo en el mapa en menos de 500ms.

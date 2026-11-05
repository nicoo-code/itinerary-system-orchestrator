# Plan de Implementación: Buscador y Filtro Interactivo de Aeropuertos
**Documento de Referencia Obligatorio:** Leer previamente [`Architecture.md`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Architecture.md)  
**Archivo de Plan:** `PLAN-filtro-aeropuertos-autocompletado-2026-11-04.md`  
**Fecha:** 04 de Noviembre de 2026  
**Estado:** PENDIENTE DE EJECUCIÓN (Solo Diseño y Especificación Técnica)

---

## 1. Rol Asignado al Agente
* **Rol:** **Frontend Interaction Engineer & UX Component Specialist**
* **Misión:** Reemplazar los controles `<select>` nativos primitivos actuales por un componente de autocompletado y búsqueda predictiva dinámico (Combobox inteligente), permitiendo a los usuarios buscar y filtrar rápidamente entre más de 50 aeropuertos por ciudad, nombre o código IATA.

---

## 2. Diagnóstico y Problemas a Resolver
1. **Selector Nativo Inmanejable:** Como se aprecia en la captura del usuario, el elemento `<select>` despliega una lista masiva de más de 50 opciones no ordenadas ni categorizadas, requiriendo hacer scroll manual excesivo.
2. **Sin Búsqueda Predictiva:** Si el usuario quiere volar a *"Medellín"*, no puede escribir para autocompletar; debe buscar visualmente opción por opción.
3. **Falta de Validación Visual Inmediata:** Si el usuario selecciona el mismo aeropuerto en origen y destino, solo se entera cuando hace submit y el servidor o JS arroja un error general.

---

## 3. Especificación Detallada de Cambios

### 3.1 Componente "Airport Combobox / Searchable Dropdown"
Diseñar e implementar un componente modular de selección sin dependencias externas pesadas (Vanilla JS puro y accesible):
* **Campo de Entrada (Input con Icono de Búsqueda):**
  * Placeholder dinámico: *"Buscar por ciudad, IATA o nombre (Ej: Bogotá, BOG, El Dorado)..."*
  * Soporte de teclado: Flechas arriba/abajo (`ArrowUp`, `ArrowDown`), `Enter` para seleccionar, `Escape` para cerrar.
* **Panel Desplegable Flotante (Dropdown Menu):**
  * Muestra resultados ordenados por relevancia (coincidencia exacta de código IATA primero, luego ciudad, luego nombre).
  * Renderizado enriquecido por ítem:
    * Badge destacado con el código IATA: `[BOG]`, `[MDE]`, `[CLO]`.
    * Nombre completo de la ciudad y departamento en texto secundario.
    * Indicador de tipo: *Internacional / Nacional / Regional*.
* **Control de Duplicados en Tiempo Real:**
  * Si el aeropuerto seleccionado en Origen ya está elegido, se deshabilita o resalta como no disponible en el selector de Destino (y viceversa).
* **Botón de Intercambio Rápido (Swap Airports):**
  * Botón central con icono SVG de doble flecha para alternar origen y destino con un solo clic.

### 3.2 Filtro Global para el Catálogo de Aeropuertos
* En la pestaña de exploración de aeropuertos, incluir una barra de búsqueda global y filtros por chip:
  * Filtro por tipo: *Todos*, *Internacionales*, *Nacionales*.
  * Filtro por departamento / región.

---

## 4. Archivos Afectados
* [`Taller-Git-Prueba/frontend/index.html`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/index.html)
* [`Taller-Git-Prueba/frontend/app.js`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/app.js)
* [`Taller-Git-Prueba/frontend/style.css`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/style.css)

---

## 5. Criterios de Aceptación y Validación
1. El usuario puede escribir "MDE" o "Medellin" y encontrar el aeropuerto en menos de 100ms.
2. El componente oculta el `<select>` nativo pero mantiene el valor del ID para enviar la petición POST `origin_airport_id` y `destination_airport_id` compatible con el backend.
3. Se previene visualmente que origen y destino sean idénticos antes del envío.
4. Funciona tanto con clic/touch en pantallas móviles como con navegación de teclado.

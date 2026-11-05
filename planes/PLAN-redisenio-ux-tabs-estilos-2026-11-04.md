# Plan de Implementación: Rediseño Estructural UX/UI y Sistema Multi-Pestaña
**Documento de Referencia Obligatorio:** Leer previamente [`Architecture.md`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Architecture.md)  
**Archivo de Plan:** `PLAN-redisenio-ux-tabs-estilos-2026-11-04.md`  
**Fecha:** 04 de Noviembre de 2026  
**Estado:** PENDIENTE DE EJECUCIÓN (Solo Diseño y Especificación Técnica)

---

## 1. Rol Asignado al Agente
* **Rol:** **Senior Frontend Architect & UI/UX Designer**
* **Misión:** Transformar la interfaz actual (monolítica, tosca y con elementos tipo prototipo) en una plataforma web corporativa, moderna y seria, orientada a la experiencia de usuario real de un portal de itinerarios de viajes y aerolíneas comerciales.

---

## 2. Diagnóstico y Problemas a Resolver
1. **Presencia de Emojis Infantiles:** En el encabezado actual aparece `✈️ Itinerarios Personales`, lo que resta seriedad académica y profesional al proyecto, transmitiendo una estética de código autogenerado por IA básica.
2. **Estructura Plana en Una Sola Pantalla:** Todo el contenido (formulario, tabla y mapa) está forzado en un layout de dos columnas desequilibrado.
3. **Falta de Organización por Pestañas:** Un sistema real de itinerarios separa las vistas operativas de las analíticas y de consulta.
4. **Tipografía y Componentes Rudimentarios:** Botones y tablas con estilos por defecto poco estilizados.

---

## 3. Especificación Detallada de Cambios

### 3.1 Eliminación de Emojis y Sistema de Iconografía Vectorial (SVG)
* Eliminar **todos** los emojis (`✈️`, etc.) de títulos, textos, botones e indicadores.
* Implementar un conjunto de iconos SVG limpios, consistentes y profesionales (estilo Lucide / Heroicons inline):
  * Icono de navegación aérea (Compass / Plane minimalista vectorizado).
  * Iconos de pestañas: `CalendarPlus` (Planificar), `MapPin` (Aeropuertos), `Ticket` (Itinerarios), `Activity` (Métricas & Salud).
  * Iconos de acción: `RefreshCw`, `Trash2`, `Search`, `ArrowRight`, `Download`.

### 3.2 Arquitectura de Navegación Multi-Pestaña (Tab Navigation)
Crear un sistema de navegación con pestañas de alto impacto visual y persistencia de estado:
1. **Pestaña 1: "Planificador de Itinerarios"**
   * Formulario ergonómico en dos fases o tarjetas con visualización clara de origen $\rightarrow$ destino.
   * Resumen dinámico previo a la confirmación (vista previa de la tarjeta de embarque/itinerario).
2. **Pestaña 2: "Explorador de Aeropuertos y Mapa Táctico"**
   * Vista expandida del mapa nacional.
   * Barra de búsqueda y filtrado rápido.
   * Ficha técnica del aeropuerto seleccionado al hacer clic en el mapa.
3. **Pestaña 3: "Mis Itinerarios y Reservas"**
   * Listado organizado en tarjetas (Cards) y vista de tabla con estado de vuelo (`CREATED`, `CONFIRMED`).
   * Acciones rápidas: ver ruta en mapa, clonar datos o cancelar/eliminar itinerario con modal de confirmación.
4. **Pestaña 4: "Centro de Monitoreo & Auditoría"**
   * Indicadores de salud del sistema: API Gateway, Circuit Breaker (`CLOSED`), Redis Cache, RabbitMQ y PostgreSQL.
   * Log de notificaciones en tiempo real consumidas por el componente Serverless.

### 3.3 Paleta de Colores y Sistema de Diseño (Design System)
* **Primario:** Azul corporativo aeronáutico (`#0f172a`, `#1e293b`, `#0284c7`).
* **Secundario:** Acentos en azul cian (`#38bdf8`) y verde esmeralda para estados exitosos (`#10b981`).
* **Superficies:** Fondos en blanco y gris neutro claro (`#f8fafc`, `#f1f5f9`) con bordes sutiles (`#e2e8f0`) y sombras suaves (`box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1)`).
* **Tipografía:** Tipografías del sistema de alta legibilidad (`Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `Roboto`).

---

## 4. Archivos Afectados
* [`Taller-Git-Prueba/frontend/index.html`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/index.html)
* [`Taller-Git-Prueba/frontend/style.css`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/style.css)
* [`Taller-Git-Prueba/frontend/app.js`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/app.js)

---

## 5. Criterios de Aceptación y Validación
1. Cero presencia de emojis en todo el código HTML, JS y CSS.
2. Navegación fluida entre las 4 pestañas sin recargar la página.
3. El diseño es 100% responsivo (desktop, tablet y móvil).
4. El cambio no rompe la comunicación con los endpoints REST del API Gateway (`/api/v1/*`).

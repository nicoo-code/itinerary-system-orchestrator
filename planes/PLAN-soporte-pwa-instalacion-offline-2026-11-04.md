# Plan de Implementación: Transformación PWA y Soporte de Instalación Móvil / Escritorio
**Documento de Referencia Obligatorio:** Leer previamente [`Architecture.md`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Architecture.md)  
**Archivo de Plan:** `PLAN-soporte-pwa-instalacion-offline-2026-11-04.md`  
**Fecha:** 04 de Noviembre de 2026  
**Estado:** PENDIENTE DE EJECUCIÓN (Solo Diseño y Especificación Técnica)

---

## 1. Rol Asignado al Agente
* **Rol:** **Progressive Web App (PWA) & Mobile Performance Engineer**
* **Misión:** Convertir la plataforma web de itinerarios en una Progressive Web App (PWA) completa, permitiendo que cualquier usuario desde una computadora o teléfono móvil reciba el prompt interactivo de instalación para ejecutarla como una aplicación nativa de escritorio o app móvil independiente.

---

## 2. Diagnóstico y Problemas a Resolver
1. **Falta de Instalabilidad:** Actualmente es una página web tradicional. Si el usuario ingresa desde un teléfono o desde Chrome/Edge en el computador, no tiene forma de instalarla en su pantalla de inicio o dock.
2. **Sin Estrategia de Caché Estático:** Toda recarga depende 100% de la red para descargar HTML, CSS y JS, afectando el tiempo de carga en dispositivos móviles con baja cobertura.
3. **Falta de Configuración de Branding PWA:** Ausencia de `manifest.json`, iconos adaptativos y metadatos de viewport temático (`theme-color`).

---

## 3. Especificación Detallada de Cambios

### 3.1 Manifiesto de la Aplicación Web (`manifest.json`)
Crear el archivo de especificación PWA en el directorio del frontend:
* **Nombre de la App:** `"AeroRoute - Sistema de Itinerarios"`
* **Nombre Corto:** `"AeroRoute"`
* **Descripción:** `"Plataforma distribuida para la planificación y visualización geoespacial de itinerarios de viaje en Colombia."`
* **Colores de Marca:**
  * `theme_color`: `#0f172a` (Barra de estado superior).
  * `background_color`: `#f8fafc` (Splash screen de inicio).
* **Display Mode:** `"standalone"` (Oculta la barra de navegación del navegador, luciendo como app nativa).
* **Iconografía PWA:**
  * Icono vectorial SVG de alta resolución con diseño de compás / vuelo aeroportuario.
  * Iconos generados en resoluciones estándar: `192x192` y `512x512` con soporte `maskable`.

### 3.2 Service Worker (`sw.js`) y Estrategia de Almacenamiento
* Implementar `sw.js` con ciclo de vida completo (`install`, `activate`, `fetch`):
  * **Caché en Instalación:** Precaching de activos estáticos críticos (`index.html`, `style.css`, `app.js`, Plotly JS y fuentes).
  * **Estrategia de Red:** *Stale-While-Revalidate* para recursos estáticos y *Network-First* con fallback informativo para peticiones API (`/api/v1/*`).
  * **Limpieza Automática:** Eliminación de versiones obsoletas de caché en el evento `activate`.

### 3.3 Banner / Notificación de Instalación Interactiva
* Capturar el evento estándar del navegador `beforeinstallprompt`:
  * Prevenir el comportamiento por defecto y almacenar el evento.
  * Mostrar una notificación flotante sutil o botón elegante en el header:
    * *"Instalar App en este Dispositivo"* con icono de descarga SVG.
  * Al hacer clic, disparar el prompt nativo (`deferredPrompt.prompt()`) y registrar si el usuario aceptó o descartó la instalación.
* Notificación de estado instalada (`appinstalled`):
  * Ocultar el botón y mostrar mensaje de bienvenida.

### 3.4 Optimización Responsiva para Móviles
* Metatags en `index.html`: `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`.
* Ajuste de padding táctil (Touch Targets de mínimo 44x44px) para botones y selectores.

---

## 4. Archivos Afectados
* [`Taller-Git-Prueba/frontend/manifest.json`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/manifest.json) (Nuevo)
* [`Taller-Git-Prueba/frontend/sw.js`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/sw.js) (Nuevo)
* [`Taller-Git-Prueba/frontend/icons/`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/icons/) (Nuevo)
* [`Taller-Git-Prueba/frontend/index.html`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/index.html)
* [`Taller-Git-Prueba/frontend/app.js`](file:///c:/Dev/Universidad/Arquitectura%20Soft/Taller-Git-Prueba/frontend/app.js)

---

## 5. Criterios de Aceptación y Validación
1. Chrome / Edge / Safari muestran el icono nativo de *"Instalar aplicación"*.
2. El banner personalizado de instalación aparece en móvil y escritorio y permite instalar la app en el escritorio/pantalla de inicio con un solo clic.
3. La aplicación se ejecuta en una ventana independiente sin barras de URL.
4. El Service Worker queda registrado exitosamente en `Application > Service Workers` en las herramientas de desarrollo.

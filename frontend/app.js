/**
 * AeroItinerarios - Plataforma Distribuida de Itinerarios de Vuelo
 * Frontend Architecture & Controllers (Vanilla JS Moderno)
 * Cero Emojis - Iconografía Vectorial SVG
 */

document.addEventListener('DOMContentLoaded', () => {
  // ==========================================
  // ESTADO GLOBAL DE LA APLICACIÓN
  // ==========================================
  const state = {
    airports: [],
    airportsMap: {}, // id -> Airport Object
    itineraries: [],
    notificationsLog: [],
    activeTab: 'tab-planner',
    currentView: 'cards', // 'cards' | 'table'
    selectedAirport: null,
    itineraryToDelete: null,
    autoPollTimer: null,
    mapRendered: false,
    plotlyData: null,
    plotlyLayout: null
  };

  // ==========================================
  // ELEMENTOS DEL DOM
  // ==========================================
  const dom = {
    // Topbar y Ribbon
    gatewayIndicator: document.getElementById('gateway-indicator'),
    circuitIndicator: document.getElementById('circuit-indicator'),
    circuitIndicatorText: document.getElementById('circuit-indicator-text'),
    btnGlobalRefresh: document.getElementById('btn-global-refresh'),
    toastContainer: document.getElementById('toast-container'),

    // Navegación por Pestañas
    tabButtons: document.querySelectorAll('.tab-button'),
    tabPanels: document.querySelectorAll('.tab-panel'),
    badgeAirportsCount: document.getElementById('badge-airports-count'),
    badgeItinerariesCount: document.getElementById('badge-itineraries-count'),

    // Pestaña 1: Planificador
    form: document.getElementById('itinerary-form'),
    userNameInput: document.getElementById('user_name'),
    departureDateInput: document.getElementById('departure_date'),
    durationMinutesInput: document.getElementById('duration_minutes'),
    originHiddenInput: document.getElementById('origin_airport'),
    destHiddenInput: document.getElementById('destination_airport'),
    btnSwapRoute: document.getElementById('btn-swap-route'),
    routeWarning: document.getElementById('route-warning'),
    btnSubmit: document.getElementById('btn-submit'),
    btnSubmitText: document.getElementById('btn-submit-text'),
    presetChips: document.querySelectorAll('.preset-chip'),

    // Boarding Pass Preview
    bpOriginCode: document.getElementById('bp-origin-code'),
    bpOriginCity: document.getElementById('bp-origin-city'),
    bpDestCode: document.getElementById('bp-dest-code'),
    bpDestCity: document.getElementById('bp-dest-city'),
    bpPassengerName: document.getElementById('bp-passenger-name'),
    bpDepartureDate: document.getElementById('bp-departure-date'),
    bpDurationTag: document.getElementById('bp-duration-tag'),
    bpStatusBadge: document.getElementById('bp-status-badge'),

    // Pestaña 2: Mapa y Catálogo
    mapSearchInput: document.getElementById('airport-search-input'),
    btnClearAirportSearch: document.getElementById('btn-clear-airport-search'),
    filterChips: document.querySelectorAll('.chip[data-filter]'),
    mapCounterBadge: document.getElementById('map-counter-badge'),
    btnRecenterMap: document.getElementById('btn-recenter-map'),
    airportsCatalogTbody: document.getElementById('airports-catalog-tbody'),
    airportResultsCount: document.getElementById('airport-results-count'),

    // Ficha Técnica de Aeropuerto
    detailIataBadge: document.getElementById('detail-iata-badge'),
    detailName: document.getElementById('detail-name'),
    detailCityDept: document.getElementById('detail-city-dept'),
    detailId: document.getElementById('detail-id'),
    detailIata: document.getElementById('detail-iata'),
    detailType: document.getElementById('detail-type'),
    detailCoords: document.getElementById('detail-coords'),
    btnUseAsOrigin: document.getElementById('btn-use-as-origin'),
    btnUseAsDest: document.getElementById('btn-use-as-dest'),

    // Pestaña 3: Mis Itinerarios
    itinerarySearchInput: document.getElementById('itinerary-search-input'),
    btnViewCards: document.getElementById('btn-view-cards'),
    btnViewTable: document.getElementById('btn-view-table'),
    btnRefreshItineraries: document.getElementById('btn-refresh-itineraries'),
    btnExportItineraries: document.getElementById('btn-export-itineraries'),
    itinerariesCardsView: document.getElementById('itineraries-cards-view'),
    itinerariesTableView: document.getElementById('itineraries-table-view'),
    itinerariesList: document.getElementById('itineraries-list'),

    // Modal de Confirmación
    deleteModal: document.getElementById('delete-modal'),
    modalPassengerName: document.getElementById('modal-passenger-name'),
    modalRouteName: document.getElementById('modal-route-name'),
    btnCancelDelete: document.getElementById('btn-cancel-delete'),
    btnConfirmDelete: document.getElementById('btn-confirm-delete'),

    // Pestaña 4: Monitoreo & Auditoría
    chkAutoPoll: document.getElementById('chk-auto-poll-health'),
    btnRefreshMonitoring: document.getElementById('btn-refresh-monitoring'),
    btnExportAuditLog: document.getElementById('btn-export-audit-log'),
    gwHealthStatus: document.getElementById('gw-health-status'),
    gwLatency: document.getElementById('gw-latency'),
    cbHealthState: document.getElementById('cb-health-state'),
    cbMetricState: document.getElementById('cb-metric-state'),
    redisMetricStatus: document.getElementById('redis-metric-status'),
    cbMetricFailures: document.getElementById('cb-metric-failures'),
    itineraryHealthStatus: document.getElementById('itinerary-health-status'),
    dbMetricStatus: document.getElementById('db-metric-status'),
    outboxMetricStatus: document.getElementById('outbox-metric-status'),
    notifHealthStatus: document.getElementById('notif-health-status'),
    amqpMetricStatus: document.getElementById('amqp-metric-status'),
    notifsMetricTotal: document.getElementById('notifs-metric-total'),
    notificationsLogList: document.getElementById('notifications-log-list')
  };

  // ==========================================
  // SISTEMA DE NOTIFICACIONES TOAST (SIN EMOJIS)
  // ==========================================
  function showToast(title, message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Iconos vectoriales según el tipo
    let iconSvg = '';
    if (type === 'success') {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
        <polyline points="22 4 12 14.01 9 11.01"/>
      </svg>`;
    } else if (type === 'error') {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="15" y1="9" x2="9" y2="15"/>
        <line x1="9" y1="9" x2="15" y2="15"/>
      </svg>`;
    } else {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/>
        <line x1="12" y1="16" x2="12" y2="12"/>
        <line x1="12" y1="8" x2="12.01" y2="8"/>
      </svg>`;
    }

    toast.innerHTML = `
      ${iconSvg}
      <div class="toast-body">
        <div class="toast-title">${title}</div>
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-close" aria-label="Cerrar notificación">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    `;

    toast.querySelector('.toast-close').addEventListener('click', () => {
      toast.remove();
    });

    dom.toastContainer.appendChild(toast);

    setTimeout(() => {
      if (toast.parentNode) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(40px)';
        setTimeout(() => toast.remove(), 250);
      }
    }, 5000);
  }

  // ==========================================
  // ARQUITECTURA MULTI-PESTAÑA (TAB CONTROLLER)
  // ==========================================
  function switchTab(tabId) {
    if (!tabId) return;

    dom.tabButtons.forEach(btn => {
      const isTarget = btn.getAttribute('data-tab') === tabId;
      btn.classList.toggle('active', isTarget);
      btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
    });

    dom.tabPanels.forEach(panel => {
      const isTarget = panel.id === tabId;
      panel.classList.toggle('active', isTarget);
    });

    state.activeTab = tabId;
    localStorage.setItem('aero_active_tab', tabId);
    
    // Hash en la URL para navegación limpia
    const hash = tabId.replace('tab-', '');
    if (window.location.hash !== `#${hash}`) {
      history.replaceState(null, null, `#${hash}`);
    }

    // AJUSTE CRÍTICO: Redimensionar Plotly si la pestaña de mapa se vuelve activa
    if (tabId === 'tab-map') {
      setTimeout(() => {
        const mapEl = document.getElementById('map');
        if (mapEl && window.Plotly && state.mapRendered) {
          Plotly.Plots.resize('map');
        } else if (!state.mapRendered) {
          loadAirportsMap();
        }
      }, 50);
    }
  }

  dom.tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      switchTab(tabId);
    });
  });

  // Restaurar pestaña desde URL Hash o LocalStorage
  function restoreInitialTab() {
    const hash = window.location.hash.replace('#', '');
    const validTabs = ['planner', 'map', 'itineraries', 'monitoring'];
    if (hash && validTabs.includes(hash)) {
      switchTab(`tab-${hash}`);
      return;
    }

    const savedTab = localStorage.getItem('aero_active_tab');
    if (savedTab && document.getElementById(savedTab)) {
      switchTab(savedTab);
    }
  }

  // ==========================================
  // 1. CARGA DEL CATÁLOGO DE AEROPUERTOS
  // ==========================================
  async function loadAirportsCatalog() {
    try {
      const response = await fetch('/api/v1/airports');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      state.airports = data;
      state.airportsMap = {};
      data.forEach(a => {
        state.airportsMap[a.id] = a;
      });

      // Actualizar contadores
      if (dom.badgeAirportsCount) dom.badgeAirportsCount.textContent = data.length;
      if (dom.mapCounterBadge) dom.mapCounterBadge.textContent = `${data.length} Aeropuertos Registrados`;
      if (dom.airportResultsCount) dom.airportResultsCount.textContent = `${data.length} resultados`;

      populateAirportSelects(data);
      renderAirportsDirectoryTable(data);

      // Si no hay seleccionado, pre-seleccionar BOG (ID: 1)
      const defaultAirport = data.find(a => a.iata_code === 'BOG') || data[0];
      if (defaultAirport) {
        updateAirportDetailSheet(defaultAirport);
      }

    } catch (err) {
      console.warn('Error fetching airports catalogue:', err);
      showToast('Advertencia de Conectividad', 'No se pudo conectar con el catálogo en vivo. Verifique el API Gateway.', 'error');
    }
  }

  // ==========================================
  // COMPONENTE AIRPORT COMBOBOX (BUSCABLE)
  // ==========================================
  function normalizeText(value) {
    return String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function createAirportCombobox({
    wrapperId,
    hiddenInputId,
    textInputId,
    iataPillId,
    clearBtnId,
    toggleBtnId,
    listboxId,
    counterpartLabel,
    getCounterpartId,
    onChange
  }) {
    const wrapper = document.getElementById(wrapperId);
    const container = wrapper ? wrapper.querySelector('.combobox-container') : null;
    const hiddenInput = document.getElementById(hiddenInputId);
    const textInput = document.getElementById(textInputId);
    const iataPill = document.getElementById(iataPillId);
    const clearBtn = document.getElementById(clearBtnId);
    const toggleBtn = document.getElementById(toggleBtnId);
    const listbox = document.getElementById(listboxId);

    let isOpen = false;
    let isFiltering = false;
    let highlightedIndex = -1;
    let visibleOptions = [];
    let justFocused = false;

    function formatDisplay(airport) {
      if (!airport) return '';
      return `${airport.city} - ${airport.name}`;
    }

    function syncVisualSelection() {
      const selectedId = hiddenInput ? hiddenInput.value : '';
      const airport = selectedId ? state.airportsMap[selectedId] : null;

      if (airport) {
        if (textInput) textInput.value = formatDisplay(airport);
        if (iataPill) {
          iataPill.textContent = airport.iata_code || '---';
          iataPill.classList.remove('d-none');
        }
        if (container) container.classList.add('has-selection');
      } else {
        if (textInput) textInput.value = '';
        if (iataPill) {
          iataPill.textContent = '---';
          iataPill.classList.add('d-none');
        }
        if (container) container.classList.remove('has-selection');
      }

      isFiltering = false;
      if (container) container.classList.remove('is-filtering');
      if (clearBtn) clearBtn.classList.add('d-none');
    }

    function filterAndRank(rawQuery) {
      const query = normalizeText(rawQuery);
      if (!isFiltering || !query) {
        return state.airports.slice();
      }

      const scored = [];
      state.airports.forEach(airport => {
        const iata = normalizeText(airport.iata_code);
        const city = normalizeText(airport.city);
        const name = normalizeText(airport.name);
        const dept = normalizeText(airport.department);

        let score = 0;
        if (iata === query) score = 100;
        else if (iata.startsWith(query)) score = 80;
        else if (city.startsWith(query)) score = 60;
        else if (name.startsWith(query)) score = 40;
        else if (
          iata.includes(query) ||
          city.includes(query) ||
          name.includes(query) ||
          dept.includes(query)
        ) {
          score = 20;
        }

        if (score > 0) {
          scored.push({ airport, score });
        }
      });

      scored.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        return (a.airport.city || '').localeCompare(b.airport.city || '', 'es');
      });

      return scored.map(entry => entry.airport);
    }

    function renderOptions() {
      if (!listbox) return;
      const query = textInput ? textInput.value : '';
      visibleOptions = filterAndRank(query);

      const selectedId = hiddenInput ? String(hiddenInput.value) : '';
      const disabledId = getCounterpartId ? String(getCounterpartId() || '') : '';

      if (visibleOptions.length === 0) {
        listbox.innerHTML = `
          <div class="combobox-dropdown-header">
            <span>0 coincidencias</span>
          </div>
          <div class="combobox-empty">
            No se encontraron aeropuertos para "<strong>${escapeHtml(query.trim())}</strong>".
          </div>
        `;
        highlightedIndex = -1;
        return;
      }

      // Ajustar índice resaltado válido
      if (highlightedIndex >= visibleOptions.length) {
        highlightedIndex = -1;
      }
      if (highlightedIndex === -1 && isFiltering) {
        highlightedIndex = visibleOptions.findIndex(a => String(a.id) !== disabledId);
      }

      const headerLabel = isFiltering && normalizeText(query)
        ? `${visibleOptions.length} coincidencia${visibleOptions.length === 1 ? '' : 's'}`
        : `${visibleOptions.length} terminales disponibles — escribe para filtrar`;

      const rowsHtml = visibleOptions.map((airport, idx) => {
        const idStr = String(airport.id);
        const isSelected = idStr === selectedId;
        const isDisabled = Boolean(disabledId && idStr === disabledId);
        const isHighlighted = idx === highlightedIndex;

        const classes = [
          'combobox-option',
          isSelected ? 'is-selected' : '',
          isDisabled ? 'is-disabled' : '',
          isHighlighted ? 'is-highlighted' : ''
        ].filter(Boolean).join(' ');

        let statusBadge = '';
        if (isDisabled) {
          statusBadge = `<span class="option-badge-used">En ${escapeHtml(counterpartLabel)}</span>`;
        } else if (isSelected) {
          statusBadge = `
            <span class="option-badge-check" aria-label="Seleccionado">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            </span>
          `;
        }

        return `
          <div class="${classes}" role="option" aria-selected="${isSelected}" aria-disabled="${isDisabled}" data-index="${idx}" data-id="${idStr}">
            <span class="option-iata">${escapeHtml(airport.iata_code || '---')}</span>
            <div class="option-details">
              <div class="option-title">${escapeHtml(airport.city)} — ${escapeHtml(airport.name)}</div>
              <div class="option-meta">${escapeHtml(airport.department || 'Colombia')} · ${escapeHtml(airport.type || 'Comercial')}</div>
            </div>
            ${statusBadge}
          </div>
        `;
      }).join('');

      listbox.innerHTML = `
        <div class="combobox-dropdown-header">
          <span>${headerLabel}</span>
        </div>
        ${rowsHtml}
      `;
    }

    function open(startFiltering = false) {
      if (!listbox || !container) return;
      isOpen = true;
      if (startFiltering) {
        isFiltering = true;
        container.classList.add('is-filtering');
      }
      container.classList.add('is-open');
      listbox.classList.remove('d-none');
      if (textInput) textInput.setAttribute('aria-expanded', 'true');

      if (!isFiltering) {
        const selectedId = hiddenInput ? String(hiddenInput.value) : '';
        highlightedIndex = visibleOptions.findIndex(a => String(a.id) === selectedId);
      }
      renderOptions();

      if (!isFiltering && hiddenInput && hiddenInput.value) {
        const activeEl = listbox.querySelector('.combobox-option.is-selected');
        if (activeEl) {
          activeEl.scrollIntoView({ block: 'nearest' });
        }
      }
    }

    function close(restoreLabel = true) {
      if (!listbox || !container) return;
      isOpen = false;
      highlightedIndex = -1;
      container.classList.remove('is-open');
      listbox.classList.add('d-none');
      if (textInput) textInput.setAttribute('aria-expanded', 'false');
      if (restoreLabel) {
        syncVisualSelection();
      }
    }

    function selectAirport(airport, triggerChange = true) {
      if (!airport || !hiddenInput) return;
      const disabledId = getCounterpartId ? String(getCounterpartId() || '') : '';
      if (disabledId && String(airport.id) === disabledId) {
        return;
      }
      hiddenInput.value = String(airport.id);
      close(true);
      if (triggerChange && typeof onChange === 'function') {
        onChange(airport);
      }
    }

    function moveHighlight(step) {
      if (visibleOptions.length === 0) return;
      const disabledId = getCounterpartId ? String(getCounterpartId() || '') : '';
      let next = highlightedIndex;

      for (let i = 0; i < visibleOptions.length; i++) {
        next = (next + step + visibleOptions.length) % visibleOptions.length;
        if (String(visibleOptions[next].id) !== disabledId) {
          highlightedIndex = next;
          renderOptions();
          const targetEl = listbox.querySelector(`.combobox-option[data-index="${highlightedIndex}"]`);
          if (targetEl) targetEl.scrollIntoView({ block: 'nearest' });
          return;
        }
      }
    }

    if (textInput) {
      textInput.addEventListener('focus', () => {
        justFocused = true;
        textInput.select();
        open(false);
      });

      textInput.addEventListener('mouseup', (e) => {
        if (justFocused) {
          e.preventDefault();
          justFocused = false;
        }
      });

      textInput.addEventListener('click', () => {
        if (!isOpen) {
          open(false);
        }
      });

      textInput.addEventListener('input', () => {
        isFiltering = true;
        if (container) container.classList.add('is-filtering');
        if (clearBtn) clearBtn.classList.toggle('d-none', !textInput.value);
        highlightedIndex = -1;
        open(true);
      });

      textInput.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          if (!isOpen) open(false);
          else moveHighlight(1);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          if (!isOpen) open(false);
          else moveHighlight(-1);
        } else if (e.key === 'Enter') {
          if (isOpen) {
            e.preventDefault();
            const disabledId = getCounterpartId ? String(getCounterpartId() || '') : '';
            let candidate = visibleOptions[highlightedIndex];
            if (!candidate && visibleOptions.length === 1) {
              candidate = visibleOptions[0];
            }
            if (candidate && String(candidate.id) !== disabledId) {
              selectAirport(candidate, true);
            }
          }
        } else if (e.key === 'Escape') {
          if (isOpen) {
            e.preventDefault();
            close(true);
            textInput.blur();
          }
        } else if (e.key === 'Tab') {
          if (isOpen) {
            close(true);
          }
        }
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener('mousedown', (e) => e.preventDefault());
      clearBtn.addEventListener('click', () => {
        if (textInput) {
          textInput.value = '';
          textInput.focus();
        }
        isFiltering = true;
        if (container) container.classList.add('is-filtering');
        clearBtn.classList.add('d-none');
        highlightedIndex = -1;
        open(true);
      });
    }

    if (toggleBtn) {
      toggleBtn.addEventListener('mousedown', (e) => e.preventDefault());
      toggleBtn.addEventListener('click', () => {
        if (isOpen) {
          close(true);
        } else {
          if (textInput) textInput.focus();
          open(false);
        }
      });
    }

    if (listbox) {
      listbox.addEventListener('mousedown', (e) => {
        const optionEl = e.target.closest('.combobox-option');
        if (!optionEl) return;
        e.preventDefault();
        if (optionEl.classList.contains('is-disabled')) return;
        const airportId = optionEl.getAttribute('data-id');
        const airport = state.airportsMap[airportId];
        if (airport) {
          selectAirport(airport, true);
        }
      });
    }

    document.addEventListener('click', (e) => {
      if (isOpen && wrapper && !wrapper.contains(e.target)) {
        close(true);
      }
    });

    return {
      setValue(id, triggerChange = false) {
        if (!hiddenInput) return;
        hiddenInput.value = id ? String(id) : '';
        syncVisualSelection();
        if (isOpen) renderOptions();
        if (triggerChange && typeof onChange === 'function') {
          onChange(state.airportsMap[hiddenInput.value] || null);
        }
      },
      getValue() {
        return hiddenInput ? hiddenInput.value : '';
      },
      refresh() {
        syncVisualSelection();
        if (isOpen) renderOptions();
      }
    };
  }

  let originCombobox = null;
  let destCombobox = null;

  function handleRouteComboboxChange() {
    validateRouteSelection();
    updateBoardingPassPreview();
    if (originCombobox && destCombobox) {
      originCombobox.refresh();
      destCombobox.refresh();
    }
  }

  originCombobox = createAirportCombobox({
    wrapperId: 'origin-combobox-wrapper',
    hiddenInputId: 'origin_airport',
    textInputId: 'origin_airport_input',
    iataPillId: 'origin-iata-pill',
    clearBtnId: 'origin-clear-btn',
    toggleBtnId: 'origin-toggle-btn',
    listboxId: 'origin-combobox-listbox',
    counterpartLabel: 'Destino',
    getCounterpartId: () => destCombobox ? destCombobox.getValue() : '',
    onChange: handleRouteComboboxChange
  });

  destCombobox = createAirportCombobox({
    wrapperId: 'destination-combobox-wrapper',
    hiddenInputId: 'destination_airport',
    textInputId: 'destination_airport_input',
    iataPillId: 'destination-iata-pill',
    clearBtnId: 'destination-clear-btn',
    toggleBtnId: 'destination-toggle-btn',
    listboxId: 'destination-combobox-listbox',
    counterpartLabel: 'Origen',
    getCounterpartId: () => originCombobox ? originCombobox.getValue() : '',
    onChange: handleRouteComboboxChange
  });

  function populateAirportSelects(airports) {
    // Preseleccionar BOG y MDE si existen y no hay selección previa
    const currentOrigin = originCombobox.getValue();
    const currentDest = destCombobox.getValue();

    if (!currentOrigin) {
      const bog = airports.find(a => a.iata_code === 'BOG') || airports[0];
      if (bog) originCombobox.setValue(bog.id, false);
    } else {
      originCombobox.refresh();
    }

    if (!currentDest) {
      const mde = airports.find(a => a.iata_code === 'MDE') || airports[1];
      if (mde) destCombobox.setValue(mde.id, false);
    } else {
      destCombobox.refresh();
    }

    validateRouteSelection();
    updateBoardingPassPreview();
  }

  // ==========================================
  // 2. MAPA GEOGRÁFICO CON PLOTLY JS
  // ==========================================
  async function loadAirportsMap() {
    try {
      const response = await fetch('/api/v1/airports/map/plotly');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();

      state.plotlyData = payload.data;
      state.plotlyLayout = payload.layout;

      // Personalizar estilo para apariencia corporativa seria
      if (payload.layout) {
        payload.layout.paper_bgcolor = '#f8fafc';
        payload.layout.geo = Object.assign(payload.layout.geo || {}, {
          bgcolor: '#f1f5f9',
          lakecolor: '#e2e8f0',
          landcolor: '#ffffff',
          subunitcolor: '#cbd5e1',
          countrycolor: '#94a3b8'
        });
      }

      await Plotly.newPlot('map', payload.data, payload.layout, {
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['lasso2d', 'select2d', 'hoverClosestGeo']
      });

      state.mapRendered = true;

      // Escuchar clic en marcadores del mapa
      const mapDiv = document.getElementById('map');
      mapDiv.on('plotly_click', (eventData) => {
        if (!eventData || !eventData.points || eventData.points.length === 0) return;
        const point = eventData.points[0];
        
        let foundAirport = null;
        if (point.id !== undefined && state.airportsMap[point.id]) {
          foundAirport = state.airportsMap[point.id];
        } else if (point.text) {
          foundAirport = state.airports.find(a => a.iata_code === point.text);
        }

        if (foundAirport) {
          updateAirportDetailSheet(foundAirport);
          showToast('Aeropuerto Seleccionado', `${foundAirport.name} (${foundAirport.iata_code})`, 'info');
        }
      });

    } catch (err) {
      console.warn('Plotly map initialization error:', err);
      state.mapRendered = false;
    }
  }

  function updateAirportDetailSheet(airport) {
    if (!airport) return;
    state.selectedAirport = airport;

    dom.detailIataBadge.textContent = airport.iata_code || '---';
    dom.detailName.textContent = airport.name || 'Sin Nombre';
    dom.detailCityDept.textContent = `${airport.city || '--'}, ${airport.department || '--'}`;
    dom.detailId.textContent = `ID: ${airport.id}`;
    dom.detailIata.textContent = airport.iata_code || '---';
    dom.detailType.textContent = airport.type || 'Comercial';
    dom.detailCoords.textContent = `${Number(airport.latitude || 0).toFixed(4)}, ${Number(airport.longitude || 0).toFixed(4)}`;
  }

  // Centrar mapa
  if (dom.btnRecenterMap) {
    dom.btnRecenterMap.addEventListener('click', () => {
      if (window.Plotly && state.mapRendered) {
        Plotly.relayout('map', {
          'geo.center.lat': 4.5709,
          'geo.center.lon': -74.2973,
          'geo.projection.scale': 4.5
        });
        showToast('Enfoque Geográfico', 'Vista cartográfica centrada en Colombia.', 'info');
      }
    });
  }

  // Filtrado y Búsqueda en el Directorio de Aeropuertos
  function renderAirportsDirectoryTable(airportsToRender) {
    if (!dom.airportsCatalogTbody) return;

    if (airportsToRender.length === 0) {
      dom.airportsCatalogTbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No se encontraron aeropuertos coincidentes con los criterios.</td></tr>';
      return;
    }

    dom.airportsCatalogTbody.innerHTML = '';
    airportsToRender.forEach(a => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span class="badge badge-info">${a.iata_code}</span></td>
        <td><strong>${a.name}</strong></td>
        <td>${a.city}</td>
        <td>${a.department}</td>
        <td><span class="badge ${a.type?.toLowerCase().includes('internacional') ? 'badge-accent' : 'badge-primary'}">${a.type || 'Nacional'}</span></td>
        <td class="code-font">${Number(a.latitude).toFixed(3)}, ${Number(a.longitude).toFixed(3)}</td>
        <td class="text-right">
          <button type="button" class="btn btn-sm btn-secondary btn-select-airport" data-id="${a.id}">
            Seleccionar
          </button>
        </td>
      `;

      tr.querySelector('.btn-select-airport').addEventListener('click', () => {
        updateAirportDetailSheet(a);
        showToast('Ficha Técnica', `Cargado: ${a.name} (${a.iata_code})`, 'info');
        window.scrollTo({ top: 350, behavior: 'smooth' });
      });

      dom.airportsCatalogTbody.appendChild(tr);
    });
  }

  function filterAirportsList() {
    const query = dom.mapSearchInput.value.trim().toLowerCase();
    const activeChip = document.querySelector('.chip.active[data-filter]');
    const filterType = activeChip ? activeChip.getAttribute('data-filter') : 'all';

    let filtered = state.airports.filter(a => {
      const matchesQuery = !query || 
        (a.name && a.name.toLowerCase().includes(query)) ||
        (a.iata_code && a.iata_code.toLowerCase().includes(query)) ||
        (a.city && a.city.toLowerCase().includes(query)) ||
        (a.department && a.department.toLowerCase().includes(query));

      let matchesType = true;
      if (filterType === 'internacional') {
        matchesType = a.type && a.type.toLowerCase().includes('internacional');
      } else if (filterType === 'nacional') {
        matchesType = !a.type || !a.type.toLowerCase().includes('internacional');
      }

      return matchesQuery && matchesType;
    });

    if (dom.airportResultsCount) {
      dom.airportResultsCount.textContent = `${filtered.length} resultados`;
    }

    if (dom.btnClearAirportSearch) {
      dom.btnClearAirportSearch.classList.toggle('d-none', !query);
    }

    renderAirportsDirectoryTable(filtered);
  }

  if (dom.mapSearchInput) {
    dom.mapSearchInput.addEventListener('input', filterAirportsList);
  }

  if (dom.btnClearAirportSearch) {
    dom.btnClearAirportSearch.addEventListener('click', () => {
      dom.mapSearchInput.value = '';
      filterAirportsList();
    });
  }

  dom.filterChips.forEach(chip => {
    chip.addEventListener('click', () => {
      dom.filterChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      filterAirportsList();
    });
  });

  // Acciones de la Ficha Técnica: Fijar como Origen o Destino en el Planificador
  if (dom.btnUseAsOrigin) {
    dom.btnUseAsOrigin.addEventListener('click', () => {
      if (!state.selectedAirport) return;
      originCombobox.setValue(state.selectedAirport.id, true);
      switchTab('tab-planner');
      showToast('Ruta Actualizada', `${state.selectedAirport.name} fijado como aeropuerto de salida.`, 'info');
    });
  }

  if (dom.btnUseAsDest) {
    dom.btnUseAsDest.addEventListener('click', () => {
      if (!state.selectedAirport) return;
      destCombobox.setValue(state.selectedAirport.id, true);
      switchTab('tab-planner');
      showToast('Ruta Actualizada', `${state.selectedAirport.name} fijado como aeropuerto de llegada.`, 'info');
    });
  }

  // ==========================================
  // 3. PLANIFICADOR DE ITINERARIOS & PREVIEW
  // ==========================================
  function setDefaultDateTime() {
    const now = new Date();
    now.setDate(now.getDate() + 3);
    now.setHours(9, 0, 0, 0);

    // Ajuste seguro a formato YYYY-MM-DDTHH:mm
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    
    dom.departureDateInput.value = `${year}-${month}-${day}T${hours}:${minutes}`;
  }

  function validateRouteSelection() {
    const origId = originCombobox.getValue();
    const destId = destCombobox.getValue();

    const isCollision = Boolean(origId && destId && origId === destId);
    if (dom.routeWarning) {
      dom.routeWarning.classList.toggle('d-none', !isCollision);
    }

    if (dom.btnSubmit) {
      dom.btnSubmit.disabled = isCollision;
    }

    return !isCollision;
  }

  function updateBoardingPassPreview() {
    // 1. Pasajero
    const passengerName = dom.userNameInput.value.trim() || 'Nombre del Pasajero';
    dom.bpPassengerName.textContent = passengerName;

    // 2. Origen
    const origId = originCombobox.getValue();
    const origAirport = state.airportsMap[origId];
    if (origAirport) {
      dom.bpOriginCode.textContent = origAirport.iata_code || 'ORG';
      dom.bpOriginCity.textContent = origAirport.city || origAirport.name;
    } else {
      dom.bpOriginCode.textContent = 'ORG';
      dom.bpOriginCity.textContent = 'Ciudad Origen';
    }

    // 3. Destino
    const destId = destCombobox.getValue();
    const destAirport = state.airportsMap[destId];
    if (destAirport) {
      dom.bpDestCode.textContent = destAirport.iata_code || 'DST';
      dom.bpDestCity.textContent = destAirport.city || destAirport.name;
    } else {
      dom.bpDestCode.textContent = 'DST';
      dom.bpDestCity.textContent = 'Ciudad Destino';
    }

    // 4. Duración
    const duration = dom.durationMinutesInput.value || 55;
    dom.bpDurationTag.textContent = `${duration} MIN`;

    // 5. Fecha
    if (dom.departureDateInput.value) {
      try {
        const d = new Date(dom.departureDateInput.value);
        dom.bpDepartureDate.textContent = d.toLocaleDateString('es-CO', {
          weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
        });
      } catch {
        dom.bpDepartureDate.textContent = dom.departureDateInput.value;
      }
    } else {
      dom.bpDepartureDate.textContent = '--';
    }

    // 6. Estado
    dom.bpStatusBadge.textContent = 'BORRADOR';
    dom.bpStatusBadge.className = 'meta-value badge-pill badge-draft';
  }

  // Listeners de actualización reactiva del Boarding Pass
  dom.userNameInput.addEventListener('input', updateBoardingPassPreview);
  dom.departureDateInput.addEventListener('change', updateBoardingPassPreview);
  dom.durationMinutesInput.addEventListener('input', updateBoardingPassPreview);

  // Atajos de duración
  dom.presetChips.forEach(chip => {
    chip.addEventListener('click', () => {
      dom.presetChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      dom.durationMinutesInput.value = chip.getAttribute('data-mins');
      updateBoardingPassPreview();
    });
  });

  // Intercambio de ruta (Swap)
  if (dom.btnSwapRoute) {
    dom.btnSwapRoute.addEventListener('click', () => {
      const origVal = originCombobox.getValue();
      const destVal = destCombobox.getValue();
      originCombobox.setValue(destVal, false);
      destCombobox.setValue(origVal, false);
      handleRouteComboboxChange();
    });
  }

  // ==========================================
  // AUTENTICACIÓN JWT TRANSPARENTE (SESSION)
  // ==========================================
  const JWT_SESSION_KEY = 'aero_jwt_token';

  async function obtainJwtToken(forceRefresh = false, usernameHint = null) {
    if (!forceRefresh) {
      const existing = sessionStorage.getItem(JWT_SESSION_KEY);
      if (existing) return existing;
    }

    const username =
      (usernameHint && String(usernameHint).trim()) ||
      (dom.userNameInput && dom.userNameInput.value.trim()) ||
      'aero-frontend-user';

    const res = await fetch('/api/v1/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username })
    });

    if (!res.ok) {
      throw new Error(`No se pudo obtener token JWT (HTTP ${res.status})`);
    }

    const data = await res.json();
    if (data && data.access_token) {
      sessionStorage.setItem(JWT_SESSION_KEY, data.access_token);
      return data.access_token;
    }
    throw new Error('Respuesta de autenticación sin access_token');
  }

  async function fetchWithJwt(url, options = {}, usernameHint = null) {
    const token = await obtainJwtToken(false, usernameHint);
    const headers = Object.assign({}, options.headers || {}, {
      Authorization: `Bearer ${token}`
    });

    let response = await fetch(url, Object.assign({}, options, { headers }));
    if (response.status === 401) {
      sessionStorage.removeItem(JWT_SESSION_KEY);
      const refreshedToken = await obtainJwtToken(true, usernameHint);
      const retryHeaders = Object.assign({}, options.headers || {}, {
        Authorization: `Bearer ${refreshedToken}`
      });
      response = await fetch(url, Object.assign({}, options, { headers: retryHeaders }));
    }
    return response;
  }

  // Enviar Formulario de Itinerario
  dom.form.addEventListener('submit', async (e) => {
    e.preventDefault();

    if (!validateRouteSelection()) {
      showToast('Ruta Inválida', 'El aeropuerto de salida y llegada no pueden ser el mismo.', 'error');
      return;
    }

    const originId = parseInt(originCombobox.getValue(), 10);
    const destId = parseInt(destCombobox.getValue(), 10);

    if (!originId || !destId) {
      showToast('Campos Incompletos', 'Seleccione un aeropuerto de salida y uno de llegada.', 'error');
      return;
    }

    const userName = dom.userNameInput.value.trim();
    if (userName.length < 2) {
      showToast('Nombre Requerido', 'Ingrese el nombre completo del pasajero (mínimo 2 caracteres).', 'error');
      dom.userNameInput.focus();
      return;
    }

    if (!dom.departureDateInput.value || Number.isNaN(new Date(dom.departureDateInput.value).getTime())) {
      showToast('Fecha Inválida', 'Seleccione una fecha y hora de salida válida.', 'error');
      dom.departureDateInput.focus();
      return;
    }

    const payload = {
      user_name: userName,
      origin_airport_id: originId,
      destination_airport_id: destId,
      departure_date: new Date(dom.departureDateInput.value).toISOString(),
      duration_minutes: parseInt(dom.durationMinutesInput.value, 10) || 55
    };

    dom.btnSubmit.disabled = true;
    dom.btnSubmitText.textContent = 'Validando y persistiendo transacción ACID...';

    try {
      const response = await fetchWithJwt('/api/v1/itineraries', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      }, payload.user_name);

      const resData = await response.json();

      if (response.status === 201) {
        showToast('Itinerario Confirmado', `Reserva guardada para ${resData.user_name}. Evento outbox publicado en RabbitMQ.`, 'success');
        
        // Actualizar el boarding pass a confirmado
        dom.bpStatusBadge.textContent = 'CONFIRMADO';
        dom.bpStatusBadge.className = 'meta-value badge-pill badge-success';

        // Recargar itinerarios en segundo plano
        await loadItineraries();

        // Opcional: limpiar formulario después de 3 segundos
        setTimeout(() => {
          dom.form.reset();
          setDefaultDateTime();
          // Restaurar valores por defecto BOG y MDE
          const bog = state.airports.find(a => a.iata_code === 'BOG') || state.airports[0];
          const mde = state.airports.find(a => a.iata_code === 'MDE') || state.airports[1];
          if (bog) originCombobox.setValue(bog.id, false);
          if (mde) destCombobox.setValue(mde.id, false);
          handleRouteComboboxChange();
        }, 3000);

      } else {
        let errorMsg = 'No se pudo crear el itinerario.';
        if (typeof resData.detail === 'string') {
          errorMsg = resData.detail;
        } else if (Array.isArray(resData.detail)) {
          errorMsg = resData.detail
            .map(item => {
              const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : '';
              return field ? `${field}: ${item.msg}` : item.msg || JSON.stringify(item);
            })
            .join(' | ');
        } else if (resData.detail && typeof resData.detail === 'object') {
          errorMsg = resData.detail.msg || JSON.stringify(resData.detail);
        }
        showToast('Error de Validación', errorMsg, 'error');
      }
    } catch (err) {
      showToast('Falla de Conexión', `Error al comunicar con el API Gateway: ${err.message}`, 'error');
    } finally {
      dom.btnSubmit.disabled = false;
      dom.btnSubmitText.textContent = 'Confirmar y Registrar Itinerario';
    }
  });

  // ==========================================
  // 4. MIS ITINERARIOS Y RESERVAS
  // ==========================================
  async function loadItineraries() {
    try {
      const response = await fetch('/api/v1/itineraries');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();

      state.itineraries = data;
      if (dom.badgeItinerariesCount) {
        dom.badgeItinerariesCount.textContent = data.length;
      }

      renderItineraries();

    } catch (err) {
      console.warn('Error loading itineraries:', err);
    }
  }

  function renderItineraries() {
    const query = dom.itinerarySearchInput ? dom.itinerarySearchInput.value.trim().toLowerCase() : '';

    const filtered = state.itineraries.filter(item => {
      if (!query) return true;
      const passenger = (item.user_name || '').toLowerCase();
      const orig = (state.airportsMap[item.origin_airport_id]?.name || '').toLowerCase();
      const origIata = (state.airportsMap[item.origin_airport_id]?.iata_code || '').toLowerCase();
      const dest = (state.airportsMap[item.destination_airport_id]?.name || '').toLowerCase();
      const destIata = (state.airportsMap[item.destination_airport_id]?.iata_code || '').toLowerCase();
      const id = String(item.id || '').toLowerCase();

      return passenger.includes(query) || orig.includes(query) || origIata.includes(query) ||
             dest.includes(query) || destIata.includes(query) || id.includes(query);
    });

    renderItinerariesCards(filtered);
    renderItinerariesTable(filtered);
  }

  function cloneItineraryToPlanner(item) {
    dom.userNameInput.value = item.user_name;
    originCombobox.setValue(item.origin_airport_id, false);
    destCombobox.setValue(item.destination_airport_id, false);
    dom.durationMinutesInput.value = item.duration_minutes;
    handleRouteComboboxChange();
    switchTab('tab-planner');
    showToast('Itinerario Clonado', `Datos de ${item.user_name} transferidos al formulario.`, 'info');
  }

  // Renderizado en formato de Tarjetas de Embarque
  function renderItinerariesCards(itineraries) {
    if (!dom.itinerariesCardsView) return;

    if (itineraries.length === 0) {
      dom.itinerariesCardsView.innerHTML = `
        <div class="card text-center" style="grid-column: 1 / -1; padding: 3rem 1rem;">
          <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="color: var(--slate-400); margin: 0 auto 1rem auto;">
            <path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/>
            <path d="M13 5v2M13 17v2M13 11v2"/>
          </svg>
          <h3 style="color: var(--slate-700); font-size: 1.1rem;">No hay itinerarios registrados</h3>
          <p class="subtitle">Utilice la pestaña "Planificador de Vuelos" para crear su primera reserva aeronáutica.</p>
        </div>
      `;
      return;
    }

    dom.itinerariesCardsView.innerHTML = '';
    itineraries.forEach(item => {
      const orig = state.airportsMap[item.origin_airport_id] || { iata_code: 'ORG', name: `ID ${item.origin_airport_id}`, city: 'Origen' };
      const dest = state.airportsMap[item.destination_airport_id] || { iata_code: 'DST', name: `ID ${item.destination_airport_id}`, city: 'Destino' };
      
      const dateFormatted = new Date(item.departure_date).toLocaleDateString('es-CO', {
        month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
      });

      const card = document.createElement('div');
      card.className = 'itinerary-item-card';
      card.innerHTML = `
        <div class="itinerary-card-top">
          <div class="passenger-info">
            <h4>${item.user_name}</h4>
            <span class="uuid-tag">UUID: ${String(item.id).slice(0, 8)}...</span>
          </div>
          <span class="badge ${item.status === 'CONFIRMED' ? 'badge-success' : 'badge-primary'}">${item.status || 'CREATED'}</span>
        </div>

        <div class="itinerary-card-route">
          <div class="route-endpoint">
            <span class="route-iata">${orig.iata_code}</span>
            <span class="route-city">${orig.city || orig.name}</span>
          </div>

          <div class="route-arrow-box">
            <span class="route-duration">${item.duration_minutes} min</span>
            <svg class="svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </div>

          <div class="route-endpoint end">
            <span class="route-iata">${dest.iata_code}</span>
            <span class="route-city">${dest.city || dest.name}</span>
          </div>
        </div>

        <div class="itinerary-card-details">
          <span>Fecha: <strong>${dateFormatted}</strong></span>
          <span>Vuelo: <strong>AV-${String(item.id).slice(0, 4).toUpperCase()}</strong></span>
        </div>

        <div class="itinerary-card-actions">
          <button class="btn btn-sm btn-secondary btn-clone-itinerary" title="Clonar datos al planificador">
            <svg class="svg-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>
            Clonar
          </button>
          <button class="btn btn-sm btn-secondary btn-export-ticket" title="Descargar billete JSON">
            <svg class="svg-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/></svg>
            Ticket
          </button>
          <button class="btn btn-sm btn-danger btn-delete-itinerary" title="Cancelar este itinerario">
            <svg class="svg-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/></svg>
            Cancelar
          </button>
        </div>
      `;

      // Listeners de acción
      card.querySelector('.btn-clone-itinerary').addEventListener('click', () => {
        cloneItineraryToPlanner(item);
      });

      card.querySelector('.btn-export-ticket').addEventListener('click', () => {
        exportSingleItinerary(item, orig, dest);
      });

      card.querySelector('.btn-delete-itinerary').addEventListener('click', () => {
        openDeleteModal(item, orig, dest);
      });

      dom.itinerariesCardsView.appendChild(card);
    });
  }

  // Renderizado en formato de Tabla
  function renderItinerariesTable(itineraries) {
    if (!dom.itinerariesList) return;

    if (itineraries.length === 0) {
      dom.itinerariesList.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No se registran itinerarios activos.</td></tr>';
      return;
    }

    dom.itinerariesList.innerHTML = '';
    itineraries.forEach(item => {
      const orig = state.airportsMap[item.origin_airport_id] || { iata_code: 'ORG', name: `ID ${item.origin_airport_id}` };
      const dest = state.airportsMap[item.destination_airport_id] || { iata_code: 'DST', name: `ID ${item.destination_airport_id}` };
      
      const dateFormatted = new Date(item.departure_date).toLocaleDateString('es-CO', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
      });

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${item.user_name}</strong></td>
        <td><span class="badge badge-info">${orig.iata_code}</span> &rarr; <span class="badge badge-info">${dest.iata_code}</span></td>
        <td>${dateFormatted}</td>
        <td>${item.duration_minutes} min</td>
        <td class="code-font" style="font-size: 0.75rem;">${String(item.id).slice(0, 13)}...</td>
        <td><span class="badge ${item.status === 'CONFIRMED' ? 'badge-success' : 'badge-primary'}">${item.status || 'CREATED'}</span></td>
        <td class="text-right">
          <button class="btn btn-sm btn-secondary btn-clone-itinerary" title="Clonar">Clonar</button>
          <button class="btn btn-sm btn-danger btn-delete-itinerary" title="Eliminar">Cancelar</button>
        </td>
      `;

      tr.querySelector('.btn-clone-itinerary').addEventListener('click', () => {
        cloneItineraryToPlanner(item);
      });

      tr.querySelector('.btn-delete-itinerary').addEventListener('click', () => {
        openDeleteModal(item, orig, dest);
      });

      dom.itinerariesList.appendChild(tr);
    });
  }

  // Toggle vista Tarjetas / Tabla
  if (dom.btnViewCards && dom.btnViewTable) {
    dom.btnViewCards.addEventListener('click', () => {
      dom.btnViewCards.classList.add('active');
      dom.btnViewTable.classList.remove('active');
      dom.itinerariesCardsView.classList.remove('d-none');
      dom.itinerariesTableView.classList.add('d-none');
      state.currentView = 'cards';
    });

    dom.btnViewTable.addEventListener('click', () => {
      dom.btnViewTable.classList.add('active');
      dom.btnViewCards.classList.remove('active');
      dom.itinerariesTableView.classList.remove('d-none');
      dom.itinerariesCardsView.classList.add('d-none');
      state.currentView = 'table';
    });
  }

  if (dom.itinerarySearchInput) {
    dom.itinerarySearchInput.addEventListener('input', renderItineraries);
  }

  if (dom.btnRefreshItineraries) {
    dom.btnRefreshItineraries.addEventListener('click', async () => {
      await loadItineraries();
      showToast('Itinerarios Sincronizados', 'Lista de reservas actualizada desde PostgreSQL.', 'info');
    });
  }

  // Exportar itinerarios masivo en formato JSON
  if (dom.btnExportItineraries) {
    dom.btnExportItineraries.addEventListener('click', () => {
      if (state.itineraries.length === 0) {
        showToast('Exportación Cancelada', 'No hay itinerarios para exportar.', 'info');
        return;
      }
      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(state.itineraries, null, 2));
      const dlAnchor = document.createElement('a');
      dlAnchor.setAttribute('href', dataStr);
      dlAnchor.setAttribute('download', `aero_itinerarios_${new Date().toISOString().slice(0, 10)}.json`);
      dlAnchor.click();
      dlAnchor.remove();
      showToast('Exportación Exitosa', 'Copia de respaldo en formato JSON descargada.', 'success');
    });
  }

  function exportSingleItinerary(item, orig, dest) {
    const payload = {
      sistema: 'AeroItinerarios Enterprise',
      reserva_id: item.id,
      pasajero: item.user_name,
      origen: { id: item.origin_airport_id, iata: orig.iata_code, nombre: orig.name, ciudad: orig.city },
      destino: { id: item.destination_airport_id, iata: dest.iata_code, nombre: dest.name, ciudad: dest.city },
      fecha_salida_utc: item.departure_date,
      duracion_minutos: item.duration_minutes,
      estado_transaccional: item.status,
      timestamp_exportacion: new Date().toISOString()
    };

    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(payload, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute('href', dataStr);
    dlAnchor.setAttribute('download', `ticket_${item.user_name.replace(/\s+/g, '_')}_${orig.iata_code}-${dest.iata_code}.json`);
    dlAnchor.click();
    dlAnchor.remove();
    showToast('Billete Exportado', `Ticket descargado para ${item.user_name}.`, 'success');
  }

  // ==========================================
  // MODAL DE CONFIRMACIÓN CORPORATIVO (DELETE)
  // ==========================================
  function openDeleteModal(item, orig, dest) {
    state.itineraryToDelete = item;
    dom.modalPassengerName.textContent = item.user_name;
    dom.modalRouteName.textContent = `${orig.iata_code} → ${dest.iata_code}`;
    dom.deleteModal.classList.remove('d-none');
  }

  function closeDeleteModal() {
    state.itineraryToDelete = null;
    dom.deleteModal.classList.add('d-none');
  }

  if (dom.btnCancelDelete) {
    dom.btnCancelDelete.addEventListener('click', closeDeleteModal);
  }

  // Cerrar al hacer clic en el backdrop
  dom.deleteModal.addEventListener('click', (e) => {
    if (e.target === dom.deleteModal) closeDeleteModal();
  });

  if (dom.btnConfirmDelete) {
    dom.btnConfirmDelete.addEventListener('click', async () => {
      if (!state.itineraryToDelete) return;
      const targetId = state.itineraryToDelete.id;

      try {
        const response = await fetchWithJwt(`/api/v1/itineraries/${targetId}`, {
          method: 'DELETE'
        });

        if (response.status === 204 || response.ok) {
          showToast('Reserva Cancelada', `El itinerario ha sido eliminado permanentemente de PostgreSQL.`, 'success');
          closeDeleteModal();
          await loadItineraries();
        } else {
          showToast('Error', 'No se pudo eliminar el itinerario seleccionado.', 'error');
        }
      } catch (err) {
        showToast('Falla de Red', `Error al comunicar con Itinerary Service: ${err.message}`, 'error');
      }
    });
  }

  // ==========================================
  // 5. CENTRO DE MONITOREO & AUDITORÍA
  // ==========================================
  async function checkSystemHealth() {
    const t0 = performance.now();

    // 1. API Gateway Health
    try {
      const gwRes = await fetch('/health');
      const elapsed = Math.round(performance.now() - t0);
      if (gwRes.ok) {
        if (dom.gwHealthStatus) dom.gwHealthStatus.textContent = 'OPERATIVO';
        if (dom.gwLatency) dom.gwLatency.textContent = `${elapsed} ms`;
        if (dom.gatewayIndicator) {
          dom.gatewayIndicator.className = 'status-chip chip-success';
          dom.gatewayIndicator.querySelector('.status-label').textContent = 'Gateway Activo';
        }
      } else {
        throw new Error(`HTTP ${gwRes.status}`);
      }
    } catch {
      if (dom.gwHealthStatus) dom.gwHealthStatus.textContent = 'DEGRADADO';
      if (dom.gatewayIndicator) {
        dom.gatewayIndicator.className = 'status-chip chip-warning';
        dom.gatewayIndicator.querySelector('.status-label').textContent = 'Gateway Offline';
      }
    }

    // 2. Airport Service & Circuit Breaker Health
    try {
      const res = await fetch('/api/v1/airports/health');
      if (res.ok) {
        const data = await res.json();
        const cb = data.circuit_breaker || {};
        const cbState = cb.state || 'CLOSED';

        if (dom.cbHealthState) {
          dom.cbHealthState.textContent = cbState;
          dom.cbHealthState.className = cbState === 'CLOSED' ? 'badge badge-info' : 'badge badge-danger';
        }
        if (dom.cbMetricState) dom.cbMetricState.textContent = cbState;
        if (dom.cbMetricFailures) dom.cbMetricFailures.textContent = `${cb.failure_count || 0} / ${cb.failure_threshold || 3}`;
        if (dom.redisMetricStatus) {
          dom.redisMetricStatus.textContent = data.redis_connected ? 'Conectado (Redis)' : 'Fallback Local';
        }

        if (dom.circuitIndicator && dom.circuitIndicatorText) {
          dom.circuitIndicatorText.textContent = `Circuit: ${cbState}`;
          dom.circuitIndicator.className = cbState === 'CLOSED' ? 'status-chip chip-info' : 'status-chip chip-warning';
        }
      }
    } catch {
      // Ignorar degradación sutil
    }

    // 3. Itinerary Service & PostgreSQL Health
    try {
      const res = await fetch('/api/v1/itineraries/health');
      if (res.ok) {
        const data = await res.json();
        if (dom.itineraryHealthStatus) dom.itineraryHealthStatus.textContent = 'OPERATIVO';
        if (dom.dbMetricStatus) dom.dbMetricStatus.textContent = data.database_connected ? 'PostgreSQL Conectada' : 'Falla BD';
        if (dom.outboxMetricStatus) dom.outboxMetricStatus.textContent = data.outbox_worker_active ? 'Activo (Sondeando)' : 'Detenido';
      }
    } catch {
      if (dom.itineraryHealthStatus) dom.itineraryHealthStatus.textContent = 'SIN RESPUESTA';
    }

    // 4. Notification Service & RabbitMQ Health
    try {
      const res = await fetch('/api/v1/notifications/health');
      if (res.ok) {
        const data = await res.json();
        if (dom.notifHealthStatus) dom.notifHealthStatus.textContent = 'FaaS ACTIVO';
        if (dom.amqpMetricStatus) dom.amqpMetricStatus.textContent = data.consumer_active ? 'Escuchando Cola AMQP' : 'Inactivo';
      }
    } catch {
      if (dom.notifHealthStatus) dom.notifHealthStatus.textContent = 'DEGRADADO';
    }

    // 5. Cargar Logs de Notificaciones Serverless
    await loadNotificationsLog();
  }

  async function loadNotificationsLog() {
    try {
      const res = await fetch('/api/v1/notifications/logs');
      if (!res.ok) return;
      const logs = await res.json();
      state.notificationsLog = logs;

      if (dom.notifsMetricTotal) {
        dom.notifsMetricTotal.textContent = `${logs.length} Despachadas`;
      }

      if (!dom.notificationsLogList) return;

      if (logs.length === 0) {
        dom.notificationsLogList.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No se registran eventos de notificación despachados aún.</td></tr>';
        return;
      }

      dom.notificationsLogList.innerHTML = '';
      logs.slice(0, 20).forEach(log => {
        const tr = document.createElement('tr');
        const dateStr = log.sent_at ? new Date(log.sent_at).toLocaleTimeString('es-CO') : '--';

        tr.innerHTML = `
          <td>${dateStr}</td>
          <td class="code-font" style="font-size: 0.72rem;">${String(log.id).slice(0, 8)}...</td>
          <td class="code-font" style="font-size: 0.72rem;">${String(log.event_id || log.itinerary_id).slice(0, 8)}...</td>
          <td><strong>${log.recipient || 'Pasajero'}</strong></td>
          <td><span class="badge badge-accent">${log.channel || 'EMAIL'}</span></td>
          <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${log.message || '--'}</td>
          <td><span class="badge badge-success">${log.status || 'SENT'}</span></td>
        `;
        dom.notificationsLogList.appendChild(tr);
      });

    } catch (e) {
      console.warn('Could not fetch notification logs:', e);
    }
  }

  // Exportar Log de Auditoría
  if (dom.btnExportAuditLog) {
    dom.btnExportAuditLog.addEventListener('click', () => {
      if (state.notificationsLog.length === 0) {
        showToast('Log Vacío', 'No hay registros de auditoría para exportar.', 'info');
        return;
      }
      const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(state.notificationsLog, null, 2));
      const dlAnchor = document.createElement('a');
      dlAnchor.setAttribute('href', dataStr);
      dlAnchor.setAttribute('download', `auditoria_notificaciones_${new Date().toISOString().slice(0, 10)}.json`);
      dlAnchor.click();
      dlAnchor.remove();
      showToast('Auditoría Exportada', 'Log de eventos serverless descargado.', 'success');
    });
  }

  if (dom.btnRefreshMonitoring) {
    dom.btnRefreshMonitoring.addEventListener('click', async () => {
      await checkSystemHealth();
      showToast('Telemetría Actualizada', 'Métricas de salud sincronizadas con el cluster.', 'info');
    });
  }

  if (dom.chkAutoPoll) {
    dom.chkAutoPoll.addEventListener('change', () => {
      if (dom.chkAutoPoll.checked) {
        startHealthPolling();
        showToast('Sondeo Activado', 'Métricas de salud se actualizarán cada 10 segundos.', 'info');
      } else {
        stopHealthPolling();
        showToast('Sondeo Pausado', 'Actualización automática detenida.', 'info');
      }
    });
  }

  function startHealthPolling() {
    stopHealthPolling();
    state.autoPollTimer = setInterval(checkSystemHealth, 10000);
  }

  function stopHealthPolling() {
    if (state.autoPollTimer) {
      clearInterval(state.autoPollTimer);
      state.autoPollTimer = null;
    }
  }

  // Botón Global de Sincronización
  if (dom.btnGlobalRefresh) {
    dom.btnGlobalRefresh.addEventListener('click', async () => {
      showToast('Sincronizando', 'Consultando estado general de la plataforma...', 'info');
      await Promise.allSettled([
        loadAirportsCatalog(),
        loadItineraries(),
        checkSystemHealth()
      ]);
      showToast('Sincronización Completa', 'Todos los microservicios y vistas han sido actualizados.', 'success');
    });
  }

  // ==========================================
  // INICIALIZACIÓN DE LA APLICACIÓN
  // ==========================================
  setDefaultDateTime();
  restoreInitialTab();
  
  // Cargas asíncronas iniciales
  obtainJwtToken().catch(err => console.warn('Initial JWT session warmup postponed:', err));
  loadAirportsCatalog();
  loadItineraries();
  checkSystemHealth();
  startHealthPolling();

  // Escuchar cambio en hash de la URL (atrás/adelante en el navegador)
  window.addEventListener('hashchange', () => {
    restoreInitialTab();
  });
});

const state = {
  me: null,
  users: [],
  projects: [],
  sync: null,
  currentView: 'overview',
  quickFilter: 'all',
  filters: {
    search: '',
    status: '',
    category: '',
    owner: '',
    deadline: '',
    sort: 'deadline',
  },
  editingProject: null,
};

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
const isAdmin = document.body.dataset.isAdmin === 'true';

const els = {
  pageEyebrow: document.getElementById('pageEyebrow'),
  pageTitle: document.getElementById('pageTitle'),
  pageDescription: document.getElementById('pageDescription'),
  navTabs: [...document.querySelectorAll('.nav-tab')],
  viewPanels: [...document.querySelectorAll('[data-view-panel]')],
  navOverviewCount: document.getElementById('navOverviewCount'),
  navProjectsCount: document.getElementById('navProjectsCount'),
  navTimelineCount: document.getElementById('navTimelineCount'),
  navRiskCount: document.getElementById('navRiskCount'),
  overallRing: document.getElementById('overallRing'),
  overallPercent: document.getElementById('overallPercent'),
  healthTitle: document.getElementById('healthTitle'),
  healthSummary: document.getElementById('healthSummary'),
  priorityCount: document.getElementById('priorityCount'),
  priorityList: document.getElementById('priorityList'),
  statsGrid: document.getElementById('statsGrid'),
  categoryChart: document.getElementById('categoryChart'),
  deadlineDonut: document.getElementById('deadlineDonut'),
  deadlineLegend: document.getElementById('deadlineLegend'),
  ownerChart: document.getElementById('ownerChart'),
  deadlineList: document.getElementById('deadlineList'),
  quickFilterBar: document.getElementById('quickFilterBar'),
  projectsGrid: document.getElementById('projectsGrid'),
  emptyState: document.getElementById('emptyState'),
  timelineBoard: document.getElementById('timelineBoard'),
  riskHeroCount: document.getElementById('riskHeroCount'),
  riskGrid: document.getElementById('riskGrid'),
  syncCard: document.getElementById('syncCard'),
  offlineNotice: document.getElementById('offlineNotice'),
  searchInput: document.getElementById('searchInput'),
  statusFilter: document.getElementById('statusFilter'),
  categoryFilter: document.getElementById('categoryFilter'),
  ownerFilter: document.getElementById('ownerFilter'),
  deadlineFilter: document.getElementById('deadlineFilter'),
  sortSelect: document.getElementById('sortSelect'),
  refreshBtn: document.getElementById('refreshBtn'),
  openCreateBtn: document.getElementById('openCreateBtn'),
  reseedBtn: document.getElementById('reseedBtn'),
  toastContainer: document.getElementById('toastContainer'),
  dialog: document.getElementById('projectDialog'),
  form: document.getElementById('projectForm'),
  closeDialogBtn: document.getElementById('closeDialogBtn'),
  cancelDialogBtn: document.getElementById('cancelDialogBtn'),
  dialogTitle: document.getElementById('dialogTitle'),
  dialogEyebrow: document.getElementById('dialogEyebrow'),
  saveProjectBtn: document.getElementById('saveProjectBtn'),
  projectId: document.getElementById('projectId'),
  fieldNome: document.getElementById('fieldNome'),
  fieldProjetoPai: document.getElementById('fieldProjetoPai'),
  fieldUnidade: document.getElementById('fieldUnidade'),
  fieldSetor: document.getElementById('fieldSetor'),
  fieldCategoria: document.getElementById('fieldCategoria'),
  fieldResponsavel: document.getElementById('fieldResponsavel'),
  fieldPrazo: document.getElementById('fieldPrazo'),
  fieldOrdem: document.getElementById('fieldOrdem'),
  fieldProgresso: document.getElementById('fieldProgresso'),
  fieldProgressLabel: document.getElementById('fieldProgressLabel'),
  fieldObs: document.getElementById('fieldObs'),
};

const VIEW_COPY = {
  overview: {
    eyebrow: 'Central OSSEL',
    title: 'Visão executiva',
    description: 'Indicadores vivos de prazo, progresso, entregas e riscos com dados persistentes no GitHub após deploy.',
  },
  projects: {
    eyebrow: 'Operação',
    title: 'Projetos por prioridade',
    description: 'Navegue por abas, filtre por prazo, diferencie categorias e salve progresso diretamente nos cards.',
  },
  timeline: {
    eyebrow: 'Cronograma',
    title: 'Agenda de entregas',
    description: 'Organização por vencimento para enxergar atrasados, próximos prazos, no prazo, sem data e entregues.',
  },
  risks: {
    eyebrow: 'Riscos',
    title: 'Atenção imediata',
    description: 'Projetos vencidos, perto de vencer ou com baixo progresso aparecem destacados para ação rápida.',
  },
};

function text(value, fallback = '') {
  if (value === null || value === undefined || value === '') return fallback;
  return String(value);
}

function createEl(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text !== undefined) node.textContent = options.text;
  if (options.attrs) {
    Object.entries(options.attrs).forEach(([key, value]) => {
      if (value !== false && value !== null && value !== undefined) node.setAttribute(key, value);
    });
  }
  if (options.style) {
    Object.entries(options.style).forEach(([key, value]) => {
      node.style.setProperty(key, value);
    });
  }
  children.forEach((child) => node.append(child));
  return node;
}

async function apiFetch(url, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = {
    Accept: 'application/json',
    ...(options.headers || {}),
  };
  if (method !== 'GET') {
    headers['X-CSRF-Token'] = csrfToken;
  }
  let body = options.body;
  if (body && !(body instanceof FormData) && typeof body !== 'string') {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }
  const response = await fetch(url, {
    ...options,
    method,
    headers,
    body,
  });
  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = { error: await response.text() };
  }
  if (response.status === 401) {
    window.location.href = '/login';
    return null;
  }
  if (!response.ok) {
    const error = new Error(data?.error || 'Erro inesperado.');
    error.payload = data;
    error.status = response.status;
    throw error;
  }
  return data;
}

function toast(message, type = 'success', timeout = 4200) {
  const item = createEl('div', { className: `toast ${type}`, text: message, attrs: { role: 'status' } });
  els.toastContainer.append(item);
  window.setTimeout(() => {
    item.style.opacity = '0';
    item.style.transform = 'translateY(8px)';
    window.setTimeout(() => item.remove(), 220);
  }, timeout);
}

function syncToast(sync) {
  if (!sync) return;
  if (sync.enabled && sync.saved) {
    toast('Salvo no GitHub. Os dados permanecem após deploy.', 'success');
  } else if (!sync.enabled) {
    toast('Salvo apenas localmente. Configure GITHUB_REPO e GITHUB_TOKEN para não perder dados após deploy.', 'warning', 6200);
  }
}

function parseISODate(value) {
  if (!value) return null;
  const raw = String(value).slice(0, 10);
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  if (Number.isNaN(date.getTime())) return null;
  return date;
}

function todayStart() {
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return now;
}

function daysUntil(value) {
  const date = parseISODate(value);
  if (!date) return null;
  return Math.ceil((date.getTime() - todayStart().getTime()) / 86400000);
}

function formatDateTime(value) {
  if (!value) return '';
  try {
    const normalized = String(value).replace('Z', '+00:00');
    const date = new Date(normalized);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  } catch (_error) {
    return String(value);
  }
}

function formatDateBRFromISO(value) {
  const date = parseISODate(value);
  if (!date) return '';
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(date);
}

function dueInfo(project) {
  const progress = Number(project.progresso || 0);
  const status = text(project.status);
  if (status === 'Entregue' || progress >= 100) {
    return {
      key: 'delivered',
      className: 'delivered',
      label: 'Entregue',
      short: 'Entregue',
      priority: 5,
      days: daysUntil(project.prazo),
    };
  }
  const days = daysUntil(project.prazo);
  if (days === null) {
    return {
      key: 'noDate',
      className: 'noDate',
      label: 'Sem prazo',
      short: 'Sem prazo',
      priority: 4,
      days,
    };
  }
  if (days < 0) {
    return {
      key: 'overdue',
      className: 'overdue',
      label: `Vencido há ${Math.abs(days)} dia${Math.abs(days) === 1 ? '' : 's'}`,
      short: 'Atrasado',
      priority: 0,
      days,
    };
  }
  if (days === 0) {
    return {
      key: 'dueToday',
      className: 'dueToday',
      label: 'Vence hoje',
      short: 'Hoje',
      priority: 1,
      days,
    };
  }
  if (days <= 7) {
    return {
      key: 'dueSoon',
      className: 'dueSoon',
      label: `Vence em ${days} dia${days === 1 ? '' : 's'}`,
      short: 'Perto de vencer',
      priority: 2,
      days,
    };
  }
  return {
    key: 'onTime',
    className: 'onTime',
    label: 'No prazo',
    short: 'No prazo',
    priority: 3,
    days,
  };
}

function isCritical(project) {
  const due = dueInfo(project);
  return ['overdue', 'dueToday', 'dueSoon'].includes(due.key);
}

function riskScore(project) {
  const due = dueInfo(project);
  const progress = Number(project.progresso || 0);
  let score = due.priority * 100;
  if (due.key === 'overdue') score += Math.max(0, 60 + Math.abs(due.days || 0));
  if (due.key === 'dueToday') score += 40;
  if (due.key === 'dueSoon') score += 20 - (due.days || 0);
  score += Math.max(0, 100 - progress) / 10;
  return score;
}

function categoryInitials(category) {
  const value = text(category, 'Outros');
  const words = value.split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return words.slice(0, 2).map((word) => word[0]).join('').toUpperCase();
}

function mapCounts(projects, getter) {
  const map = new Map();
  projects.forEach((project) => {
    const key = getter(project) || 'Sem informação';
    map.set(key, (map.get(key) || 0) + 1);
  });
  return [...map.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'pt-BR'));
}

function computeMetrics(projects = state.projects) {
  const total = projects.length;
  const delivered = projects.filter((p) => dueInfo(p).key === 'delivered').length;
  const overdue = projects.filter((p) => dueInfo(p).key === 'overdue').length;
  const dueSoon = projects.filter((p) => ['dueSoon', 'dueToday'].includes(dueInfo(p).key)).length;
  const onTime = projects.filter((p) => dueInfo(p).key === 'onTime').length;
  const noDate = projects.filter((p) => dueInfo(p).key === 'noDate').length;
  const active = Math.max(0, total - delivered);
  const average = total ? Math.round(projects.reduce((sum, p) => sum + Number(p.progresso || 0), 0) / total) : 0;
  const completionRate = total ? Math.round((delivered / total) * 100) : 0;
  return {
    total,
    active,
    delivered,
    overdue,
    dueSoon,
    onTime,
    noDate,
    average,
    completionRate,
    critical: overdue + dueSoon,
  };
}

function setSelectOptions(select, values, firstLabel) {
  if (!select) return;
  const selected = select.value;
  select.replaceChildren(createEl('option', { text: firstLabel, attrs: { value: '' } }));
  values.forEach((value) => {
    select.append(createEl('option', { text: value || 'Sem responsável', attrs: { value } }));
  });
  if ([...select.options].some((option) => option.value === selected)) {
    select.value = selected;
  }
}

function populateFilters() {
  const statuses = [...new Set(state.projects.map((p) => p.status).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  const categories = [...new Set(state.projects.map((p) => p.categoria).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  const owners = [...new Set(state.projects.map((p) => p.assigned_to || '').filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  setSelectOptions(els.statusFilter, statuses, 'Todos');
  setSelectOptions(els.categoryFilter, categories, 'Todas');
  setSelectOptions(els.ownerFilter, owners, 'Todos');
}

function matchesQuickFilter(project, filter = state.quickFilter) {
  const due = dueInfo(project);
  if (filter === 'all') return true;
  if (filter === 'critical') return ['overdue', 'dueToday', 'dueSoon'].includes(due.key);
  if (filter === 'dueSoon') return ['dueToday', 'dueSoon'].includes(due.key);
  if (filter === 'onTime') return due.key === 'onTime';
  if (filter === 'delivered') return due.key === 'delivered';
  if (filter === 'overdue') return due.key === 'overdue';
  if (filter === 'noDate') return due.key === 'noDate';
  return true;
}

function matchesDeadlineFilter(project, filter = state.filters.deadline) {
  if (!filter) return true;
  const due = dueInfo(project);
  if (filter === 'dueSoon') return ['dueToday', 'dueSoon'].includes(due.key);
  if (filter === 'overdue') return due.key === 'overdue';
  if (filter === 'onTime') return due.key === 'onTime';
  if (filter === 'delivered') return due.key === 'delivered';
  if (filter === 'noDate') return due.key === 'noDate';
  return true;
}

function sortProjects(list) {
  const sorted = [...list];
  const getDueTime = (project) => {
    if (dueInfo(project).key === 'delivered') return Number.MAX_SAFE_INTEGER - 1;
    const date = parseISODate(project.prazo);
    return date ? date.getTime() : Number.MAX_SAFE_INTEGER;
  };
  sorted.sort((a, b) => {
    if (state.filters.sort === 'risk') return riskScore(a) - riskScore(b);
    if (state.filters.sort === 'progressAsc') return Number(a.progresso || 0) - Number(b.progresso || 0);
    if (state.filters.sort === 'progressDesc') return Number(b.progresso || 0) - Number(a.progresso || 0);
    if (state.filters.sort === 'owner') return text(a.assigned_to, 'ZZZ').localeCompare(text(b.assigned_to, 'ZZZ'), 'pt-BR') || getDueTime(a) - getDueTime(b);
    if (state.filters.sort === 'category') return text(a.categoria).localeCompare(text(b.categoria), 'pt-BR') || getDueTime(a) - getDueTime(b);
    return getDueTime(a) - getDueTime(b) || Number(a.ordem || 999) - Number(b.ordem || 999) || Number(a.id || 0) - Number(b.id || 0);
  });
  return sorted;
}

function filteredProjects() {
  const query = state.filters.search.trim().toLowerCase();
  const list = state.projects.filter((project) => {
    const haystack = [
      project.nome,
      project.projeto_pai,
      project.unidade,
      project.setor,
      project.categoria,
      project.assigned_to,
      project.obs,
      project.status,
    ].map((value) => text(value).toLowerCase()).join(' ');
    const matchesSearch = !query || haystack.includes(query);
    const matchesStatus = !state.filters.status || project.status === state.filters.status;
    const matchesCategory = !state.filters.category || project.categoria === state.filters.category;
    const matchesOwner = !state.filters.owner || project.assigned_to === state.filters.owner;
    return matchesSearch && matchesStatus && matchesCategory && matchesOwner && matchesDeadlineFilter(project) && matchesQuickFilter(project);
  });
  return sortProjects(list);
}

function updateProgressVisual(container, value) {
  const percent = Math.max(0, Math.min(100, Number(value || 0)));
  const label = container.querySelector('.progress-value');
  const fill = container.querySelector('.progress-fill');
  if (label) label.textContent = `${percent}%`;
  if (fill) fill.style.width = `${percent}%`;
}

function canEdit(project) {
  return Boolean(project?.can_edit);
}

async function patchProject(project, payload) {
  const updated = await apiFetch(`/api/projects/${project.id}`, {
    method: 'PATCH',
    body: payload,
  });
  const index = state.projects.findIndex((item) => item.id === updated.id);
  if (index >= 0) {
    state.projects[index] = updated;
  }
  renderAll();
  syncToast(updated.remote_sync);
  return updated;
}

function metaChip(label, value) {
  return createEl('span', { className: 'meta-chip' }, [
    createEl('small', { text: label }),
    createEl('strong', { text: text(value, 'Não informado') }),
  ]);
}

function renderProjectCard(project) {
  const editable = canEdit(project);
  const due = dueInfo(project);
  const article = createEl('article', {
    className: `project-card ${due.className}`,
    attrs: { 'data-id': project.id },
  });

  const category = text(project.categoria, 'Outros');
  article.append(createEl('div', { className: 'card-topline' }, [
    createEl('span', { className: 'category-pill' }, [
      createEl('span', { className: 'category-icon', text: categoryInitials(category) }),
      createEl('span', { text: category }),
    ]),
    createEl('span', { className: `deadline-badge ${due.className}`, text: due.label }),
  ]));

  article.append(createEl('div', { className: 'card-title-block' }, [
    createEl('h2', { className: 'project-title', text: text(project.nome, 'Projeto sem nome') }),
    createEl('p', { className: 'project-subtitle', text: text(project.projeto_pai || project.unidade || project.setor, 'Sem unidade definida') }),
  ]));

  article.append(createEl('div', { className: 'meta-grid' }, [
    metaChip('Unidade', project.unidade || project.projeto_pai),
    metaChip('Responsável', project.assigned_to || 'Sem responsável'),
    metaChip('Prazo', project.prazo_br || formatDateBRFromISO(project.prazo) || 'Sem prazo'),
    metaChip('Status', project.status || 'Pendente'),
  ]));

  const progressBox = createEl('section', { className: 'progress-box' });
  const progressTop = createEl('div', { className: 'progress-row' }, [
    createEl('small', { text: editable ? 'Arraste para salvar progresso' : 'Progresso' }),
    createEl('strong', { className: 'progress-value', text: `${project.progresso || 0}%` }),
  ]);
  const progressTrack = createEl('div', { className: 'progress-track' }, [createEl('span', { className: 'progress-fill' })]);
  const slider = createEl('input', {
    attrs: {
      type: 'range',
      min: '0',
      max: '100',
      step: '1',
      value: project.progresso || 0,
      'aria-label': `Progresso de ${text(project.nome, 'projeto')}`,
    },
  });
  slider.disabled = !editable;
  progressBox.append(progressTop, progressTrack, slider);
  article.append(progressBox);
  updateProgressVisual(progressBox, project.progresso || 0);

  if (editable) {
    slider.addEventListener('input', () => updateProgressVisual(progressBox, slider.value));
    slider.addEventListener('change', async () => {
      const previous = project.progresso || 0;
      const nextValue = Number(slider.value);
      if (nextValue === previous) return;
      slider.disabled = true;
      toast('Salvando progresso...', 'warning', 1600);
      try {
        await patchProject(project, { progresso: nextValue });
      } catch (error) {
        slider.value = previous;
        updateProgressVisual(progressBox, previous);
        toast(error.payload?.error || error.message || 'Não foi possível salvar o progresso.', 'error', 7200);
      } finally {
        slider.disabled = !editable;
      }
    });
  }

  const notesLabel = createEl('label', {}, [
    createEl('span', { text: 'Observações' }),
    createEl('small', { text: editable ? 'salva ao sair' : 'somente leitura' }),
  ]);
  const notes = createEl('textarea', { attrs: { rows: '4', maxlength: '2000' } });
  notes.value = text(project.obs);
  notes.readOnly = !editable;
  const notesBox = createEl('div', { className: 'card-notes' }, [notesLabel, notes]);
  article.append(notesBox);
  if (editable) {
    notes.dataset.original = notes.value;
    notes.addEventListener('blur', async () => {
      if (notes.value === notes.dataset.original) return;
      notes.disabled = true;
      try {
        await patchProject(project, { obs: notes.value });
        notes.dataset.original = notes.value;
      } catch (error) {
        notes.value = notes.dataset.original;
        toast(error.payload?.error || error.message || 'Não foi possível salvar a observação.', 'error', 7200);
      } finally {
        notes.disabled = false;
      }
    });
  }

  const updatedText = [
    project.updated_at ? `Atualizado: ${formatDateTime(project.updated_at)}` : '',
    project.updated_by ? `por ${project.updated_by}` : '',
  ].filter(Boolean).join(' ');
  const footer = createEl('footer', { className: 'card-footer' });
  footer.append(createEl('div', { className: 'card-updated', text: updatedText || 'Sem atualização registrada' }));
  const actions = createEl('div', { className: 'card-actions' });
  if (editable) {
    const editBtn = createEl('button', { className: 'card-button', text: 'Editar', attrs: { type: 'button' } });
    editBtn.addEventListener('click', () => openProjectDialog(project));
    actions.append(editBtn);
  }
  if (isAdmin) {
    const deleteBtn = createEl('button', { className: 'card-button danger', text: 'Excluir', attrs: { type: 'button' } });
    deleteBtn.addEventListener('click', () => deleteProject(project));
    actions.append(deleteBtn);
  }
  footer.append(actions);
  article.append(footer);
  return article;
}

function renderStats() {
  const m = computeMetrics();
  const cards = [
    ['Total', m.total, `${m.active} ativos no painel`, 'brand'],
    ['Críticos', m.critical, `${m.overdue} atrasados • ${m.dueSoon} perto de vencer`, m.critical ? 'danger' : 'success'],
    ['No prazo', m.onTime, `${m.noDate} sem prazo definido`, 'success'],
    ['Entregues', m.delivered, `${m.completionRate}% de conclusão`, 'brand'],
  ];
  els.statsGrid.replaceChildren(...cards.map(([label, value, detail, tone]) => createEl('article', { className: `stat-card ${tone}` }, [
    createEl('span', { text: label }),
    createEl('strong', { text: String(value) }),
    createEl('p', { text: detail }),
  ])));
}

function renderQuickTabs() {
  const buttons = [...els.quickFilterBar.querySelectorAll('[data-quick-filter]')];
  const counts = {
    all: state.projects.length,
    critical: state.projects.filter((p) => isCritical(p)).length,
    dueSoon: state.projects.filter((p) => ['dueSoon', 'dueToday'].includes(dueInfo(p).key)).length,
    onTime: state.projects.filter((p) => dueInfo(p).key === 'onTime').length,
    delivered: state.projects.filter((p) => dueInfo(p).key === 'delivered').length,
  };
  buttons.forEach((button) => {
    const key = button.dataset.quickFilter;
    button.classList.toggle('active', key === state.quickFilter);
    const count = button.querySelector('strong');
    if (count) count.textContent = String(counts[key] ?? 0);
  });
}

function renderNavBadges() {
  const m = computeMetrics();
  const filtered = filteredProjects().length;
  els.navOverviewCount.textContent = String(m.total);
  els.navProjectsCount.textContent = String(filtered);
  els.navTimelineCount.textContent = String(m.active);
  els.navRiskCount.textContent = String(m.critical);
  const riskTab = els.navTabs.find((tab) => tab.dataset.view === 'risks');
  if (riskTab) riskTab.classList.toggle('attention', m.critical > 0);
}

function renderOverview() {
  const m = computeMetrics();
  els.overallRing.style.setProperty('--percent', m.average);
  els.overallPercent.textContent = `${m.average}%`;
  if (m.critical > 0) {
    els.healthTitle.textContent = `${m.critical} projeto${m.critical === 1 ? '' : 's'} precisam de atenção`;
    els.healthSummary.textContent = `Existem ${m.overdue} atrasado${m.overdue === 1 ? '' : 's'} e ${m.dueSoon} perto de vencer. A aba Riscos mostra a prioridade de ação.`;
  } else if (m.total === 0) {
    els.healthTitle.textContent = 'Nenhum projeto carregado';
    els.healthSummary.textContent = 'Cadastre projetos ou importe a base para visualizar os dashboards.';
  } else {
    els.healthTitle.textContent = 'Portfólio sob controle';
    els.healthSummary.textContent = 'Não há projetos vencidos ou perto de vencer. Continue acompanhando o cronograma e o progresso médio.';
  }
  const priority = sortProjects(state.projects.filter((p) => isCritical(p))).slice(0, 5);
  els.priorityCount.textContent = String(priority.length);
  if (priority.length) {
    els.priorityList.replaceChildren(...priority.map((project) => {
      const due = dueInfo(project);
      return createEl('button', { className: 'priority-item', attrs: { type: 'button' } }, [
        createEl('strong', { text: project.nome }),
        createEl('span', { text: `${due.label} • ${project.progresso || 0}% • ${project.assigned_to || 'sem responsável'}` }),
      ]);
    }));
    [...els.priorityList.querySelectorAll('.priority-item')].forEach((item, index) => {
      item.addEventListener('click', () => {
        state.quickFilter = 'critical';
        switchView('projects');
        const target = priority[index];
        requestAnimationFrame(() => {
          document.querySelector(`[data-id="${target.id}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
      });
    });
  } else {
    els.priorityList.replaceChildren(createEl('div', { className: 'priority-item' }, [
      createEl('strong', { text: 'Nenhuma urgência no momento' }),
      createEl('span', { text: 'Projetos no prazo ou entregues.' }),
    ]));
  }
  renderCategoryChart();
  renderDeadlineDonut();
  renderOwnerChart();
  renderDeadlineList();
}

function renderCategoryChart() {
  const data = mapCounts(state.projects, (p) => p.categoria).slice(0, 8);
  const max = Math.max(1, ...data.map(([, count]) => count));
  if (!data.length) {
    els.categoryChart.replaceChildren(createEl('p', { className: 'empty-positive', text: 'Sem projetos para analisar.' }));
    return;
  }
  els.categoryChart.replaceChildren(...data.map(([label, count]) => createEl('div', { className: 'bar-row' }, [
    createEl('span', { className: 'bar-label', text: label }),
    createEl('span', { className: 'bar-track' }, [createEl('span', { className: 'bar-fill', style: { width: `${Math.max(8, (count / max) * 100)}%` } })]),
    createEl('strong', { className: 'bar-count', text: String(count) }),
  ])));
}

function renderDeadlineDonut() {
  const m = computeMetrics();
  const total = Math.max(1, m.total);
  const dangerDeg = (m.overdue / total) * 360;
  const warningDeg = (m.dueSoon / total) * 360;
  const successDeg = (m.onTime / total) * 360;
  els.deadlineDonut.style.setProperty('--danger-part', `${dangerDeg}deg`);
  els.deadlineDonut.style.setProperty('--warning-part', `${warningDeg}deg`);
  els.deadlineDonut.style.setProperty('--success-part', `${successDeg}deg`);
  els.deadlineDonut.querySelector('span').textContent = `${m.total}`;
  const legend = [
    ['Atrasados', m.overdue, 'overdue'],
    ['Perto de vencer', m.dueSoon, 'dueSoon'],
    ['No prazo', m.onTime, 'onTime'],
    ['Entregues/sem prazo', m.delivered + m.noDate, 'delivered'],
  ];
  els.deadlineLegend.replaceChildren(...legend.map(([label, count, cls]) => createEl('div', { className: 'legend-item' }, [
    createEl('span', {}, [createEl('i', { className: `legend-dot ${cls}` }), createEl('span', { text: label })]),
    createEl('strong', { text: String(count) }),
  ])));
}

function renderOwnerChart() {
  const data = mapCounts(state.projects, (p) => p.assigned_to || 'Sem responsável').slice(0, 8);
  const max = Math.max(1, ...data.map(([, count]) => count));
  if (!data.length) {
    els.ownerChart.replaceChildren(createEl('p', { className: 'empty-positive', text: 'Sem responsáveis para exibir.' }));
    return;
  }
  els.ownerChart.replaceChildren(...data.map(([label, count]) => createEl('div', { className: 'owner-row' }, [
    createEl('span', { className: 'owner-name', text: label }),
    createEl('span', { className: 'owner-track' }, [createEl('span', { className: 'owner-fill', style: { width: `${Math.max(8, (count / max) * 100)}%` } })]),
    createEl('strong', { className: 'owner-count', text: String(count) }),
  ])));
}

function renderDeadlineList() {
  const upcoming = sortProjects(state.projects.filter((p) => !['delivered', 'noDate'].includes(dueInfo(p).key))).slice(0, 6);
  if (!upcoming.length) {
    els.deadlineList.replaceChildren(createEl('p', { className: 'empty-positive', text: 'Nenhum vencimento ativo encontrado.' }));
    return;
  }
  els.deadlineList.replaceChildren(...upcoming.map((project) => {
    const due = dueInfo(project);
    return createEl('div', { className: 'deadline-item' }, [
      createEl('span', { className: `deadline-dot ${due.className}` }),
      createEl('span', {}, [
        createEl('strong', { text: project.nome }),
        createEl('small', { text: `${project.assigned_to || 'Sem responsável'} • ${project.progresso || 0}%` }),
      ]),
      createEl('strong', { text: due.label }),
    ]);
  }));
}

function renderProjects() {
  const list = filteredProjects();
  els.projectsGrid.replaceChildren(...list.map(renderProjectCard));
  els.emptyState.classList.toggle('hidden', list.length > 0);
}

function timelineItem(project) {
  const due = dueInfo(project);
  return createEl('div', { className: `timeline-item ${due.className}` }, [
    createEl('div', { className: 'timeline-item-title' }, [
      createEl('strong', { text: project.nome }),
      createEl('small', { text: `${project.categoria || 'Outros'} • ${project.assigned_to || 'Sem responsável'} • ${project.unidade || 'Sem unidade'}` }),
    ]),
    createEl('span', { className: `deadline-badge ${due.className}`, text: due.label }),
    createEl('div', {}, [
      createEl('div', { className: 'timeline-mini-progress' }, [createEl('span', { style: { width: `${Number(project.progresso || 0)}%` } })]),
      createEl('small', { className: 'timeline-date', text: project.prazo_br || formatDateBRFromISO(project.prazo) || 'Sem prazo' }),
    ]),
  ]);
}

function renderTimeline() {
  const groups = [
    ['overdue', 'Atrasados', (p) => dueInfo(p).key === 'overdue'],
    ['dueSoon', 'Vence hoje ou em até 7 dias', (p) => ['dueToday', 'dueSoon'].includes(dueInfo(p).key)],
    ['onTime', 'No prazo', (p) => dueInfo(p).key === 'onTime'],
    ['noDate', 'Sem prazo definido', (p) => dueInfo(p).key === 'noDate'],
    ['delivered', 'Entregues', (p) => dueInfo(p).key === 'delivered'],
  ];
  const blocks = groups.map(([key, title, fn]) => {
    const items = sortProjects(state.projects.filter(fn));
    if (!items.length) return null;
    return createEl('section', { className: `timeline-group ${key}` }, [
      createEl('header', {}, [createEl('h3', { text: title }), createEl('strong', { text: String(items.length) })]),
      createEl('div', { className: 'timeline-items' }, items.map(timelineItem)),
    ]);
  }).filter(Boolean);
  if (!blocks.length) {
    els.timelineBoard.replaceChildren(createEl('div', { className: 'empty-positive', text: 'Nenhum projeto no cronograma.' }));
    return;
  }
  els.timelineBoard.replaceChildren(...blocks);
}

function riskReason(project) {
  const due = dueInfo(project);
  const progress = Number(project.progresso || 0);
  if (due.key === 'overdue') return 'Vencido e ainda não entregue.';
  if (due.key === 'dueToday') return 'Vence hoje. Priorize validação e conclusão.';
  if (due.key === 'dueSoon' && progress < 70) return 'Perto do prazo com progresso abaixo de 70%.';
  if (due.key === 'dueSoon') return 'Perto de vencer. Acompanhe de perto.';
  if (due.key === 'onTime' && due.days <= 14 && progress < 50) return 'Prazo próximo e progresso baixo.';
  return 'Necessita acompanhamento.';
}

function riskList() {
  const items = state.projects.filter((project) => {
    const due = dueInfo(project);
    const progress = Number(project.progresso || 0);
    return ['overdue', 'dueToday', 'dueSoon'].includes(due.key) || (due.key === 'onTime' && due.days <= 14 && progress < 50);
  });
  return sortProjects(items).sort((a, b) => riskScore(a) - riskScore(b));
}

function renderRisks() {
  const items = riskList();
  els.riskHeroCount.textContent = String(items.length);
  if (!items.length) {
    els.riskGrid.replaceChildren(createEl('div', { className: 'empty-positive', text: 'Nenhum projeto crítico no momento. Continue acompanhando o cronograma.' }));
    return;
  }
  els.riskGrid.replaceChildren(...items.map((project) => {
    const due = dueInfo(project);
    return createEl('article', { className: `risk-card ${due.className}` }, [
      createEl('span', { className: `deadline-badge ${due.className}`, text: due.label }),
      createEl('h3', { text: project.nome }),
      createEl('p', { text: riskReason(project) }),
      createEl('div', { className: 'risk-meta' }, [
        createEl('span', { text: `${project.progresso || 0}% concluído` }),
        createEl('span', { text: project.assigned_to || 'Sem responsável' }),
        createEl('span', { text: project.prazo_br || formatDateBRFromISO(project.prazo) || 'Sem prazo' }),
      ]),
    ]);
  }));
}

function renderSyncStatus() {
  const sync = state.sync;
  els.syncCard.classList.remove('ok', 'warn', 'error');
  const title = els.syncCard.querySelector('strong');
  const details = els.syncCard.querySelector('small');
  els.offlineNotice.classList.add('hidden');
  els.offlineNotice.textContent = '';

  if (!sync) {
    title.textContent = 'Persistência não verificada';
    details.textContent = 'Aguardando status';
    els.syncCard.classList.add('warn');
    return;
  }

  if (sync.enabled && !sync.error) {
    title.textContent = 'GitHub ativo';
    details.textContent = `${sync.data_path}${sync.updated_at ? ` • ${formatDateTime(sync.updated_at)}` : ''}`;
    els.syncCard.classList.add('ok');
    return;
  }

  title.textContent = sync.enabled ? 'Atenção no GitHub' : 'GitHub desativado';
  details.textContent = sync.message || 'Configure as variáveis de ambiente';
  els.syncCard.classList.add(sync.enabled ? 'error' : 'warn');
  els.offlineNotice.textContent = sync.enabled
    ? `Persistência remota com erro: ${sync.message || 'verifique GITHUB_TOKEN, GITHUB_REPO e permissões.'}`
    : 'Atenção: GITHUB_REPO e GITHUB_TOKEN não estão configurados. O painel funciona, mas alterações podem ser perdidas em um novo deploy no Render Free.';
  els.offlineNotice.classList.remove('hidden');
}

function updatePageCopy() {
  const copy = VIEW_COPY[state.currentView] || VIEW_COPY.overview;
  els.pageEyebrow.textContent = copy.eyebrow;
  els.pageTitle.textContent = copy.title;
  els.pageDescription.textContent = copy.description;
  els.navTabs.forEach((tab) => tab.classList.toggle('active', tab.dataset.view === state.currentView));
  els.viewPanels.forEach((panel) => panel.classList.toggle('active', panel.dataset.viewPanel === state.currentView));
}

function renderAll() {
  populateFilters();
  renderSyncStatus();
  renderStats();
  renderOverview();
  renderQuickTabs();
  renderProjects();
  renderTimeline();
  renderRisks();
  renderNavBadges();
  updatePageCopy();
}

async function loadData(showSuccess = false) {
  els.refreshBtn.disabled = true;
  try {
    const [me, users, projects, sync] = await Promise.all([
      apiFetch('/api/me'),
      apiFetch('/api/users'),
      apiFetch('/api/projects'),
      apiFetch('/api/sync-status'),
    ]);
    state.me = me;
    state.users = users || [];
    state.projects = projects || [];
    state.sync = sync;
    renderAll();
    if (showSuccess) toast('Painel atualizado.', 'success');
  } catch (error) {
    toast(error.payload?.error || error.message || 'Não foi possível carregar o painel.', 'error', 7200);
  } finally {
    els.refreshBtn.disabled = false;
  }
}

function populateResponsibleSelect() {
  els.fieldResponsavel.replaceChildren(createEl('option', { text: 'Sem responsável', attrs: { value: '' } }));
  state.users.forEach((user) => {
    els.fieldResponsavel.append(createEl('option', { text: user.display_name || user.username, attrs: { value: user.display_name || user.username } }));
  });
}

function setAdminFieldsVisible(visible) {
  document.querySelectorAll('.admin-field').forEach((field) => {
    field.classList.toggle('hidden', !visible);
  });
}

function openProjectDialog(project = null) {
  state.editingProject = project;
  const creating = !project;
  populateResponsibleSelect();
  setAdminFieldsVisible(isAdmin);

  els.dialogTitle.textContent = creating ? 'Novo projeto' : 'Editar projeto';
  els.dialogEyebrow.textContent = creating ? 'Cadastro' : `Projeto #${project.id}`;
  els.saveProjectBtn.textContent = creating ? 'Criar projeto' : 'Salvar alterações';
  els.projectId.value = project?.id || '';
  els.fieldNome.value = project?.nome || '';
  els.fieldProjetoPai.value = project?.projeto_pai || '';
  els.fieldUnidade.value = project?.unidade || '';
  els.fieldSetor.value = project?.setor || '';
  els.fieldCategoria.value = project?.categoria || 'Troca de Máquinas';
  els.fieldResponsavel.value = project?.assigned_to || '';
  els.fieldPrazo.value = project?.prazo || '';
  els.fieldOrdem.value = project?.ordem || 999;
  els.fieldProgresso.value = project?.progresso || 0;
  els.fieldProgressLabel.textContent = `${els.fieldProgresso.value}%`;
  els.fieldObs.value = project?.obs || '';

  if (!isAdmin && creating) {
    toast('Apenas administradores podem criar projetos.', 'error');
    return;
  }

  if (els.dialog.showModal) {
    els.dialog.showModal();
  } else {
    els.dialog.setAttribute('open', 'open');
  }
}

function closeProjectDialog() {
  state.editingProject = null;
  els.form.reset();
  if (els.dialog.open) els.dialog.close();
}

async function saveProjectFromDialog(event) {
  event.preventDefault();
  const project = state.editingProject;
  const creating = !project;
  if (creating && !isAdmin) return;

  const payload = isAdmin ? {
    nome: els.fieldNome.value,
    projeto_pai: els.fieldProjetoPai.value,
    unidade: els.fieldUnidade.value,
    setor: els.fieldSetor.value,
    categoria: els.fieldCategoria.value,
    assigned_to: els.fieldResponsavel.value,
    prazo: els.fieldPrazo.value,
    ordem: els.fieldOrdem.value,
    progresso: els.fieldProgresso.value,
    obs: els.fieldObs.value,
  } : {
    progresso: els.fieldProgresso.value,
    obs: els.fieldObs.value,
  };

  els.saveProjectBtn.disabled = true;
  const originalText = els.saveProjectBtn.textContent;
  els.saveProjectBtn.textContent = 'Salvando...';
  try {
    if (creating) {
      const created = await apiFetch('/api/projects', { method: 'POST', body: payload });
      state.projects.push(created);
      syncToast(created.remote_sync);
      toast('Projeto criado com sucesso.', 'success');
    } else {
      await patchProject(project, payload);
    }
    closeProjectDialog();
    await loadData(false);
  } catch (error) {
    toast(error.payload?.error || error.message || 'Não foi possível salvar o projeto.', 'error', 7800);
  } finally {
    els.saveProjectBtn.disabled = false;
    els.saveProjectBtn.textContent = originalText;
  }
}

async function deleteProject(project) {
  const confirmed = window.confirm(`Excluir o projeto "${project.nome}"? Essa ação só será concluída se o backup no GitHub também for salvo.`);
  if (!confirmed) return;
  try {
    const result = await apiFetch(`/api/projects/${project.id}`, { method: 'DELETE' });
    state.projects = state.projects.filter((item) => item.id !== project.id);
    renderAll();
    syncToast(result.remote_sync);
    toast('Projeto excluído.', 'success');
  } catch (error) {
    toast(error.payload?.error || error.message || 'Não foi possível excluir o projeto.', 'error', 7800);
  }
}

async function reseed() {
  const first = window.confirm('Importar a base do data/seed.json? Isso substitui os projetos atuais e só conclui se o backup no GitHub for salvo.');
  if (!first) return;
  const confirmation = window.prompt('Digite IMPORTAR_BASE_COMPLETA para confirmar:');
  if (confirmation !== 'IMPORTAR_BASE_COMPLETA') {
    toast('Importação cancelada.', 'warning');
    return;
  }
  els.reseedBtn.disabled = true;
  try {
    const result = await apiFetch('/api/admin/reseed', {
      method: 'POST',
      body: { confirm: confirmation },
    });
    syncToast(result.remote_sync);
    toast(`Base importada com ${result.total} projeto(s).`, 'success');
    await loadData(false);
  } catch (error) {
    toast(error.payload?.error || error.message || 'Não foi possível importar a base.', 'error', 8000);
  } finally {
    els.reseedBtn.disabled = false;
  }
}

function switchView(view) {
  state.currentView = view || 'overview';
  updatePageCopy();
  if (view === 'projects') renderProjects();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function setQuickFilter(filter) {
  state.quickFilter = filter || 'all';
  renderQuickTabs();
  renderProjects();
  renderNavBadges();
}

function bindEvents() {
  els.refreshBtn.addEventListener('click', () => loadData(true));
  els.navTabs.forEach((tab) => {
    tab.addEventListener('click', () => switchView(tab.dataset.view));
  });
  document.querySelectorAll('[data-jump-view]').forEach((button) => {
    button.addEventListener('click', () => {
      const filter = button.dataset.quickFilter;
      if (filter) setQuickFilter(filter);
      switchView(button.dataset.jumpView);
    });
  });
  els.quickFilterBar.querySelectorAll('[data-quick-filter]').forEach((button) => {
    button.addEventListener('click', () => {
      setQuickFilter(button.dataset.quickFilter);
      switchView('projects');
    });
  });
  els.searchInput.addEventListener('input', () => {
    state.filters.search = els.searchInput.value;
    renderProjects();
    renderNavBadges();
  });
  els.statusFilter.addEventListener('change', () => {
    state.filters.status = els.statusFilter.value;
    renderProjects();
    renderNavBadges();
  });
  els.categoryFilter.addEventListener('change', () => {
    state.filters.category = els.categoryFilter.value;
    renderProjects();
    renderNavBadges();
  });
  els.ownerFilter.addEventListener('change', () => {
    state.filters.owner = els.ownerFilter.value;
    renderProjects();
    renderNavBadges();
  });
  els.deadlineFilter.addEventListener('change', () => {
    state.filters.deadline = els.deadlineFilter.value;
    renderProjects();
    renderNavBadges();
  });
  els.sortSelect.addEventListener('change', () => {
    state.filters.sort = els.sortSelect.value;
    renderProjects();
  });
  els.openCreateBtn?.addEventListener('click', () => openProjectDialog(null));
  els.reseedBtn?.addEventListener('click', reseed);
  els.closeDialogBtn.addEventListener('click', closeProjectDialog);
  els.cancelDialogBtn.addEventListener('click', closeProjectDialog);
  els.form.addEventListener('submit', saveProjectFromDialog);
  els.fieldProgresso.addEventListener('input', () => {
    els.fieldProgressLabel.textContent = `${els.fieldProgresso.value}%`;
  });
  els.dialog.addEventListener('click', (event) => {
    const rect = els.dialog.getBoundingClientRect();
    const clickedOutside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
    if (clickedOutside) closeProjectDialog();
  });
}

bindEvents();
loadData(false);

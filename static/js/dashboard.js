const state = {
  me: null,
  users: [],
  projects: [],
  sync: null,
  filters: {
    search: '',
    status: '',
    category: '',
    owner: '',
  },
  editingProject: null,
};

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
const isAdmin = document.body.dataset.isAdmin === 'true';

const els = {
  statsGrid: document.getElementById('statsGrid'),
  projectsGrid: document.getElementById('projectsGrid'),
  emptyState: document.getElementById('emptyState'),
  syncCard: document.getElementById('syncCard'),
  offlineNotice: document.getElementById('offlineNotice'),
  searchInput: document.getElementById('searchInput'),
  statusFilter: document.getElementById('statusFilter'),
  categoryFilter: document.getElementById('categoryFilter'),
  ownerFilter: document.getElementById('ownerFilter'),
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

function statusClass(status) {
  if (status === 'Entregue') return 'done';
  if (status === 'Em andamento') return 'progress';
  return 'pending';
}

function canEdit(project) {
  return Boolean(project?.can_edit);
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

function setSelectOptions(select, values, firstLabel) {
  const selected = select.value;
  select.replaceChildren(createEl('option', { text: firstLabel, attrs: { value: '' } }));
  values.forEach((value) => {
    const option = createEl('option', { text: value || 'Sem responsável', attrs: { value } });
    select.append(option);
  });
  if ([...select.options].some((option) => option.value === selected)) {
    select.value = selected;
  }
}

function populateFilters() {
  const statuses = [...new Set(state.projects.map((p) => p.status).filter(Boolean))].sort();
  const categories = [...new Set(state.projects.map((p) => p.categoria).filter(Boolean))].sort();
  const owners = [...new Set(state.projects.map((p) => p.assigned_to || '').filter(Boolean))].sort();
  setSelectOptions(els.statusFilter, statuses, 'Todos');
  setSelectOptions(els.categoryFilter, categories, 'Todas');
  setSelectOptions(els.ownerFilter, owners, 'Todos');
}

function renderStats() {
  const total = state.projects.length;
  const done = state.projects.filter((p) => p.status === 'Entregue').length;
  const progress = state.projects.filter((p) => p.status === 'Em andamento').length;
  const average = total ? Math.round(state.projects.reduce((sum, p) => sum + Number(p.progresso || 0), 0) / total) : 0;
  const cards = [
    ['Total', total],
    ['Em andamento', progress],
    ['Entregues', done],
    ['Progresso médio', `${average}%`],
  ];
  els.statsGrid.replaceChildren(...cards.map(([label, value]) => createEl('article', { className: 'stat-card' }, [
    createEl('span', { text: label }),
    createEl('strong', { text: String(value) }),
  ])));
}

function filteredProjects() {
  const query = state.filters.search.trim().toLowerCase();
  return state.projects.filter((project) => {
    const haystack = [
      project.nome,
      project.projeto_pai,
      project.unidade,
      project.setor,
      project.categoria,
      project.assigned_to,
      project.obs,
    ].map((value) => text(value).toLowerCase()).join(' ');
    const matchesSearch = !query || haystack.includes(query);
    const matchesStatus = !state.filters.status || project.status === state.filters.status;
    const matchesCategory = !state.filters.category || project.categoria === state.filters.category;
    const matchesOwner = !state.filters.owner || project.assigned_to === state.filters.owner;
    return matchesSearch && matchesStatus && matchesCategory && matchesOwner;
  });
}

function updateProgressVisual(container, value) {
  const percent = Math.max(0, Math.min(100, Number(value || 0)));
  const label = container.querySelector('.progress-value');
  const fill = container.querySelector('.progress-fill');
  if (label) label.textContent = `${percent}%`;
  if (fill) fill.style.width = `${percent}%`;
}

async function patchProject(project, payload, options = {}) {
  const updated = await apiFetch(`/api/projects/${project.id}`, {
    method: 'PATCH',
    body: payload,
  });
  const index = state.projects.findIndex((item) => item.id === updated.id);
  if (index >= 0) {
    state.projects[index] = updated;
  }
  renderAll({ keepFilters: true });
  syncToast(updated.remote_sync);
  return updated;
}

function renderProjectCard(project) {
  const editable = canEdit(project);
  const article = createEl('article', { className: 'project-card', attrs: { 'data-id': project.id } });

  const titleBlock = createEl('div', {}, [
    createEl('h2', { className: 'project-title', text: text(project.nome, 'Projeto sem nome') }),
    createEl('p', { className: 'project-subtitle', text: text(project.projeto_pai || project.unidade || project.setor, 'Sem unidade definida') }),
  ]);
  const badge = createEl('span', { className: `badge ${statusClass(project.status)}`, text: text(project.status, 'Pendente') });
  article.append(createEl('header', { className: 'card-head' }, [titleBlock, badge]));

  const chips = [
    project.unidade,
    project.categoria,
    project.assigned_to ? `Resp.: ${project.assigned_to}` : 'Sem responsável',
    project.prazo_br ? `Prazo: ${project.prazo_br}` : '',
  ].filter(Boolean).map((value) => createEl('span', { className: 'meta-chip', text: value }));
  article.append(createEl('div', { className: 'meta-grid' }, chips));

  const progressBox = createEl('section', { className: 'progress-box' });
  const progressTop = createEl('div', { className: 'progress-row' }, [
    createEl('small', { text: editable ? 'Arraste para salvar progresso' : 'Progresso' }),
    createEl('strong', { className: 'progress-value', text: `${project.progresso || 0}%` }),
  ]);
  const progressTrack = createEl('div', { className: 'progress-track' }, [
    createEl('span', { className: 'progress-fill' }),
  ]);
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

  const notesLabel = createEl('label', { text: 'Observações' });
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

function renderProjects() {
  const list = filteredProjects();
  els.projectsGrid.replaceChildren(...list.map(renderProjectCard));
  els.emptyState.classList.toggle('hidden', list.length > 0);
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

function renderAll() {
  populateFilters();
  renderStats();
  renderSyncStatus();
  renderProjects();
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

function bindEvents() {
  els.refreshBtn.addEventListener('click', () => loadData(true));
  els.searchInput.addEventListener('input', () => {
    state.filters.search = els.searchInput.value;
    renderProjects();
  });
  els.statusFilter.addEventListener('change', () => {
    state.filters.status = els.statusFilter.value;
    renderProjects();
  });
  els.categoryFilter.addEventListener('change', () => {
    state.filters.category = els.categoryFilter.value;
    renderProjects();
  });
  els.ownerFilter.addEventListener('change', () => {
    state.filters.owner = els.ownerFilter.value;
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

(() => {
    'use strict';

    const chat = document.querySelector('[data-chat]');
    if (!chat || chat.dataset.atualizar !== 'true' || !window.fetch ||
        !window.FormData || !window.AbortController || !window.crypto?.getRandomValues) return;

    const historico = chat.querySelector('[data-chat-historico]');
    const form = chat.querySelector('[data-chat-form]');
    const readForm = chat.querySelector('[data-chat-read-form]');
    const status = chat.querySelector('[data-chat-status]');
    const envioStatus = chat.querySelector('[data-chat-envio-status]');
    const novas = chat.querySelector('[data-chat-novas]');
    const texto = form?.elements.namedItem('texto');
    const clienteId = form?.elements.namedItem('cliente_id');
    const ultimaVisivel = form?.elements.namedItem('ultima_visivel');
    const enviar = chat.querySelector('[data-chat-enviar]');
    const composicao = chat.querySelector('[data-chat-composicao]');
    const indisponivel = chat.querySelector('[data-chat-indisponivel]');
    const csrf = form?.elements.namedItem('csrfmiddlewaretoken')?.value;
    if (!historico || !form || !readForm || !texto || !clienteId || !csrf) return;

    let cursor = Number(chat.dataset.ultimoId) || 0;
    // Only a fully fetched range may be marked as read. A POST response can
    // arrive before older messages sent by the other participant are fetched.
    let cursorLegivel = cursor;
    let ultimoMarcado = 0;
    let lendo = false;
    let lerDepoisDe = 0;
    let buscando = false;
    let enviando = false;
    let encerrado = false;
    let podeEnviar = chat.dataset.podeEnviar === 'true';
    let tentativaTexto = null;
    let falhas = 0;
    let timer = null;
    const ids = new Set(Array.from(historico.querySelectorAll('[data-mensagem-id]'), el => Number(el.dataset.mensagemId)));

    function uuid() {
        if (window.crypto.randomUUID) return window.crypto.randomUUID();
        const bytes = window.crypto.getRandomValues(new Uint8Array(16));
        bytes[6] = (bytes[6] & 15) | 64;
        bytes[8] = (bytes[8] & 63) | 128;
        const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }

    function pertoDoFim() {
        return historico.scrollHeight - historico.scrollTop - historico.clientHeight < 85;
    }

    function mostrarStatus(mensagem, erro = false) {
        status.textContent = mensagem;
        status.classList.toggle('chat-status--erro', erro);
    }

    function mostrarEnvio(mensagem, erro = false) {
        envioStatus.textContent = mensagem;
        envioStatus.hidden = !mensagem;
        envioStatus.classList.toggle('chat-status--erro', erro);
    }

    function atualizarComposicao(permitido) {
        podeEnviar = permitido;
        composicao.disabled = !permitido || encerrado;
        enviar.disabled = enviando || !permitido || encerrado;
        indisponivel.hidden = permitido || encerrado;
    }

    function encerrar(codigo) {
        encerrado = true;
        clearTimeout(timer);
        atualizarComposicao(false);
        const mensagem = codigo === 401 ? 'Sua sessão expirou. Entre novamente para continuar.' :
            'Esta conversa está indisponível. Suas mensagens ainda não enviadas foram mantidas neste campo.';
        mostrarStatus(mensagem, true);
        const link = document.createElement('a');
        link.className = 'ajuda-link';
        link.href = window.location.pathname;
        link.textContent = ' Atualizar a conversa';
        status.append(link);
    }

    async function requisitar(url, options = {}) {
        const controller = new AbortController();
        const limite = setTimeout(() => controller.abort(), 18000);
        try {
            const response = await fetch(url, {
                ...options,
                credentials: 'same-origin',
                cache: 'no-store',
                headers: { Accept: 'application/json', 'X-CSRFToken': csrf },
                signal: controller.signal,
            });
            const json = response.headers.get('content-type')?.includes('application/json');
            const data = json ? await response.json() : null;
            if (!response.ok || !data) {
                const error = new Error(data?.erro || 'Não foi possível conectar. Tente novamente.');
                error.status = response.status;
                throw error;
            }
            return data;
        } finally {
            clearTimeout(limite);
        }
    }

    function adicionar(mensagem) {
        const id = Number(mensagem.id);
        if (!Number.isSafeInteger(id) || id <= 0 || ids.has(id)) return false;
        const balao = document.createElement('article');
        balao.className = `chat-mensagem${mensagem.minha ? ' chat-mensagem--minha' : ''}`;
        balao.dataset.mensagemId = String(id);
        const autor = document.createElement('strong');
        autor.className = 'chat-mensagem__autor';
        autor.textContent = mensagem.minha ? 'Você' : mensagem.autor;
        const conteudo = document.createElement('p');
        conteudo.className = 'chat-mensagem__texto';
        conteudo.textContent = mensagem.texto;
        const horario = document.createElement('time');
        horario.dateTime = mensagem.criado_em;
        horario.textContent = mensagem.horario;
        balao.append(autor, conteudo, horario);
        const posterior = Array.from(historico.querySelectorAll('[data-mensagem-id]'))
            .find(el => Number(el.dataset.mensagemId) > id);
        historico.querySelector('[data-chat-vazio]')?.remove();
        historico.insertBefore(balao, posterior || null);
        ids.add(id);
        return true;
    }

    async function marcarLidas() {
        if (encerrado || lendo || document.hidden || !pertoDoFim() ||
            cursorLegivel <= ultimoMarcado || Date.now() < lerDepoisDe) return;
        const limiteLido = cursorLegivel;
        const dados = new FormData(readForm);
        dados.set('ultimo_id', String(limiteLido));
        lendo = true;
        try {
            await requisitar(chat.dataset.lidasUrl, { method: 'POST', body: dados });
            ultimoMarcado = limiteLido;
            lerDepoisDe = 0;
        } catch (error) {
            if ([401, 403, 404].includes(error.status)) encerrar(error.status);
            else lerDepoisDe = Date.now() + 16000;
        } finally {
            lendo = false;
        }
    }

    function irParaFim() {
        historico.scrollTop = historico.scrollHeight;
        novas.hidden = true;
        marcarLidas();
    }

    function agendar(delay = 8000) {
        clearTimeout(timer);
        if (!encerrado && !document.hidden) timer = setTimeout(buscar, delay);
    }

    async function buscar() {
        if (buscando || encerrado || document.hidden) return;
        buscando = true;
        let temMais = false;
        try {
            for (let lote = 0; lote < 5; lote += 1) {
                if (document.hidden || encerrado) break;
                const url = new URL(chat.dataset.mensagensUrl, window.location.origin);
                url.searchParams.set('apos', String(cursor));
                const data = await requisitar(url);
                const acompanhar = pertoDoFim();
                let recebidas = 0;
                for (const mensagem of data.mensagens) {
                    if (adicionar(mensagem)) recebidas += 1;
                }
                const proxima = Number(data.proxima);
                if (!Number.isSafeInteger(proxima) || proxima < cursor) throw new Error('Resposta inválida.');
                cursor = proxima;
                temMais = Boolean(data.tem_mais);
                atualizarComposicao(Boolean(data.pode_enviar));
                if (!temMais) {
                    cursorLegivel = cursor;
                    ultimaVisivel.value = String(cursorLegivel);
                }
                if (recebidas) {
                    if (acompanhar) irParaFim();
                    else novas.hidden = false;
                }
                if (!temMais) break;
            }
            falhas = 0;
            if (!encerrado) mostrarStatus('A conversa é atualizada automaticamente enquanto esta página está aberta.');
            if (!temMais) marcarLidas();
        } catch (error) {
            if ([401, 403, 404].includes(error.status)) encerrar(error.status);
            else {
                falhas += 1;
                mostrarStatus(error.status === 429 ? 'Muitas atualizações. Vamos tentar novamente em instantes.' :
                    'A conexão foi interrompida. Tentaremos atualizar a conversa novamente.', true);
            }
        } finally {
            buscando = false;
            agendar(falhas ? Math.min(60000, 8000 * (2 ** falhas)) : temMais ? 250 : 8000);
        }
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (enviando || encerrado || !podeEnviar || !form.reportValidity()) return;
        const rascunho = texto.value;
        if (!rascunho.trim()) {
            mostrarEnvio('Escreva uma mensagem antes de enviar.', true);
            texto.focus();
            return;
        }
        // Retry the same draft with the same idempotency key after a timeout.
        if (tentativaTexto !== null && tentativaTexto !== rascunho) clienteId.value = uuid();
        tentativaTexto = rascunho;
        const dados = new FormData(form);
        dados.set('ultima_visivel', String(cursorLegivel));
        enviando = true;
        enviar.disabled = true;
        enviar.textContent = 'Enviando…';
        mostrarEnvio('Enviando sua mensagem…');
        try {
            const data = await requisitar(form.action, { method: 'POST', body: dados });
            adicionar(data.mensagem);
            if (texto.value === rascunho) texto.value = '';
            clienteId.value = uuid();
            tentativaTexto = null;
            mostrarEnvio('Mensagem enviada.');
            irParaFim();
            // Do not advance the fetch/read cursor to our own message ID.
            // Polling must first fetch every preceding incoming message.
            agendar(0);
        } catch (error) {
            if ([401, 404].includes(error.status)) encerrar(error.status);
            if (error.status === 403) atualizarComposicao(false);
            const detalhe = [400, 403, 429].includes(error.status) ? `${error.message} ` : '';
            mostrarEnvio(`${detalhe}A mensagem foi mantida. Tente enviá-la novamente quando a conexão estiver disponível.`, true);
        } finally {
            enviando = false;
            enviar.textContent = 'Enviar mensagem →';
            enviar.disabled = !podeEnviar || encerrado;
        }
    });

    texto.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
            event.preventDefault();
            form.requestSubmit();
        }
    });
    novas.addEventListener('click', irParaFim);
    historico.addEventListener('scroll', () => {
        if (pertoDoFim()) {
            novas.hidden = true;
            marcarLidas();
        }
    }, { passive: true });
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) clearTimeout(timer);
        else {
            marcarLidas();
            agendar(0);
        }
    });
    window.addEventListener('online', () => agendar(0));
    readForm.hidden = true;
    irParaFim();
    agendar(0);
})();

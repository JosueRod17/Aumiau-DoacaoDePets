(() => {
    const painel = document.querySelector('[data-pluttu]');
    if (!painel || !window.fetch) return;
    const historico = painel.querySelector('[data-pluttu-historico]');
    const erro = painel.querySelector('[data-pluttu-erro]');
    const formulario = painel.querySelector('[data-pluttu-form]');
    const entrada = formulario.querySelector('[name="mensagem"]');
    const encaminhar = painel.querySelector('[data-pluttu-encaminhar]').getAttribute('href');
    const saudacao = historico.firstElementChild.cloneNode(true);
    let enviando = false;

    const texto = (tag, conteudo) => {
        const elemento = document.createElement(tag);
        elemento.textContent = conteudo;
        return elemento;
    };
    const link = (rotulo, url) => {
        const elemento = texto('a', `${rotulo} →`);
        elemento.className = 'ajuda-link';
        elemento.href = url;
        return elemento;
    };
    const exibir = (itens) => {
        historico.replaceChildren(saudacao.cloneNode(true));
        itens.forEach((item) => {
            const usuario = document.createElement('div');
            usuario.className = 'pluttu-balao pluttu-balao--usuario';
            usuario.append(texto('strong', 'Você'), texto('p', item.mensagem));
            const bot = document.createElement('div');
            bot.className = 'pluttu-balao pluttu-balao--assistente';
            bot.append(texto('strong', 'Pluttu'));
            if (item.resposta.pergunta) bot.append(texto('small', `Da central de ajuda: ${item.resposta.pergunta}`));
            bot.append(texto('p', item.resposta.texto));
            if (item.resposta.url) bot.append(link(item.resposta.rotulo, item.resposta.url));
            if (item.resposta.encaminhar) bot.append(link('Encaminhar para a equipe', encaminhar));
            historico.append(usuario, bot);
        });
        historico.scrollTop = historico.scrollHeight;
    };
    painel.querySelectorAll('form').forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            if (enviando) return;
            const dados = new FormData(form);
            if (event.submitter && event.submitter.name) dados.set(event.submitter.name, event.submitter.value);
            enviando = true;
            erro.textContent = '';
            historico.setAttribute('aria-busy', 'true');
            painel.querySelectorAll('button').forEach((botao) => { botao.disabled = true; });
            try {
                const resposta = await fetch(form.action, {
                    method: 'POST', body: dados, credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const resultado = await resposta.json();
                if (!resposta.ok) throw new Error(resultado.erro || 'Não foi possível enviar. Atualize a página e tente novamente.');
                exibir(resultado.historico);
                if (form === formulario) entrada.value = '';
            } catch (falha) {
                erro.textContent = falha instanceof SyntaxError || falha instanceof TypeError
                    ? 'Não foi possível conectar ao Pluttu. Tente novamente ou use Falar com a equipe.'
                    : falha.message;
            } finally {
                enviando = false;
                historico.removeAttribute('aria-busy');
                painel.querySelectorAll('button').forEach((botao) => { botao.disabled = false; });
                if (form === formulario) entrada.focus();
            }
        });
    });
    historico.scrollTop = historico.scrollHeight;
})();

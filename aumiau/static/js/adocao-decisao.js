document.querySelectorAll('[data-decisao-adocao]').forEach((form) => {
    const decisao = form.querySelector('[name="acao"]');
    const resposta = form.querySelector('[name="resposta"]');
    const orientacao = form.querySelector('[data-orientacao-aprovacao]');
    if (!decisao || !resposta) return;
    const atualizar = () => {
        const aprovar = decisao.value === 'aprovar';
        resposta.placeholder = decisao.value === 'recusar'
            ? resposta.dataset.placeholderRecusa
            : resposta.dataset.placeholderAprovacao;
        resposta.required = decisao.value === 'recusar';
        if (orientacao) orientacao.hidden = !aprovar;
    };
    decisao.addEventListener('change', atualizar);
    atualizar();
});

document.addEventListener('DOMContentLoaded', () => {
    const ICONE_ABERTO = `
        <svg viewBox="0 0 24 24">
            <path
                d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6S2.5 12 2.5 12Z"
            ></path>

            <circle cx="12" cy="12" r="2.75"></circle>
        </svg>
    `;

    const ICONE_FECHADO = `
        <svg viewBox="0 0 24 24">
            <path d="M3 3l18 18"></path>

            <path
                d="M10.6 6.1A10 10 0 0 1 12 6c6 0 9.5 6 9.5 6a15 15 0 0 1-2.1 2.8"
            ></path>

            <path
                d="M6.1 6.1C3.8 8 2.5 12 2.5 12s3.5 6 9.5 6c1.5 0 2.8-.4 4-.9"
            ></path>

            <path
                d="M9.9 9.9a3 3 0 0 0 4.2 4.2"
            ></path>
        </svg>
    `;

    const campos = document.querySelectorAll(
        'input[type="password"]'
    );

    campos.forEach((campo) => {
        if (campo.closest('.campo-senha')) {
            return;
        }

        const caixa = document.createElement('div');
        caixa.className = 'campo-senha';

        campo.parentNode.insertBefore(caixa, campo);
        caixa.appendChild(campo);

        const botao = document.createElement('button');
        botao.type = 'button';
        botao.className = 'senha-toggle';
        botao.hidden = true;
        botao.title = 'Mostrar senha';

        botao.setAttribute('aria-label', 'Mostrar senha');
        botao.setAttribute('aria-pressed', 'false');

        if (campo.id) {
            botao.setAttribute('aria-controls', campo.id);
        }

        const icone = document.createElement('span');
        icone.className = 'senha-toggle__icone';
        icone.setAttribute('aria-hidden', 'true');
        icone.innerHTML = ICONE_ABERTO;

        botao.appendChild(icone);
        caixa.appendChild(botao);

        function definirVisibilidade(mostrar) {
            campo.type = mostrar ? 'text' : 'password';

            botao.setAttribute(
                'aria-pressed',
                String(mostrar)
            );

            botao.setAttribute(
                'aria-label',
                mostrar ? 'Ocultar senha' : 'Mostrar senha'
            );

            botao.title = mostrar
                ? 'Ocultar senha'
                : 'Mostrar senha';

            icone.innerHTML = mostrar
                ? ICONE_FECHADO
                : ICONE_ABERTO;
        }

        function atualizarOlho() {
            const temSenha = campo.value.length > 0;

            botao.hidden = !temSenha;

            if (!temSenha) {
                definirVisibilidade(false);
            }
        }

        botao.addEventListener('click', (event) => {
            const inicioSelecao = campo.selectionStart;
            const finalSelecao = campo.selectionEnd;
            const deveMostrar = campo.type === 'password';

            definirVisibilidade(deveMostrar);

            if (event.detail > 0) {
                campo.focus({
                    preventScroll: true,
                });

                if (
                    inicioSelecao !== null &&
                    finalSelecao !== null
                ) {
                    campo.setSelectionRange(
                        inicioSelecao,
                        finalSelecao
                    );
                }
            }
        });

        campo.addEventListener('input', atualizarOlho);
        campo.addEventListener('change', atualizarOlho);

        atualizarOlho();
    });
});
document.addEventListener('DOMContentLoaded', () => {
    const dialogs = [
        ...document.querySelectorAll('dialog.auth-dialog'),
    ];

        function atualizarRolagem() {
            const existeDialogAberto = dialogs.some(
                (dialog) => dialog.open
            );

            document.documentElement.classList.toggle(
                'auth-modal-aberto',
                existeDialogAberto
            );
        }

        function abrirDialog(dialog) {
            if (!dialog || dialog.open) {
                return;
            }

            dialogs.forEach((dialogAberto) => {
                if (
                    dialogAberto !== dialog &&
                    dialogAberto.open
                ) {
                    dialogAberto.close();
                }
            });

            dialog.showModal();
            atualizarRolagem();
        }

        document.addEventListener('click', (event) => {
            if (!(event.target instanceof Element)) {
                return;
            }

            const botaoTrocarPainel = event.target.closest(
                '[data-conta-show]'
            );

            if (botaoTrocarPainel) {
                const dialog = botaoTrocarPainel.closest('dialog');

                mostrarPainelConta(
                    dialog,
                    botaoTrocarPainel.dataset.contaShow,
                    true
                );

                return;
            }

            const botaoAbrir = event.target.closest(
                '[data-dialog-open]'
            );

            if (botaoAbrir) {
                const idDialog = botaoAbrir.dataset.dialogOpen;
                const dialog = document.getElementById(idDialog);

                if (dialog instanceof HTMLDialogElement) {
                    event.preventDefault();
                    abrirDialog(dialog);
                }

                return;
            }

            const botaoFechar = event.target.closest(
                '[data-dialog-close]'
            );

            if (botaoFechar) {
                botaoFechar.closest('dialog')?.close();
            }
        });

        dialogs.forEach((dialog) => {
            dialog.addEventListener('click', (event) => {
                const area = dialog.getBoundingClientRect();

                const clicouFora =
                    event.clientX < area.left ||
                    event.clientX > area.right ||
                    event.clientY < area.top ||
                    event.clientY > area.bottom;

                if (clicouFora) {
                    dialog.close();
                }
            });

            dialog.addEventListener('close', atualizarRolagem);
        });

        const contaDialog = document.getElementById(
            'conta-dialog'
        );

        if (contaDialog instanceof HTMLDialogElement) {
            const painelInicial =
                contaDialog.dataset.contaInitialPanel || 'menu';

            mostrarPainelConta(
                contaDialog,
                painelInicial
            );

            contaDialog.addEventListener('close', () => {
                mostrarPainelConta(
                    contaDialog,
                    painelInicial
                );
            });
        }

        const dialogInicial = dialogs.find(
            (dialog) => dialog.dataset.openOnLoad === 'true'
        );

        if (dialogInicial) {
            abrirDialog(dialogInicial);

            const url = new URL(window.location.href);

            url.searchParams.delete('conta');

            window.history.replaceState(
                {},
                '',
                `${url.pathname}${url.search}${url.hash}`
            );
        }

        function mostrarPainelConta( dialog, nomePainel, moverFoco = false) {
        if (!(dialog instanceof HTMLDialogElement)) {
            return;
        }

        const paineis = [
            ...dialog.querySelectorAll('[data-conta-panel]'),
        ];

        const painelAtivo = paineis.find((painel) => {
            return painel.dataset.contaPanel === nomePainel;
        });

        if (!painelAtivo) {
            return;
        }

        paineis.forEach((painel) => {
            painel.hidden = painel !== painelAtivo;
        });

            dialog
        .querySelectorAll('[data-conta-senha]')
        .forEach((campo) => {
            campo.value = '';
            campo.type = 'password';

            campo.dispatchEvent(
                new Event('input', {
                    bubbles: true,
                })
            );
        });

        const tituloAtivo = painelAtivo.querySelector(
            '[data-conta-panel-title]'
        );

        if (tituloAtivo?.id) {
            dialog.setAttribute(
                'aria-labelledby',
                tituloAtivo.id
            );
        }

        if (moverFoco) {
            requestAnimationFrame(() => {
                const elementoFoco = painelAtivo.querySelector(
                    '[data-conta-focus], ' +
                    'button:not(:disabled), ' +
                    'input:not(:disabled), ' +
                    'select:not(:disabled)'
                );

                elementoFoco?.focus();
            });
        }
    }
});
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
});
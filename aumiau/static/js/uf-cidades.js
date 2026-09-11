document.addEventListener('DOMContentLoaded', () => {
    const cacheCidades = new Map();

    const normalizar = (texto) => {
        return texto
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLocaleUpperCase('pt-BR');
    };

    async function buscarCidades(uf, signal) {
        if (cacheCidades.has(uf)) {
            return cacheCidades.get(uf);
        }

        const resposta = await fetch(
            `https://brasilapi.com.br/api/ibge/municipios/v1/${encodeURIComponent(uf)}?providers=gov`,
            {
                headers: {
                    Accept: 'application/json',
                },
                signal,
            }
        );

        if (!resposta.ok) {
            throw new Error('Não foi possível consultar as cidades.');
        }

        const dados = await resposta.json();

        if (!Array.isArray(dados)) {
            throw new Error('Resposta inválida da API.');
        }

        const cidades = [
            ...new Set(
                dados
                    .map((municipio) => municipio.nome?.trim())
                    .filter(Boolean)
            ),
        ].sort((cidadeA, cidadeB) => {
            return cidadeA.localeCompare(
                cidadeB,
                'pt-BR',
                { sensitivity: 'base' }
            );
        });

        cacheCidades.set(uf, cidades);

        return cidades;
    }

    document
        .querySelectorAll('[data-uf-cidades-form]')
        .forEach((formulario) => {
            const ufSelect = formulario.querySelector(
                '[data-uf-select]'
            );

            const cidadeSelect = formulario.querySelector(
                '[data-cidade-select]'
            );

            const status = formulario.querySelector(
                '[data-cidades-status]'
            );

            if (!ufSelect || !cidadeSelect) {
                return;
            }

            let controlador;
            let numeroConsulta = 0;

            const cidadeInicial = cidadeSelect.value.trim();

            function mostrarOpcao(texto, desabilitado = true) {
                cidadeSelect.replaceChildren(
                    new Option(texto, '')
                );

                cidadeSelect.disabled = desabilitado;
            }

            async function carregarCidades(
                cidadeSelecionada = ''
            ) {
                const uf = ufSelect.value.trim().toUpperCase();
                const consultaAtual = ++numeroConsulta;

                controlador?.abort();

                if (!uf) {
                    mostrarOpcao('Selecione primeiro a UF');

                    if (status) {
                        status.textContent = '';
                    }

                    return;
                }

                controlador = new AbortController();

                mostrarOpcao('Carregando cidades...');

                if (status) {
                    status.textContent = 'Consultando cidades...';
                }

                try {
                    const cidades = await buscarCidades(
                        uf,
                        controlador.signal
                    );

                    if (consultaAtual !== numeroConsulta) {
                        return;
                    }

                    cidadeSelect.replaceChildren(
                        new Option('Selecione a cidade', '')
                    );

                    cidades.forEach((cidade) => {
                        cidadeSelect.add(
                            new Option(cidade, cidade)
                        );
                    });

                    const cidadeEncontrada = cidades.find(
                        (cidade) => {
                            return normalizar(cidade) ===
                                normalizar(cidadeSelecionada);
                        }
                    );

                    if (cidadeEncontrada) {
                        cidadeSelect.value = cidadeEncontrada;
                    }

                    cidadeSelect.disabled = false;

                    if (status) {
                        status.textContent = '';
                    }
                } catch (erro) {
                    if (erro.name === 'AbortError') {
                        return;
                    }

                    if (consultaAtual !== numeroConsulta) {
                        return;
                    }

                    if (cidadeSelecionada) {
                        cidadeSelect.replaceChildren(
                            new Option(
                                cidadeSelecionada,
                                cidadeSelecionada,
                                true,
                                true
                            )
                        );

                        cidadeSelect.disabled = false;
                    } else {
                        mostrarOpcao(
                            'Não foi possível carregar as cidades'
                        );
                    }

                    if (status) {
                        status.textContent =
                            'Não foi possível consultar as cidades. Selecione a UF novamente.';
                    }
                }
            }

            ufSelect.addEventListener('change', () => {
                carregarCidades('');
            });

            if (ufSelect.value) {
                carregarCidades(cidadeInicial);
            } else {
                mostrarOpcao('Selecione primeiro a UF');
            }
        });
});
# AuMiau

Aplicação Django para adoção de pets e cadastro de ONGs.

## Executar no Windows

Requer Python 3.12 ou superior. Execute na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe aumiau\manage.py migrate
.\.venv\Scripts\python.exe aumiau\manage.py runserver
```

Abra http://127.0.0.1:8000/. Após atualizar o código em outro PC, instale as dependências e execute `migrate` novamente. Use o Python da `.venv` deste repositório para evitar ambientes sem Django ou Pillow.

### Comando curto no VS Code

O comando abaixo também funciona na raiz do repositório e na pasta `aumiau`, sem depender do VS Code. Se for iniciado com o Python global, o `manage.py` usa automaticamente a `.venv` existente neste projeto. Não instala pacotes nem altera a política do PowerShell. Se você ativou outro ambiente virtual explicitamente, ele é respeitado; desative-o para usar a `.venv` do projeto.

Abra a raiz `Aumiau-DoacaoDePets` como pasta do VS Code. O arquivo `.vscode/settings.json` configura **novos terminais** para abrir em `aumiau` e usar o Python de `.venv` diretamente, inclusive quando o PowerShell bloqueia scripts de ativação. Depois de instalar as dependências acima, feche os terminais antigos, abra um novo e execute:

```powershell
python manage.py runserver
```

Se o editor ainda marcar os imports de Django como ausentes, use **Python: Select Interpreter** e selecione `.venv\Scripts\python.exe` deste repositório. O interpretador salvo anteriormente pelo editor pode prevalecer sobre o padrão do projeto.

Em um PowerShell fora do VS Code, na raiz do repositório, use `.\.venv\Scripts\python.exe aumiau\manage.py runserver`. Não é necessário liberar a execução de scripts. Outra opção é abrir o Prompt de Comando (`cmd`) na raiz, executar `.venv\Scripts\activate.bat`, entrar em `aumiau` e usar o comando curto.

## Cadastros e aprovação

- `/pets/`: busca com filtros, ordenação e paginação.
- `/pets/anunciar/`: cadastro de pet com foto, galeria, prévia e rascunho.
- `/pets/meus-anuncios/`: acompanhamento dos anúncios do responsável.
- `/ongs/`: diretório e perfis das organizações aprovadas.
- `/ongs/cadastrar/` e `/ongs/painel/`: cadastro, edição e gestão das ONGs do usuário.
- `/ajuda/`: perguntas frequentes, pesquisa e abertura de chamados.

ONGs e anúncios novos ficam pendentes até a aprovação no painel do supervisor. Editar um cadastro publicado exige nova análise. Pets de uma ONG só aparecem publicamente enquanto ela estiver aprovada. O formulário permite vincular pets apenas a ONGs aprovadas do próprio usuário. Contatos públicos são informados explicitamente; os contatos privados da conta não são copiados para anúncios.

As conversas sobre adoção usam o e-mail ou WhatsApp informado pelo responsável. Os chamados da central de ajuda ficam no banco e podem ser respondidos pelo administrador em `/admin/adocoes/chamadoajuda/`. Não há envio automático de e-mails.

## Dados em computadores diferentes

O SQLite fica em `aumiau/db.sqlite3`, e as fotos enviadas ficam em `aumiau/media/`. Ambos são ignorados pelo Git, assim como a `.venv`. `git pull` traz o código e as migrações, mas não os usuários, pets, ONGs nem as fotos. `migrate` atualiza a estrutura do banco e não transfere os registros do outro PC.

Para transferir uma instalação local, pare os servidores e preserve uma cópia do banco e de `media/` dos dois computadores antes de copiar os arquivos. Copiar um banco sobre outro substitui os registros existentes; não é uma mesclagem. Para uso simultâneo com os mesmos dados em vários computadores, configure um banco compartilhado e um armazenamento compartilhado de imagens. Não envie bancos com dados pessoais ou uploads ao repositório Git.

ONGs antigas sem responsável podem ser vinculadas a uma conta pelo administrador no cadastro da organização.

## Verificações

Use configurações isoladas para que os testes não acessem dados compartilhados:

```powershell
.\.venv\Scripts\python.exe aumiau\manage.py check
.\.venv\Scripts\python.exe aumiau\manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe aumiau\manage.py test adocoes ongs pets usuarios supervisores --settings=aumiau.settings_test
```

Os testes usam um banco temporário e verificam cadastros, uploads, moderação, filtros, permissões e retorno após login/cadastro.

## Ativar os mesmos cadastros e fotos em todos os PCs

O código oferece dois modos: `local` (padrão atual) e `shared` (PostgreSQL + armazenamento compatível com S3). A configuração não cria uma hospedagem nem transfere automaticamente o SQLite existente.

1. Configure um banco PostgreSQL central e um bucket de imagens no serviço de sua escolha.
2. Copie `.env.example` para `.env` na raiz de cada checkout, sem sobrescrever um `.env` existente.
3. Defina `AUMIAU_DATA_MODE=shared` e preencha `DATABASE_URL`, `DJANGO_SECRET_KEY`, `S3_BUCKET_NAME`, `S3_ACCESS_KEY_ID` e `S3_SECRET_ACCESS_KEY`. Todos os PCs devem usar o mesmo banco, bucket e chave Django. Para provedores compatíveis com S3, preencha também o endpoint HTTPS e a região informados por eles.
4. Instale `requirements.txt`, rode `migrate` e inicie o servidor. Com isso, os novos cadastros e uploads são gravados nos serviços centrais e aparecem nos outros PCs ao atualizar a página.

No modo `shared`, dados incompletos geram uma mensagem de configuração. O projeto não troca silenciosamente para SQLite nem para fotos locais. As imagens usam URLs assinadas e os uploads não sobrescrevem arquivos homônimos.

Para levar os dados já existentes, é necessária uma migração inicial: preserve um backup, escolha qual banco local contém os registros que serão importados e transfira também suas fotos, mantendo os caminhos registrados no banco. Não importe um SQLite sobre um banco compartilhado que já tenha dados. Esse procedimento depende do serviço escolhido e dos dados de cada PC.

O `.env`, os bancos e os uploads continuam fora do Git. Compartilhe as credenciais apenas com pessoas autorizadas, por um canal privado. Para hospedar a aplicação, configure ainda `DJANGO_DEBUG=false`, os domínios permitidos e as origens HTTPS de formulários.

Documentação dos backends: [PostgreSQL no Django](https://docs.djangoproject.com/en/6.0/ref/databases/#postgresql-notes) e [armazenamento S3](https://django-storages.readthedocs.io/en/stable/backends/amazon-S3.html).

## Continuar alterações de código em outro computador

O banco compartilhado sincroniza os cadastros; alterações em Python, HTML, CSS e JavaScript são distribuídas pelo Git. Na máquina onde terminou de trabalhar, revise os arquivos, faça o commit e envie sua branch com `git push`. Antes de continuar em outro PC, use a mesma branch e execute:

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe aumiau\manage.py migrate
```

Se houver alterações locais ainda não salvas em commit, conclua ou preserve esse trabalho antes do `pull`. O projeto não cria commits, envia código ou resolve conflitos automaticamente.

## Cadastro de pets e fotos

A espécie selecionada determina o select de raças/tipos. O catálogo local inclui “Sem raça definida (vira-lata)”, “Desconheço” e “Outra raça ou tipo”; não precisa de uma API disponível para cadastrar. Há opções específicas para coelho, hamster, porquinho-da-índia, ave, peixe, tartaruga/jabuti, furão, chinchila e outros répteis.

Informe a data de nascimento ou marque que não sabe para preencher anos/meses aproximados. A idade calculada acompanha o tempo. Cadastros antigos conservam suas estimativas e porte desconhecido; novos formulários exigem pequeno, médio ou grande. O valor interno `pendente` permanece compatível com o banco, mas aparece como “Em análise”.

Com JavaScript ativo, o anúncio é enviado sem recarregar a página quando há erros: os arquivos selecionados permanecem no formulário. Cada nova foto tem um botão de remoção. Fechar ou recarregar manualmente a página descarta os arquivos ainda não enviados. Os links de e-mail oferecem Gmail, Outlook e o aplicativo padrão do dispositivo.

## CPF, CNPJ e moderação

Novas contas exigem CPF com dígitos verificadores válidos e sem duplicidade. Essa checagem é matemática, não confirma titularidade nem situação na Receita. O CPF completo não é armazenado: ficam um HMAC e os quatro últimos dígitos. Defina uma `DOCUMENT_HASH_KEY` forte, estável e igual em todos os PCs antes de começar os cadastros compartilhados. Se vazia, usa `DJANGO_SECRET_KEY`; mudar a chave invalida a comparação com hashes existentes, que não podem ser recalculados sem solicitar o CPF novamente.

A consulta oficial de CPF **não está integrada nem ativa**. A [Consulta CPF v3 do Serpro](https://centraldeajuda.serpro.gov.br/duvidas/pt/avisos/avisoconsultacpfv3/) exige contratação, credenciais e data de nascimento. Nenhum CPF é enviado a um serviço externo pelo código atual.

O cadastro de ONG exige CNPJ único e confere seus dígitos. CNPJs numéricos são consultados pela [BrasilAPI](https://brasilapi.com.br/docs#tag/CNPJ), com prazo de 5 segundos, cache de uma hora e exigência de situação ativa. Indisponibilidade não gera validação falsa: o formulário mantém os valores e solicita nova tentativa. A consulta não comprova o vínculo do responsável com a instituição; a aprovação da equipe continua necessária. O [CNPJ alfanumérico](https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/cnpj-alfanumerico/cnpj-alfa) tem dígitos conferidos localmente e aguarda confirmação documental explícita da supervisão, pois a API documenta somente o formato numérico. Cadastros antigos não recebem CNPJ inventado.

No painel de supervisão, suspensão e banimento exigem um motivo. A conta perde o acesso, os anúncios são arquivados e as ONGs são suspensas. Banimento registra o identificador de CPF para impedir novo cadastro com o mesmo documento informado; isso não é uma prova de identidade. Contas antigas sem CPF só podem ser bloqueadas pelo cadastro existente. Reativar não republica automaticamente anúncios e ONGs.

“Excluir minha conta” exige senha atual (ou confirmação recente pelo Google para contas sem senha) e confirmação explícita. Anonimiza a conta, remove chamados e dados pessoais dos anúncios atuais e solicita a remoção das fotos no armazenamento. Não altera animais transferidos a outro responsável. Referências de auditoria são preservadas sem a identificação da conta; o hash de CPF só permanece separado se houver banimento. Uma falha externa ao remover fotos é registrada no log para o administrador tentar novamente.

## Ativar login com Google

O fluxo está implementado, mas o botão depende de credenciais reais. Configure um cliente OAuth do tipo Aplicativo da Web e a tela de consentimento no Google Cloud conforme a [documentação oficial](https://developers.google.com/identity/openid-connect/openid-connect). Cadastre a URI de retorno exata, por exemplo `http://127.0.0.1:8000/usuarios/google/retorno/`, e preencha `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `GOOGLE_REDIRECT_URI` no `.env`. Se usar a porta 8001 ou `localhost`, ajuste o mesmo endereço nas duas configurações. Em hospedagem, use HTTPS. Instale `requirements.txt` atualizado e reinicie o servidor.

O código verifica o ID token com a biblioteca oficial, além de state, nonce, PKCE, expiração e e-mail verificado. Novos usuários completam CPF, localização e termos antes de entrar. Uma conta existente não é vinculada apenas por coincidência do e-mail: entre primeiro com senha e escolha “Vincular Google” em Minha conta. Contas Google podem criar uma senha após confirmar sua identidade novamente. Os testes simulam respostas do provedor; um login real só pode ser conferido depois da configuração das credenciais.

## Pluttu e atendimento humano

O Pluttu fica na central de ajuda e responde usando as FAQs do próprio site, sem API de IA externa. Mantém as últimas seis perguntas na sessão e oferece encaminhamento quando não encontra uma resposta. O usuário revisa a mensagem e escolhe se deseja anexar a conversa ao chamado. A equipe responde pelo administrador, e o usuário acompanha em Meus chamados; não há promessa de atendente ao vivo. O histórico encaminhado é assinado e vinculado à conta que o revisou.

Para iniciar com um comando curto, abra um novo terminal do VS Code conforme a configuração acima e execute `python manage.py runserver`. Depois de atualizar o projeto, execute também `python manage.py migrate` nesse ambiente.

## Painel e cadastros de demonstração

O admin e a supervisão concentram anúncios na opção **Pets**; a fila de análise permanece disponível pelo filtro de status. Títulos usam o sufixo `AuMiau Admin`, com favicon próprio. O formulário administrativo também oferece raça/tipo por espécie e nascimento ou idade estimada. ONGs podem receber uma foto JPG/PNG de até 5 MB.

Para criar os mesmos exemplos em outra máquina, com o ambiente virtual ativo e dentro da pasta `aumiau`:

```powershell
python manage.py migrate
python manage.py popular_demo
python manage.py runserver
```

`popular_demo` cria 12 pets e 3 ONGs fictícias com 15 fotos reais licenciadas do Pexels. Funciona apenas no modo local, sem downloads: as imagens estão incluídas no projeto. Executar novamente preserva edições, não duplica os exemplos e não altera cadastros reais. Os cards usam os fluxos normais de navegação e contato sem inventar documentos ou dados pessoais. Há 9 pets publicados, 2 em análise e 1 adotado.

Os [créditos e fontes das fotografias](aumiau/pets/demo_data/README.md) acompanham o projeto. Estes exemplos ajudam a reproduzir as telas em outro PC; dados reais ainda precisam do banco e armazenamento compartilhados descritos acima.

O site público, os formulários, a conta e os painéis foram ajustados para uso em celular. O favicon SVG enviado para o projeto está em `aumiau/static/img/favicon.svg`. Para colocar a aplicação no ar, siga o [guia de hospedagem](DEPLOY.md).

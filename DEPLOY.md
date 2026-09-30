# Publicar o AuMiau sem perder cadastros

Para uma primeira versão gratuita sem cadastrar cartão, use **Render Free** para o Django e **Neon Free** para o PostgreSQL e as fotos. O projeto já separa dados locais (`AUMIAU_DATA_MODE=local`) de dados compartilhados (`shared`). O Render apaga arquivos locais em reinícios e após períodos ociosos; por isso o banco SQLite e a pasta `media/` não podem guardar os cadastros publicados.

1. Crie um projeto PostgreSQL no plano **Free** da [Neon](https://neon.com/docs/get-started/connect-neon), na região **AWS N. Virginia (`aws-us-east-1`)**. Em **Connect**, desative a opção de pool e copie a URL de conexão PostgreSQL **direta**, com `sslmode=require`, para `DATABASE_URL`. O mesmo endereço é usado durante `migrate` no build; mantenha uma conexão direta nessa implantação simples. Não coloque essa URL no Git.
2. Na branch principal da Neon, abra **Object storage → New bucket** e crie `aumiau-fotos` com acesso **private**. Em **Connect → Storage → Parameters only**, copie `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ENDPOINT_URL_S3` e `AWS_REGION`. A [Neon documenta esse fluxo pelo painel](https://neon.com/docs/storage/buckets) e a [correspondência das credenciais](https://neon.com/docs/storage/authentication). O projeto usa URLs assinadas para ler as fotos privadas.
3. Envie **todos os arquivos alterados** deste repositório ao Git remoto. No Render, crie um Blueprint a partir do [render.yaml](render.yaml). O plano web deve ser **Free**, na região **Virginia**. Preencha as variáveis marcadas `sync: false` conforme a tabela abaixo. O Blueprint gera `DJANGO_SECRET_KEY` e `DOCUMENT_HASH_KEY`; preserve esses valores, pois trocá-los afeta sessões e a identificação de CPF já cadastrados.

   | Variável no Render | Valor da Neon |
   | --- | --- |
   | `DATABASE_URL` | URL PostgreSQL direta, sem pool |
   | `S3_BUCKET_NAME` | `aumiau-fotos` |
   | `S3_ACCESS_KEY_ID` | `AWS_ACCESS_KEY_ID` |
   | `S3_SECRET_ACCESS_KEY` | `AWS_SECRET_ACCESS_KEY` |
   | `S3_ENDPOINT_URL` | `AWS_ENDPOINT_URL_S3` |
   | `S3_REGION_NAME` | `AWS_REGION`, por exemplo `us-east-1` (sem o prefixo `aws-`) |

   Mantenha `S3_ADDRESSING_STYLE=path`, `AUMIAU_DATA_MODE=shared` e `DJANGO_DEBUG=false`. Nunca publique esses segredos no Git.
4. O [build.sh](build.sh) instala as dependências, executa `collectstatic` e aplica `migrate`. O serviço inicia com Gunicorn. O host fornecido pelo Render é adicionado automaticamente. Para domínio próprio, adicione o domínio em `DJANGO_ALLOWED_HOSTS` e a origem HTTPS em `DJANGO_CSRF_TRUSTED_ORIGINS`. Mantenha `DJANGO_DEBUG=false`.
5. O Render Free não oferece shell para executar `createsuperuser`. Para criar a primeira conta administrativa, use um checkout local com `.env` em modo `shared`, apontando para **o mesmo** banco e bucket da Neon, e rode `python manage.py createsuperuser`. Faça isso apenas em um PC confiável e nunca publique o `.env`.
6. Confira o site público, `/pets/`, `/admin/`, o cadastro de ONG, o envio e a leitura de uma foto após reiniciar o serviço. Se usar login Google, cadastre a URL HTTPS de retorno no Google Cloud e defina `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `GOOGLE_REDIRECT_URI` no Render.

Os cadastros antigos em `aumiau/db.sqlite3` e as fotos em `aumiau/media/` **não são migrados automaticamente**. Antes de importar, faça backup, escolha uma origem e preserve os caminhos das fotos ao transferi-las para o bucket. Não importe um banco antigo sobre dados novos da Neon sem planejar a mesclagem. O Git distribui código e migrações; a Neon mantém os dados entre computadores. Mantenha cópias independentes dos dados e das fotos.

Limites atuais: o [Render Free](https://render.com/docs/free) hiberna após 15 minutos sem acesso, pode demorar cerca de um minuto para acordar e oferece 750 horas de instância por mês por workspace. O banco gratuito do próprio Render expira em 30 dias; não o use para cadastros. A [Neon Free](https://neon.com/blog/neon-backend-is-ga) oferece 0,5 GB de banco, 100 CU-h por mês e 5 GB de Object Storage por projeto. A [API S3 da Neon](https://neon.com/docs/storage/s3-compatibility) cobre as operações e URLs assinadas usadas pelo projeto, mas a integração específica com `django-storages` deve ser conferida com um upload e uma leitura reais após configurar a conta. Se houver incompatibilidade, o [Cloudflare R2 Standard](https://developers.cloudflare.com/r2/pricing/) é uma alternativa com cota gratuita de 10 GB-mês; sua [ativação exige checkout de assinatura](https://developers.cloudflare.com/r2/get-started/) e pode gerar cobranças acima da cota.

O plano gratuito é adequado para testes públicos e volume inicial pequeno. Para operação contínua com cadastros reais, acompanhe as cotas e planeje uma hospedagem paga com disponibilidade e backups apropriados.

Ao executar `python manage.py check --deploy` localmente com `DJANGO_DEBUG=false`, o Django pode avisar sobre redirecionamento SSL e HSTS. O [Render redireciona HTTP para HTTPS](https://render.com/docs/native-runtimes) no proxy; HSTS deve ser ativado somente depois de confirmar o domínio e o certificado em produção.

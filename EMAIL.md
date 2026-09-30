# Recuperação de senha

O link **Esqueci minha senha** já abre o fluxo de recuperação. Em desenvolvimento,
sem credenciais de envio e com `DJANGO_DEBUG=true`, a mensagem aparece apenas no
terminal. Na hospedagem, sem configuração, a página informa indisponibilidade.

## Ativar gratuitamente no Render

1. Crie uma conta no [plano gratuito da Brevo](https://www.brevo.com/products/transactional-email/).
   O plano oferece até 300 envios por dia; confirme os limites na sua conta.
2. Em **Configurações → Remetentes, domínios e IPs**, adicione o remetente do AuMiau
   e conclua a verificação recebida no e-mail. Se usar domínio próprio, conclua a
   autenticação indicada pela Brevo. O serviço transacional precisa estar liberado.
3. Em **SMTP e API → Chaves de API**, crie uma chave da API (não a senha SMTP).
4. No Render, abra **aumiau → Environment → Edit** e cadastre:

   | Variável | Valor |
   | --- | --- |
   | `BREVO_API_KEY` | A chave secreta da API Brevo |
   | `DEFAULT_FROM_EMAIL` | O endereço do remetente verificado |
   | `EMAIL_FROM_NAME` | `AuMiau` |
   | `DJANGO_DEBUG` | `false` |

5. Salve e aplique o novo deploy. Para uso local, preencha as mesmas variáveis
   somente no `.env`, que é ignorado pelo Git. Não coloque valores reais no
   `.env.example`, no `render.yaml`, em commits ou no chat.
6. No site publicado, use **Esqueci minha senha** com o e-mail de uma conta ativa
   que tenha senha. Confira a caixa de entrada e o spam. O link expira em uma hora
   e perde a validade após a alteração da senha. Contas exclusivas do Google
   continuam usando o login Google.

O envio usa a [API HTTPS da Brevo](https://developers.brevo.com/reference/send-transac-email),
pois o [Render Free bloqueia as portas SMTP 25, 465 e 587](https://render.com/docs/free).
As respostas de chamados e adoções permanecem nas respectivas áreas do site;
elas não disparam e-mails.

## Validação realizada

Os testes usam caixa de saída em memória e simulam a API, sem disparar mensagens
reais. A entrega na caixa de entrada depende das credenciais, da aprovação do
remetente e da configuração na conta Brevo.

import re
import unicodedata

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core import signing
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from pets.models import Pet

from .forms import ChamadoAjudaForm, PluttuForm
from .models import ChamadoAjuda


CATEGORIAS_FAQ = [
    {'slug': 'adocao', 'nome': 'Adoção', 'icone': '🐾', 'descricao': 'Processo, requisitos e acompanhamento'},
    {'slug': 'ongs', 'nome': 'ONGs e protetores', 'icone': '🏠', 'descricao': 'Cadastro, anúncios e gestão'},
    {'slug': 'conta', 'nome': 'Minha conta', 'icone': '👤', 'descricao': 'Login, dados pessoais e segurança'},
    {'slug': 'doacoes', 'nome': 'Doações', 'icone': '💳', 'descricao': 'Como ajudar com segurança'},
]

PERGUNTAS = [
    {
        'id': 'recuperar_senha', 'rota': 'usuarios:recuperar', 'rotulo': 'Recuperar minha senha',
        'categoria': 'conta', 'destaque': False,
        'pergunta': 'Esqueci minha senha. Como recuperar o acesso?',
        'resposta': 'Na tela de entrada, selecione Esqueci minha senha e informe o e-mail cadastrado. Se a conta estiver ativa e tiver senha, enviaremos um link válido por uma hora. Confira também o spam. Contas criadas somente pelo Google devem usar Entrar com Google.',
    },
    {
        'id': 'adotar', 'rota': 'pets:lista', 'rotulo': 'Encontrar um pet',
        'categoria': 'adocao', 'destaque': True,
        'pergunta': 'Como funciona o processo de adoção?',
        'resposta': 'Encontre um pet na página de adoção e abra o anúncio para conhecer sua história e suas necessidades. Use Solicitar adoção no anúncio e acompanhe a resposta em Minhas adoções. A equipe analisa o pedido junto ao responsável pelo pet, que confirma os requisitos e a disponibilidade. Após a aprovação, abra Mensagens no menu da sua conta para conversar com o responsável e combinar o dia, horário e local da retirada.',
    },
    {
        'id': 'contato', 'rota': 'ongs:lista', 'rotulo': 'Conhecer as ONGs',
        'categoria': 'adocao', 'destaque': True,
        'pergunta': 'Posso falar com a ONG antes de solicitar a adoção?',
        'resposta': 'Sim. Consulte o perfil público da ONG ou os contatos disponibilizados no anúncio do pet. Use a conversa para esclarecer cuidados, rotina e requisitos antes de decidir pela adoção. O AuMiau não confirma a adoção automaticamente.',
    },
    {
        'id': 'conta', 'rota': 'home', 'rotulo': 'Abrir minha conta',
        'categoria': 'conta', 'destaque': True,
        'pergunta': 'Como editar meus dados ou alterar minha senha?',
        'resposta': 'Entre na sua conta, abra o menu do perfil e selecione Minha conta. Nessa área você pode editar os dados do cadastro e alterar a senha informando a senha atual. Se precisar relatar um problema, envie uma mensagem pela central de ajuda.',
    },
    {
        'id': 'anunciar', 'rota': 'pets:anunciar', 'rotulo': 'Anunciar um pet',
        'categoria': 'ongs', 'destaque': True,
        'pergunta': 'Como anunciar um pet para adoção?',
        'resposta': 'Entre na sua conta e selecione Anunciar pet. Preencha as informações do animal, sua localização e seus cuidados, adicione uma foto e envie o cadastro. O anúncio passa por análise antes de aparecer publicamente. Você acompanha a situação em Meus anúncios.',
    },
    {
        'id': 'doacoes', 'rota': 'ongs:lista', 'rotulo': 'Conhecer as ONGs',
        'categoria': 'doacoes', 'destaque': True,
        'pergunta': 'O AuMiau cobra alguma taxa?',
        'resposta': 'O cadastro e a publicação de anúncios não têm cobrança na plataforma. O AuMiau não processa pagamentos nem recebe doações pelo site. Se desejar ajudar uma ONG, converse diretamente com ela e confira os dados do destinatário antes de qualquer transferência.',
    },
    {
        'id': 'ong', 'rota': 'ongs:cadastrar', 'rotulo': 'Cadastrar ONG',
        'categoria': 'ongs', 'destaque': False,
        'pergunta': 'Como cadastrar uma ONG e acompanhar a análise?',
        'resposta': 'Entre na sua conta e escolha Cadastrar ONG. Informe os dados da organização e envie o formulário. Na área Minhas ONGs você acompanha a situação do cadastro. Apenas organizações aprovadas aparecem na lista pública de ONGs.',
    },
    {
        'id': 'analise', 'rota': 'pets:meus_pets', 'rotulo': 'Ver meus anúncios',
        'categoria': 'ongs', 'destaque': False,
        'pergunta': 'Por que meu pet ou minha ONG ainda não aparece no site?',
        'resposta': 'Novos cadastros precisam passar pela análise da equipe. Confira a situação e, quando houver, o motivo da rejeição na sua área de anúncios ou de ONGs. Atualizações em cadastros já publicados também podem exigir uma nova análise.',
    },
    {
        'id': 'chamados', 'rota': 'meus_chamados', 'rotulo': 'Ver meus chamados',
        'categoria': 'conta', 'destaque': False,
        'pergunta': 'Como acompanho uma mensagem enviada à central de ajuda?',
        'resposta': 'Entre com a mesma conta usada no envio e abra Meus chamados. Selecione o assunto para ver a mensagem, a situação e a resposta, quando disponível. As respostas ficam nessa área; não há envio automático de e-mail.',
    },
    {
        'id': 'denuncia', 'rota': 'chamado_novo', 'rotulo': 'Relatar à equipe',
        'categoria': 'doacoes', 'destaque': False,
        'pergunta': 'Como relatar um anúncio suspeito ou um pedido de dinheiro?',
        'resposta': 'Abra um chamado com o assunto Segurança e denúncias. Inclua o link do anúncio e descreva o que aconteceu, sem enviar senhas ou dados de pagamento. A mensagem poderá ser consultada pela administração da plataforma.',
    },
]


def _normalizar(texto):
    return ''.join(
        letra for letra in unicodedata.normalize('NFKD', texto.casefold())
        if not unicodedata.combining(letra)
    )


def _resposta_faq(faq):
    url = reverse(faq['rota'])
    if faq['id'] == 'conta':
        url += '?conta=1'
    elif faq['id'] == 'denuncia':
        url += '?categoria=seguranca'
    return {'texto': faq['resposta'], 'pergunta': faq['pergunta'], 'url': url, 'rotulo': faq['rotulo'], 'encaminhar': False}


def _responder_pluttu(mensagem):
    """Resolve intenções conhecidas usando apenas o conteúdo publicado na FAQ."""
    texto = _normalizar(mensagem)
    palavras = set(re.findall(r'[a-z0-9]+', texto))
    for faq in PERGUNTAS:
        if texto.rstrip(' .?!') == _normalizar(faq['pergunta']).rstrip(' .?!'):
            return _resposta_faq(faq)

    def tem(*termos):
        return bool(palavras.intersection(termos))

    topico = None
    if tem('humano', 'humana', 'pessoa', 'atendente', 'suporte', 'equipe'):
        return {
            'texto': 'Você pode encaminhar sua dúvida para uma pessoa da equipe. Abra um chamado, revise a conversa e escolha se deseja incluí-la. A resposta ficará em Meus chamados; este atendimento não é um chat ao vivo.',
            'encaminhar': True,
        }
    if tem('senha') and tem('esqueci', 'esqueceu', 'recuperar', 'recuperacao', 'perdi'):
        topico = 'recuperar_senha'
    elif tem('denuncia', 'denunciar', 'suspeito', 'golpe', 'fraude'):
        topico = 'denuncia'
    elif tem('analise', 'pendente', 'aprovado', 'rejeitado', 'rejeicao') or 'nao aparece' in texto:
        topico = 'analise'
    elif tem('chamado', 'chamados') and tem('acompanhar', 'acompanho', 'resposta', 'ver', 'consultar', 'andamento'):
        topico = 'chamados'
    elif tem('ong', 'ongs', 'organizacao') and tem('cadastrar', 'cadastro', 'registrar', 'criar'):
        topico = 'ong'
    elif tem('anunciar', 'publicar') or (tem('cadastrar', 'cadastro') and tem('pet', 'animal', 'cachorro', 'gato')):
        topico = 'anunciar'
    elif tem('alterar', 'editar', 'trocar', 'atualizar') and tem('senha', 'dados', 'cadastro', 'conta', 'telefone', 'email'):
        topico = 'conta'
    elif tem('taxa', 'cobra', 'cobrado', 'pagar', 'doacao', 'doacoes', 'doar'):
        topico = 'doacoes'
    elif tem('falar', 'contato', 'contatar', 'conversar') and tem('ong', 'ongs', 'responsavel', 'anunciante', 'protetor'):
        topico = 'contato'
    elif tem('adotar') or (tem('adocao') and tem('como', 'processo', 'funciona', 'requisitos')):
        topico = 'adotar'
    elif palavras and palavras.issubset({'oi', 'ola', 'bom', 'boa', 'dia', 'tarde', 'noite', 'pluttu', 'tudo', 'bem'}):
        return {'texto': 'Olá! Sou o Pluttu, assistente virtual do AuMiau. Posso explicar como adotar, anunciar um pet, cadastrar uma ONG ou acompanhar seus chamados. Qual é sua dúvida?', 'encaminhar': False}

    if not topico:
        return {
            'texto': 'Ainda não encontrei uma orientação na nossa central que responda a essa dúvida. Posso encaminhar você para uma pessoa da equipe: abra um chamado e acompanhe a resposta em Meus chamados.',
            'encaminhar': True,
        }
    faq = next(item for item in PERGUNTAS if item['id'] == topico)
    return _resposta_faq(faq)


def _contexto_chat(request, form=None):
    return {
        'pluttu_form': form if form is not None else PluttuForm(),
        'pluttu_historico': request.session.get('pluttu_historico', []),
    }


@never_cache
@require_GET
def ajuda(request):
    busca = request.GET.get('q', '').strip()[:200]
    categoria = request.GET.get('categoria', '')
    if categoria not in {item['slug'] for item in CATEGORIAS_FAQ}:
        categoria = ''
    perguntas = PERGUNTAS
    if categoria:
        perguntas = [item for item in perguntas if item['categoria'] == categoria]
    if busca:
        termos = _normalizar(busca).split()
        perguntas = [
            item for item in perguntas
            if all(termo in _normalizar(item['pergunta'] + ' ' + item['resposta']) for termo in termos)
        ]
    if not busca and not categoria:
        perguntas = [item for item in perguntas if item['destaque']]
    return render(request, 'ajuda/index.html', {
        'busca': busca,
        'categoria_ativa': categoria,
        'categorias': CATEGORIAS_FAQ,
        'perguntas': perguntas,
        'assuntos': ChamadoAjuda.Categoria.choices,
        **_contexto_chat(request),
    })


@never_cache
@require_http_methods(['GET', 'POST'])
def pluttu(request):
    if request.method == 'GET':
        return redirect(reverse('ajuda') + '#pluttu')
    ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.POST.get('acao') == 'limpar':
        request.session.pop('pluttu_historico', None)
        if ajax:
            return JsonResponse({'historico': []})
        return redirect(reverse('ajuda') + '#pluttu')
    form = PluttuForm(request.POST)
    if not form.is_valid():
        if ajax:
            return JsonResponse({'erro': form.errors['mensagem'][0]}, status=400)
        return render(request, 'ajuda/pluttu.html', _contexto_chat(request, form), status=400)
    mensagem = form.cleaned_data['mensagem']
    resposta = _responder_pluttu(mensagem)
    historico = request.session.get('pluttu_historico', [])[-5:]
    historico.append({'mensagem': mensagem, 'resposta': resposta})
    request.session['pluttu_historico'] = historico
    if ajax:
        return JsonResponse({'historico': historico})
    return redirect(reverse('ajuda') + '#pluttu')


@never_cache
@login_required
@require_http_methods(['GET', 'POST'])
def chamado_novo(request):
    pet_id = request.GET.get('pet', '').strip()
    pet = None
    if pet_id:
        if not re.fullmatch(r'[1-9][0-9]{0,17}', pet_id):
            raise Http404('Anúncio indisponível.')
        pet = get_object_or_404(Pet.objects.publicos(), pk=int(pet_id))
    categoria = request.GET.get('categoria', '')
    initial = {'categoria': categoria} if categoria in ChamadoAjuda.Categoria.values else {}
    if pet:
        initial.update({
            'categoria': ChamadoAjuda.Categoria.ADOCAO,
            'assunto': f'Interesse em adotar {pet.nome}',
            'mensagem': f'Olá! Tenho interesse em conhecer {pet.nome}. Gostaria de saber se o pet está disponível para adoção e como posso prosseguir.',
        })
    if request.method == 'GET' and request.GET.get('pluttu') == '1':
        historico = request.session.get('pluttu_historico', [])
        if historico:
            conversa = '\n\n'.join(
                f"Você: {item['mensagem']}\nPluttu: {item['resposta']['texto']}" for item in historico
            )
            initial.update({
                'assunto': 'Dúvida encaminhada pelo Pluttu',
                'mensagem': historico[-1]['mensagem'],
                'conversa_pluttu': signing.dumps({'usuario': request.user.pk, 'conversa': conversa}, salt='pluttu-encaminhamento', compress=True),
            })
    form = ChamadoAjudaForm(request.POST if request.method == 'POST' else None, initial=initial, usuario=request.user, pet=pet)
    if request.method == 'POST' and form.is_valid():
        chamado = form.save(commit=False)
        chamado.usuario = request.user
        chamado.pet = pet
        if form.cleaned_data.get('incluir_conversa'):
            chamado.contexto_pluttu = form.contexto_pluttu
        chamado.save()
        messages.success(request, 'Sua mensagem foi registrada. Acompanhe a resposta por aqui.')
        return redirect('chamado_detalhe', pk=chamado.pk)
    return render(request, 'ajuda/chamado_form.html', {'form': form, 'pet': pet})


@never_cache
@login_required
@require_GET
def meus_chamados(request):
    chamados = ChamadoAjuda.objects.filter(usuario=request.user)
    pagina = Paginator(chamados, 12).get_page(request.GET.get('page'))
    return render(request, 'ajuda/chamados.html', {'pagina': pagina})


@never_cache
@login_required
@require_GET
def chamado_detalhe(request, pk):
    chamado = get_object_or_404(ChamadoAjuda.objects.select_related('pet'), pk=pk, usuario=request.user)
    pet_publico = bool(chamado.pet_id and Pet.objects.publicos().filter(pk=chamado.pet_id).exists())
    return render(request, 'ajuda/chamado_detalhe.html', {'chamado': chamado, 'pet_publico': pet_publico})


@require_GET
def termos(request):
    return render(request, 'ajuda/termos.html')


@require_GET
def privacidade(request):
    return render(request, 'ajuda/privacidade.html')

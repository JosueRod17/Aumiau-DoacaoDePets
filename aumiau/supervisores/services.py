from .models import RegistroAtividade


def registrar_atividade(
    supervisor,
    acao,
    entidade,
    objeto,
    descricao,
):
    descricao = str(descricao).strip()

    if len(descricao) > 255:
        descricao = f'{descricao[:252]}...'

    return RegistroAtividade.objects.create(
        supervisor=supervisor,
        acao=acao,
        entidade=str(entidade)[:40],
        objeto_id=getattr(objeto, 'pk', None),
        descricao=descricao,
    )

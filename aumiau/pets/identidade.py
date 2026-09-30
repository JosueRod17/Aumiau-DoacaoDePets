"""Campos de identificação compartilhados entre anúncio e supervisão."""
from django.utils import timezone
from .models import Pet
from .racas import OUTRA_RACA, RACAS_POR_ESPECIE, escolhas_raca


def configurar_identidade(self):
    self.fields['especie'].choices = [('', 'Selecione uma espécie'), *Pet.Especie.choices]
    self.fields['porte'].choices = [(valor, rotulo) for valor, rotulo in Pet.Porte.choices if valor != Pet.Porte.NAO_INFORMADO]
    if not self.is_bound and self.initial.get('porte') == Pet.Porte.NAO_INFORMADO:
        self.initial['porte'] = ''
    especie = self.data.get('especie') if self.is_bound else self.initial.get('especie', '')
    self.fields['raca'].choices = escolhas_raca(especie)
    if not self.is_bound and self.instance.pk:
        raca = self.instance.raca
        if raca not in dict(self.fields['raca'].choices):
            self.initial['raca'] = OUTRA_RACA
            self.initial['raca_outra'] = raca
        self.initial['nascimento_desconhecido'] = not bool(self.instance.data_nascimento)
    self.catalogo_racas = RACAS_POR_ESPECIE
    self.fields['data_nascimento'].widget.attrs['max'] = timezone.localdate().isoformat()


def limpar_identidade(self, dados):
    self.instance.idade_estimada_informada = bool(dados.get('nascimento_desconhecido'))
    if dados.get('raca') == OUTRA_RACA:
        if not dados.get('raca_outra'):
            self.add_error('raca_outra', 'Informe a raça ou tipo, ou selecione Desconheço.')
        else:
            dados['raca'] = dados['raca_outra']
    if dados.get('nascimento_desconhecido'):
        dados['data_nascimento'] = None
        if dados.get('idade_anos') is None and dados.get('idade_meses') is None:
            self.add_error('idade_anos', 'Informe a idade aproximada em anos ou meses.')
        dados['idade_anos'] = dados.get('idade_anos') or 0
        dados['idade_meses'] = dados.get('idade_meses') or 0
    else:
        nascimento = dados.get('data_nascimento')
        if not nascimento and 'data_nascimento' not in self.errors:
            self.add_error('data_nascimento', 'Informe a data de nascimento ou marque que não sabe.')
        elif nascimento and nascimento > timezone.localdate():
            self.add_error('data_nascimento', 'A data de nascimento não pode ser no futuro.')
        dados['idade_anos'] = 0
        dados['idade_meses'] = 0

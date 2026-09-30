from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Pet


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CadastroAdminPetTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_superuser('admin-form', 'admin@example.com', 'teste')
        self.client.force_login(self.usuario)

    def dados(self, **alteracoes):
        return {
            'nome': 'Amora', 'especie': 'gato', 'raca': 'Sem raça definida', 'genero': 'femea',
            'porte': 'pequeno', 'data_nascimento': '2024-02-01', 'cidade': 'Natal', 'estado': 'RN',
            'descricao': 'Gatinha de teste', 'status': 'pendente',
            'fotos-TOTAL_FORMS': '0', 'fotos-INITIAL_FORMS': '0', 'fotos-MIN_NUM_FORMS': '0',
            'fotos-MAX_NUM_FORMS': '1000', '_save': 'Salvar',
        } | alteracoes

    def test_novo_anuncio_salva_nascimento_e_outra_raca_pelo_admin(self):
        response = self.client.post(reverse('admin:pets_pet_add'), self.dados(raca='__outra__', raca_outra='Raça informada'))
        self.assertEqual(response.status_code, 302)
        pet = Pet.objects.get(nome='Amora')
        self.assertEqual(pet.raca, 'Raça informada')
        self.assertEqual(pet.data_nascimento, date(2024, 2, 1))
        self.assertEqual(pet.responsavel, self.usuario)
        self.assertFalse(pet.idade_estimada_informada)

    def test_idade_estimada_no_admin_e_porte_obrigatorio(self):
        url = reverse('admin:pets_pet_add')
        dados = self.dados(data_nascimento='', nascimento_desconhecido='on', idade_anos='3', idade_meses='4', porte='nao_informado')
        response = self.client.post(url, dados)
        self.assertEqual(response.status_code, 200)
        self.assertIn('porte', response.context['adminform'].form.errors)
        dados['porte'] = 'medio'
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        pet = Pet.objects.get(nome='Amora')
        self.assertIsNone(pet.data_nascimento)
        self.assertTrue(pet.idade_estimada_informada)
        self.assertEqual(pet.idade_atual, (3, 4))

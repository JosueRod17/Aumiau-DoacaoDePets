# Documentação Django
**Autor:** Josué Rodrigues da Silva

## INICIO

### 1. Estar no local onde deseja criar o projeto

Primeiramente deve escolher onde deseja que seu projeto e ambiente virtual sejam criados.

Exemplo:

```text
C:\Users\josue64889816\Documents\dev
```

### 2. Criar um ambiente virtual (VENV)

No terminal, execute:

```bash
python -m venv venv
```

Isso criará uma pasta chamada `venv`, onde ficarão todas as dependências do projeto.

---

### 3. Ativar o ambiente virtual

Primeiro, entre na pasta onde a VENV foi criada.

Exemplo:

```bash
cd C:\Users\josue64889816\Documents\dev
```

Depois, execute:

#### Windows

```bash
venv\Scripts\activate
```

Se tudo der certo, o terminal ficará parecido com:

```text
(venv) C:\Users\Josue\Documents\dev>
```

---

### 4. Instalar o Django

Com a VENV ativada, instale o Django:

```bash
pip install django
```

Para verificar se a instalação deu certo:

```bash
django-admin --version
```

---

### 5. Criar um projeto Django

Execute:

```bash
django-admin startproject nome_do_projeto
```

---

### 6. Entrar na pasta do projeto

```bash
cd nome_do_projeto
```

---

### 7. Executar as migrações iniciais

As migrações criam as tabelas padrão do Django no banco de dados.

```bash
python manage.py migrate
```

---

### 8. Iniciar o servidor

Para verificar se o projeto está funcionando:

```bash
python manage.py runserver
```

Depois, abra o navegador em:

```
http://127.0.0.1:8000/
```

---

### 9. Criar uma aplicação (App)

Dentro do projeto, crie um aplicativo:

```bash
python manage.py startapp nome_do_app
```

Estrutura criada:

```text
membros/
├── migrations/
├── admin.py
├── apps.py
├── models.py
├── tests.py
├── views.py
└── ...
```

---

### 10. Registrar o App

Abra o arquivo:

```text
nome_do_projeto/settings.py
```

Na lista `INSTALLED_APPS`, adicione:

```python
INSTALLED_APPS = [
    ...
    'nome_do_app',
]
```

---
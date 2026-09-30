# Dados de demonstração do AuMiau

Este diretório contém os dados fictícios e as fotos usadas por:

```powershell
python manage.py popular_demo
```

Execute na pasta `aumiau`, após as migrações. O comando só funciona com `AUMIAU_DATA_MODE=local`, não faz downloads e cria 3 ONGs e 12 pets (9 publicados, 2 em análise e 1 adotado). Os cadastros têm códigos exclusivos `demo-ong-sp`, `demo-ong-rj`, `demo-ong-pr` e `demo-pet-01` a `demo-pet-12`. Eles não têm responsáveis, documentos ou contatos reais.

Executar novamente preserva os campos já salvos, inclusive alterações feitas no painel. Apenas cadastros inexistentes são criados; fotos são preenchidas somente quando o campo está vazio. A operação não procura nem modifica cadastros reais por nome.

## Fotos e créditos

As fotografias são reais, mas os nomes, instituições, histórias e informações clínicas dos exemplos são fictícios. Nenhuma fotografia representa um animal anunciado de verdade ou endosso dos fotógrafos e instituições retratadas ao AuMiau.

As 15 fotos foram obtidas no [Pexels](https://www.pexels.com/) e são utilizadas sob a [Pexels License](https://www.pexels.com/license/). Essa licença permite uso em websites e aplicativos, inclusive comerciais, sem exigir atribuição. Não permite revenda das fotos inalteradas ou sua redistribuição como biblioteca concorrente de imagens. Os arquivos são incluídos neste projeto como conteúdo das telas de demonstração.

O arquivo `manifest.json` registra o autor, a página original, a URL de download, a espécie e a licença de cada foto. Downloads feitos em 28/09/2026, com largura de 1000 pixels. Créditos:

| Arquivo | Fotógrafo |
| --- | --- |
| cachorro-01.jpg | SOYD CONTENIDO |
| cachorro-02.jpg | FurtherMore Studio |
| cachorro-03.jpg | Genie Music |
| cachorro-04.jpg | Theerapat Sonphong |
| cachorro-05.jpg | Justus Menke |
| cachorro-06.jpg | Victor Miyata |
| gato-01.jpg | Chalta Phirta |
| gato-02.jpg | Antoun Boustani |
| gato-03.jpg | Leo Tavares |
| gato-04.jpg | Doğu Tuncer |
| coelho-01.jpg | Andy Lee |
| ave-01.jpg | Jiří Mikoláš |
| ong-01.jpg | Mia X |
| ong-02.jpg | Arijit Dey |
| ong-03.jpg | Daigoro Folz |
